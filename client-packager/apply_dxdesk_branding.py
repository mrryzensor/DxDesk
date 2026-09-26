#!/usr/bin/env python3
"""Apply the DxDesk branding overlay to a RustDesk source checkout.

The overlay is intentionally kept outside the RustDesk source tree. This lets
the source checkout be replaced by a newer upstream revision without manually
merging branding changes into RustDesk files.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
CLIENT_DIR = ROOT_DIR / "client"
ASSETS_DIR = ROOT_DIR / "assets"
BRANDING_FILE = ROOT_DIR / "branding.json"


def load_defaults() -> dict[str, str]:
    if BRANDING_FILE.exists():
        with BRANDING_FILE.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    return {
        "app_name": "DxDesk",
        "publisher": "DxDesk",
        "description": "DxDesk Remote Desktop",
        "server_host": "204.216.171.102",
        "server_key": "",
    }


def read_text(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def write_if_changed(path: Path, content: str) -> bool:
    if path.read_text(encoding="utf-8") == content:
        return False
    path.write_text(content, encoding="utf-8", newline="")
    return True


def replace_in_file(path: Path, transform) -> bool:
    content = read_text(path)
    if content is None:
        return False
    updated = transform(content)
    return updated != content and write_if_changed(path, updated)


def generate_svg_wrapper(png_path: Path, svg_dest: Path) -> None:
    encoded = base64.b64encode(png_path.read_bytes()).decode("ascii")
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" '
        f'width="100%" height="100%"><image href="data:image/png;base64,{encoded}" '
        'width="512" height="512"/></svg>'
    )
    svg_dest.write_text(svg, encoding="utf-8")


def copy_if_available(source: Path, destination: Path) -> bool:
    if not source.exists() or not destination.parent.exists():
        return False
    if destination.exists() and destination.read_bytes() == source.read_bytes():
        return False
    shutil.copyfile(source, destination)
    return True


def patch_branding(
    client_dir: Path,
    app_name: str,
    publisher: str,
    description: str,
    host: str,
    key: str,
) -> None:
    print(f"Aplicando la marca {app_name} en {client_dir}")

    config_rs = client_dir / "libs" / "hbb_common" / "src" / "config.rs"

    def patch_config(content: str) -> str:
        def app_name_replacement(match: re.Match[str]) -> str:
            original = match.group(0)
            if "static ref" in original:
                return f'    pub static ref APP_NAME: RwLock<String> = RwLock::new("{app_name}".to_owned());'
            return f'pub const APP_NAME: &str = "{app_name}";'

        content = re.sub(
            r"(?m)^\s*pub\s+(?:static ref|const)\s+APP_NAME[^;]*;",
            app_name_replacement,
            content,
            count=1,
        )
        content = re.sub(
            r"(?m)^\s*pub const RENDEZVOUS_SERVERS: &\[&str\] = &\[[^;]*;",
            f'pub const RENDEZVOUS_SERVERS: &[&str] = &["{host}"];',
            content,
            count=1,
        )
        if key:
            content = re.sub(
                r'(?m)^\s*pub const RS_PUB_KEY: &str = "[^"]*";',
                f'pub const RS_PUB_KEY: &str = "{key}";',
                content,
                count=1,
            )
        return content

    replace_in_file(config_rs, patch_config)

    common_rs = client_dir / "src" / "common.rs"

    def patch_common(content: str) -> str:
        return re.sub(
            r"(?s)(pub fn get_app_name\(\) -> String \{).*?(\n\})",
            lambda match: f'{match.group(1)}\n    "{app_name}".to_string(){match.group(2)}',
            content,
            count=1,
        )

    replace_in_file(common_rs, patch_common)

    common_dart = client_dir / "flutter" / "lib" / "common.dart"

    def patch_dart(content: str) -> str:
        return re.sub(
            r"(?s)String get appName\s*\{.*?\n\}",
            f'String get appName => "{app_name}";',
            content,
            count=1,
        )

    replace_in_file(common_dart, patch_dart)

    # Assets used by Flutter, the native runners and Linux package builders.
    logo_square = ASSETS_DIR / "logo_square.png"
    icon_32 = ASSETS_DIR / "icons" / "icon_32x32.png"
    icon_64 = ASSETS_DIR / "icons" / "icon_64x64.png"
    icon_128 = ASSETS_DIR / "icons" / "icon_128x128.png"
    icon_256 = ASSETS_DIR / "icons" / "icon_256x256.png"
    ico = ASSETS_DIR / "dxdesk.ico"
    icns = ASSETS_DIR / "dxdesk.icns"

    flutter_assets = client_dir / "flutter" / "assets"
    if logo_square.exists() and flutter_assets.exists():
        for name in ("logo.png", "logo_light.png", "logo_dark.png", "icon.png"):
            copy_if_available(logo_square, flutter_assets / name)
        if (flutter_assets / "logo.svg").exists():
            generate_svg_wrapper(logo_square, flutter_assets / "logo.svg")

    res_dir = client_dir / "res"
    if logo_square.exists() and res_dir.exists():
        for name in ("logo.png", "128x128@2x.png", "icon.png", "mac-icon.png"):
            copy_if_available(logo_square, res_dir / name)
        copy_if_available(icon_32, res_dir / "32x32.png")
        copy_if_available(ico, res_dir / "icon.ico")
        copy_if_available(ico, res_dir / "tray-icon.ico")
        if (res_dir / "logo.svg").exists():
            generate_svg_wrapper(logo_square, res_dir / "logo.svg")

    windows_resources = client_dir / "flutter" / "windows" / "runner" / "resources"
    copy_if_available(ico, windows_resources / "app_icon.ico")
    copy_if_available(icns, client_dir / "flutter" / "macos" / "Runner" / "AppIcon.icns")

    def patch_runner_rc(content: str) -> str:
        def replace_value(match: re.Match[str]) -> str:
            field = match.group(1)
            value = {
                "CompanyName": publisher,
                "FileDescription": description,
                "ProductName": app_name,
            }[field]
            return f'            VALUE "{field}", "{value}" "\\0"'

        return re.sub(
            r'(?m)^\s*VALUE "(CompanyName|FileDescription|ProductName)",.*$',
            replace_value,
            content,
        )

    runner_rc = client_dir / "flutter" / "windows" / "runner" / "Runner.rc"
    replace_in_file(runner_rc, patch_runner_rc)
    main_cpp = client_dir / "flutter" / "windows" / "runner" / "main.cpp"
    replace_in_file(
        main_cpp,
        lambda text: re.sub(
            r'CreateAndShow\(L"[^"]+"',
            f'CreateAndShow(L"{app_name}"',
            text,
        ),
    )

    cargo_toml = client_dir / "Cargo.toml"

    def patch_cargo(content: str) -> str:
        content = re.sub(
            r'(?m)^description\s*=\s*"[^"]*"',
            f'description = "{description}"',
            content,
            count=1,
        )
        content = re.sub(
            r'(?m)^ProductName\s*=\s*"[^"]*"',
            f'ProductName = "{app_name}"',
            content,
            count=1,
        )
        content = re.sub(
            r'(?m)^FileDescription\s*=\s*"[^"]*"',
            f'FileDescription = "{description}"',
            content,
            count=1,
        )
        content = re.sub(
            r'(?m)^LegalCopyright\s*=\s*"[^"]*"',
            f'LegalCopyright = "Copyright © 2026 {publisher}"',
            content,
            count=1,
        )
        return content

    replace_in_file(cargo_toml, patch_cargo)

    # Android, iOS, macOS and Linux visible labels. Internal protocol names,
    # package IDs and URI schemes intentionally remain RustDesk-compatible.
    strings_xml = client_dir / "flutter" / "android" / "app" / "src" / "main" / "res" / "values" / "strings.xml"
    replace_in_file(strings_xml, lambda text: text.replace("RustDesk", app_name))
    manifest = client_dir / "flutter" / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
    replace_in_file(
        manifest,
        lambda text: re.sub(r'android:label="RustDesk"', f'android:label="{app_name}"', text),
    )
    ios_plist = client_dir / "flutter" / "ios" / "Runner" / "Info.plist"
    replace_in_file(ios_plist, lambda text: text.replace(">RustDesk<", f">{app_name}<"))
    mac_xcconfig = client_dir / "flutter" / "macos" / "Runner" / "Configs" / "AppInfo.xcconfig"
    replace_in_file(
        mac_xcconfig,
        lambda text: re.sub(r'(?m)^PRODUCT_NAME\s*=.*$', f'PRODUCT_NAME = {app_name}', text),
    )
    linux_app = client_dir / "flutter" / "linux" / "my_application.cc"
    replace_in_file(
        linux_app,
        lambda text: text.replace(
            'set_title(header_bar, "rustdesk")',
            f'set_title(header_bar, "{app_name}")',
        ).replace(
            'set_title(window, "rustdesk")',
            f'set_title(window, "{app_name}")',
        ),
    )

    # Source icon directories generated by flutter_launcher_icons.
    mipmap_sizes = {
        "mipmap-mdpi": icon_32,
        "mipmap-hdpi": icon_64,
        "mipmap-xhdpi": icon_128,
        "mipmap-xxhdpi": icon_256,
        "mipmap-xxxhdpi": icon_256,
    }
    android_res = client_dir / "flutter" / "android" / "app" / "src" / "main" / "res"
    for directory, source in mipmap_sizes.items():
        if source.exists():
            for candidate in android_res.glob(f"{directory}*/ic_launcher*.png"):
                copy_if_available(source, candidate)

    print("Marca y recursos aplicados correctamente.")


def main() -> None:
    defaults = load_defaults()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", nargs="?", default=defaults["server_host"])
    parser.add_argument("key", nargs="?", default=defaults.get("server_key", ""))
    parser.add_argument("--client-dir", type=Path, default=CLIENT_DIR)
    args = parser.parse_args()
    patch_branding(
        args.client_dir.resolve(),
        defaults.get("app_name", "DxDesk"),
        defaults.get("publisher", "DxDesk"),
        defaults.get("description", "DxDesk Remote Desktop"),
        args.host,
        args.key,
    )


if __name__ == "__main__":
    main()
