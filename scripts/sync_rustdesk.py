#!/usr/bin/env python3
"""Replace the vendored client with a branded RustDesk upstream revision.

The repository keeps ``client/`` as a generated vendor snapshot. The branding
overlay is applied after every sync, so upstream changes and local identity
changes do not have to be merged by hand.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
CLIENT_DIR = ROOT_DIR / "client"
STATE_FILE = ROOT_DIR / ".upstream-rustdesk.json"
BRANDING_FILE = ROOT_DIR / "branding.json"
BRANDING_SCRIPT = ROOT_DIR / "client-packager" / "apply_dxdesk_branding.py"


def run(command: list[str], cwd: Path | None = None, capture_output: bool = False) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        check=True,
        text=True,
        capture_output=capture_output,
    )
    return result.stdout.strip() if capture_output else ""


def load_branding() -> dict[str, str]:
    with BRANDING_FILE.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def current_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    with STATE_FILE.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_state(repository: str, ref: str, commit: str, previous: dict) -> None:
    if (
        previous.get("repository") == repository
        and previous.get("ref") == ref
        and previous.get("commit") == commit
        and STATE_FILE.exists()
    ):
        return
    state = {
        "repository": repository,
        "ref": ref,
        "commit": commit,
        "synced_at": datetime.now(timezone.utc).isoformat(),
    }
    content = json.dumps(state, indent=2, ensure_ascii=False) + "\n"
    if not STATE_FILE.exists() or STATE_FILE.read_text(encoding="utf-8") != content:
        STATE_FILE.write_text(content, encoding="utf-8")


def clone_upstream(repository: str, ref: str, destination: Path) -> None:
    run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--recurse-submodules",
            "--shallow-submodules",
            "--branch",
            ref,
            repository,
            str(destination),
        ]
    )


def sync_client(source: Path) -> None:
    resolved_root = ROOT_DIR.resolve()
    resolved_client = CLIENT_DIR.resolve()
    if resolved_client.parent != resolved_root or resolved_client.name != "client":
        raise RuntimeError(f"Refusing to replace unexpected client path: {resolved_client}")
    if CLIENT_DIR.exists() and not (CLIENT_DIR / "Cargo.toml").exists():
        raise RuntimeError("Refusing to replace client/: Cargo.toml was not found")

    if CLIENT_DIR.exists():
        shutil.rmtree(CLIENT_DIR)
    shutil.copytree(
        source,
        CLIENT_DIR,
        ignore=shutil.ignore_patterns(".git", "target", "build", ".dart_tool"),
    )


def stabilize_upstream_build_files() -> None:
    """Reapply CI compatibility patches after replacing the vendored checkout.

    RustDesk's upstream checkout is intentionally replaced wholesale during a
    sync. These build inputs need local fixes for the hosted runners: vcpkg
    must keep each Android ABI in its own install root, and AppImage Builder
    must accept both xz and zstd Debian payloads.
    """
    android_deps = CLIENT_DIR / "flutter" / "build_android_deps.sh"
    if android_deps.is_file():
        content = android_deps.read_text(encoding="utf-8")
        if "ISOLATED_ROOT=\"${VCPKG_ROOT}/android-installed/${VCPKG_TARGET}\"" not in content:
            marker = 'echo "INFO: Building and install vcpkg dependencies for Android ${ANDROID_ABI} ..."\n\n'
            isolated = (
                "# vcpkg manifest mode can remove the previous ABI when all Android\n"
                "# triplets share one install root. Build each ABI in isolation and\n"
                "# copy its complete tree to the stable location consumed by Cargo.\n"
                "ISOLATED_ROOT=\"${VCPKG_ROOT}/android-installed/${VCPKG_TARGET}\"\n"
                "FINAL_TRIPLET_ROOT=\"${VCPKG_ROOT}/installed/${VCPKG_TARGET}\"\n"
                "rm -rf \"${ISOLATED_ROOT}\" \"${FINAL_TRIPLET_ROOT}\"\n"
                "mkdir -p \"${ISOLATED_ROOT}\" \"${VCPKG_ROOT}/installed\"\n\n"
            )
            if marker not in content:
                raise RuntimeError(f"No se encontró el punto de parcheo Android: {android_deps}")
            content = content.replace(marker, marker + isolated, 1)
            if '--x-install-root=' in content:
                content = content.replace(
                    '\t--x-install-root="${VCPKG_ROOT}/installed"',
                    '\t--x-install-root="${ISOLATED_ROOT}"',
                    1,
                )
            else:
                content = content.replace(
                    '\t--triplet "${VCPKG_TARGET}"',
                    '\t--triplet "${VCPKG_TARGET}" \\\n\t--x-install-root="${ISOLATED_ROOT}"',
                    1,
                )
            completion = 'popd\n\necho "INFO: Completed building vcpkg dependencies for Android ${ANDROID_ABI}"'
            replacement = (
                "popd\n\n"
                "if [ ! -d \"${ISOLATED_ROOT}/${VCPKG_TARGET}\" ]; then\n"
                "\techo \"ERROR: vcpkg did not create the ${VCPKG_TARGET} install tree\" 1>&2\n"
                "\texit 1\n"
                "fi\n"
                "cp -a \"${ISOLATED_ROOT}/${VCPKG_TARGET}\" \"${FINAL_TRIPLET_ROOT}\"\n\n"
                "if [ ! -s \"${FINAL_TRIPLET_ROOT}/include/opus/opus_multistream.h\" ] ||\n"
                "\t[ ! -s \"${FINAL_TRIPLET_ROOT}/lib/libopus.a\" ]; then\n"
                "\techo \"ERROR: incomplete Opus package for ${VCPKG_TARGET}\" 1>&2\n"
                "\texit 1\n"
                "fi\n\n"
                'echo "INFO: Completed building vcpkg dependencies for Android ${ANDROID_ABI}"'
            )
            if completion not in content:
                raise RuntimeError(f"No se encontró el cierre de parcheo Android: {android_deps}")
            content = content.replace(completion, replacement, 1)
            android_deps.write_text(content, encoding="utf-8", newline="\n")

    for recipe_name in ("AppImageBuilder-x86_64.yml", "AppImageBuilder-aarch64.yml"):
        recipe = CLIENT_DIR / "appimage" / recipe_name
        if not recipe.is_file():
            continue
        content = recipe.read_text(encoding="utf-8")
        patched = content.replace("bsdtar -zxvf rustdesk.deb", "bsdtar -xf rustdesk.deb")
        patched = patched.replace("tar -xvf ./data.tar.xz", "tar -xvf ./data.tar.*")
        if patched != content:
            recipe.write_text(patched, encoding="utf-8", newline="\n")


def set_github_output(commit: str, changed: bool) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            handle.write(f"upstream_sha={commit}\n")
            handle.write(f"changed={'true' if changed else 'false'}\n")


def main() -> int:
    branding = load_branding()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=branding["upstream_repository"])
    parser.add_argument("--ref", default=branding["upstream_ref"])
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    commit = run(
        ["git", "ls-remote", args.repository, f"refs/heads/{args.ref}"],
        capture_output=True,
    ).split()[0]
    old_state = current_state()
    upstream_changed = old_state.get("commit") != commit
    source_changed = upstream_changed or args.force or not (CLIENT_DIR / "Cargo.toml").exists()

    if source_changed:
        with tempfile.TemporaryDirectory(prefix="dxdesk-rustdesk-") as temp_dir:
            upstream_dir = Path(temp_dir) / "rustdesk"
            print(f"Clonando {args.repository}@{args.ref} ({commit[:12]})...")
            clone_upstream(args.repository, args.ref, upstream_dir)
            sync_client(upstream_dir)

    stabilize_upstream_build_files()

    # Reapply the overlay even when upstream did not move, so branding.json or
    # the logo can be changed independently of the upstream sync.
    run(
        [
            sys.executable,
            str(BRANDING_SCRIPT),
            "--client-dir",
            str(CLIENT_DIR),
            branding["server_host"],
            branding.get("server_key", ""),
        ]
    )
    write_state(args.repository, args.ref, commit, old_state)
    set_github_output(commit, source_changed)
    print(f"RustDesk upstream sincronizado en {commit}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
