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
        "server_key": "NH9EpepEnWXY5I8r3lv2qnCNDxYucPzDtoBsK6imNcg=",
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


def _replace_literals(content: str, replacements: tuple[tuple[str, str], ...]) -> str:
    for old, new in replacements:
        content = content.replace(old, new)
    return content


def generate_svg_wrapper(png_path: Path, svg_dest: Path) -> None:
    encoded = base64.b64encode(png_path.read_bytes()).decode("ascii")
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" '
        f'width="100%" height="100%"><image href="data:image/png;base64,{encoded}" '
        'width="512" height="512"/></svg>'
    )
    svg_dest.write_text(svg, encoding="utf-8")


def generate_png_variant(source: Path, destination: Path, size: int) -> None:
    """Create a small PNG used by native tray code from the branded square logo."""
    if not source.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image

        with Image.open(source) as image:
            resized = image.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
            resized.save(destination, format="PNG")
    except ImportError:
        # The workflows install Pillow before running this overlay. Keep a
        # dependency-free fallback for local source preparation.
        shutil.copyfile(source, destination)


def generate_portable_label(source: Path, destination: Path, app_name: str) -> None:
    """Generate the small branded label embedded in the Windows portable stub."""
    if not source.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image, ImageDraw, ImageFont

        canvas = Image.new("RGBA", (96, 32), (0, 0, 0, 0))
        with Image.open(source) as image:
            logo = image.convert("RGBA")
            logo.thumbnail((24, 24), Image.Resampling.LANCZOS)
            canvas.alpha_composite(logo, (4, (32 - logo.height) // 2))

        draw = ImageDraw.Draw(canvas)
        font = ImageFont.load_default()
        bounds = draw.textbbox((0, 0), app_name, font=font)
        text_width = bounds[2] - bounds[0]
        text_height = bounds[3] - bounds[1]
        draw.text(
            (32, (32 - text_height) // 2 - bounds[1]),
            app_name,
            fill=(255, 255, 255, 255),
            font=font,
        )
        # Keep the label readable even if a future app name is wider than the
        # portable stub's fixed 96px slot.
        if text_width > 60:
            draw.rectangle((92, 0, 95, 31), fill=(0, 0, 0, 0))
        canvas.save(destination, format="PNG")
    except ImportError:
        # All CI workflows install Pillow. This fallback still provides a valid
        # image for local builds without the optional dependency.
        shutil.copyfile(source, destination)


def copy_if_available(source: Path, destination: Path) -> bool:
    if not source.exists():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
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
    upstream_repository = load_defaults().get("upstream_repository", "https://rustdesk.com")

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
        content = re.sub(
            r"(?s)String get appName\s*\{.*?\n\}",
            f'String get appName => "{app_name}";',
            content,
            count=1,
        )
        # Do not expose the upstream attribution link in a branded client.
        # Keep the widget as a no-op because callers still reference it.
        return re.sub(
            r"(?s)Widget loadPowered\(BuildContext context\) \{.*?\n\}\n\nconst _kDefaultLogoAsset",
            "Widget loadPowered(BuildContext context) => const SizedBox.shrink();\n\nconst _kDefaultLogoAsset",
            content,
            count=1,
        )

    replace_in_file(common_dart, patch_dart)

    # Replace visible product labels while leaving protocol names, package IDs,
    # native library names and compatibility paths unchanged.
    visible_label_files = {
        client_dir / "flutter" / "lib" / "mobile" / "pages" / "settings_page.dart": (
            ("Keep RustDesk background service", f"Keep {app_name} background service"),
            ("About RustDesk", f"About {app_name}"),
        ),
        client_dir / "flutter" / "lib" / "desktop" / "pages" / "desktop_setting_page.dart": (
            ("About RustDesk", f"About {app_name}"),
        ),
        client_dir / "flutter" / "lib" / "desktop" / "widgets" / "tabbar_widget.dart": (
            ('"RustDesk",', f'"{app_name}",'),
        ),
        client_dir / "flutter" / "android" / "app" / "src" / "main" / "kotlin" / "com" / "carriez" / "flutter_hbb" / "BootReceiver.kt": (
            ('"RustDesk is Open"', f'"{app_name} is Open"'),
        ),
        client_dir / "flutter" / "android" / "app" / "src" / "main" / "kotlin" / "com" / "carriez" / "flutter_hbb" / "FloatingWindowService.kt": (
            ('translate("Show RustDesk")', f'translate("Show {app_name}")'),
        ),
        client_dir / "flutter" / "android" / "app" / "src" / "main" / "kotlin" / "com" / "carriez" / "flutter_hbb" / "MainService.kt": (
            ('"RustDesk"', f'"{app_name}"'),
            ('"RustDesk Service"', f'"{app_name} Service"'),
            ('"RustDesk Service Channel"', f'"{app_name} Service Channel"'),
        ),
    }
    for path, replacements in visible_label_files.items():
        replace_in_file(
            path,
            lambda text, replacements=replacements: _replace_literals(text, replacements),
        )

    # The legacy UI and all language packs share this attribution key. Emptying
    # it protects builds that still load the legacy UI while the Flutter widget
    # above remains a harmless no-op.
    for language_file in (client_dir / "src" / "lang").glob("*.rs"):
        replace_in_file(
            language_file,
            lambda text: re.sub(
                r'(\("powered_by_me",\s*)"(?:[^"\\]|\\.)*"',
                r'\1""',
                text,
            ),
        )
    replace_in_file(
        client_dir / "src" / "ui" / "index.tis",
        lambda text: text.replace("translate('powered_by_me')", '""'),
    )

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
        for source, name in (
            (icon_32, "32x32.png"),
            (icon_64, "64x64.png"),
            (icon_128, "128x128.png"),
            (icon_256, "256x256.png"),
        ):
            copy_if_available(source, res_dir / name)
        copy_if_available(icon_32, res_dir / "32x32.png")
        copy_if_available(ico, res_dir / "icon.ico")
        copy_if_available(ico, res_dir / "tray-icon.ico")
        copy_if_available(icns, res_dir / "AppIcon.icns")
        # RustDesk keeps these two macOS tray templates ignored by the
        # upstream client .gitignore. Generate them on every branded build so
        # a clean GitHub runner cannot fail at src/tray.rs:include_bytes!.
        generate_png_variant(logo_square, res_dir / "mac-tray-dark-x2.png", 60)
        generate_png_variant(logo_square, res_dir / "mac-tray-light-x2.png", 48)
        if (res_dir / "logo.svg").exists():
            generate_svg_wrapper(logo_square, res_dir / "logo.svg")
        scalable_svg = res_dir / "scalable.svg"
        if scalable_svg.exists() or logo_square.exists():
            generate_svg_wrapper(logo_square, scalable_svg)

        # The portable packer includes this file at compile time. RustDesk's
        # upstream .gitignore excludes it, so create it on every clean runner.
        generate_portable_label(
            logo_square,
            client_dir / "libs" / "portable" / "src" / "res" / "label.png",
            app_name,
        )

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
    replace_in_file(
        main_cpp,
        lambda text: text.replace('std::wstring app_name = L"RustDesk"', f'std::wstring app_name = L"{app_name}"'),
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

    portable_cargo_toml = client_dir / "libs" / "portable" / "Cargo.toml"
    replace_in_file(portable_cargo_toml, patch_cargo)

    # Android, iOS, macOS and Linux visible labels. Internal protocol names,
    # package IDs and URI schemes intentionally remain RustDesk-compatible.
    strings_xml = client_dir / "flutter" / "android" / "app" / "src" / "main" / "res" / "values" / "strings.xml"
    replace_in_file(strings_xml, lambda text: text.replace("RustDesk", app_name))
    manifest = client_dir / "flutter" / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
    replace_in_file(
        manifest,
        lambda text: text.replace("RustDesk", app_name),
    )
    ios_plist = client_dir / "flutter" / "ios" / "Runner" / "Info.plist"
    replace_in_file(ios_plist, lambda text: text.replace(">RustDesk<", f">{app_name}<"))
    mac_xcconfig = client_dir / "flutter" / "macos" / "Runner" / "Configs" / "AppInfo.xcconfig"
    replace_in_file(
        mac_xcconfig,
        lambda text: re.sub(r'(?m)^PRODUCT_NAME\s*=.*$', f'PRODUCT_NAME = {app_name}', text),
    )
    mac_project = client_dir / "flutter" / "macos" / "Runner.xcodeproj" / "project.pbxproj"
    replace_in_file(mac_project, lambda text: text.replace("RustDesk.app", f"{app_name}.app"))
    mac_scheme = client_dir / "flutter" / "macos" / "Runner.xcodeproj" / "xcshareddata" / "xcschemes" / "Runner.xcscheme"
    replace_in_file(mac_scheme, lambda text: text.replace("RustDesk.app", f"{app_name}.app"))
    linux_app = client_dir / "flutter" / "linux" / "my_application.cc"
    replace_in_file(
        linux_app,
        lambda text: text.replace(
            'gtk_header_bar_set_title(header_bar, "rustdesk")',
            f'gtk_header_bar_set_title(header_bar, "{app_name}")',
        ).replace(
            'gtk_window_set_title(window, "rustdesk")',
            f'gtk_window_set_title(window, "{app_name}")',
        ),
    )

    for desktop_file in (res_dir / "rustdesk.desktop", res_dir / "rustdesk-link.desktop"):
        replace_in_file(
            desktop_file,
            lambda text: re.sub(
                r"(?m)^(Name|GenericName|Comment)=.*$",
                lambda match: {
                    "Name": app_name,
                    "GenericName": f"{app_name} Remote Desktop",
                    "Comment": description,
                }[match.group(1)],
                text,
            ),
        )

    # Linux package metadata is generated by build.py and the RPM templates. Keep the
    # executable/package paths as rustdesk for compatibility, but expose DxDesk to users.
    build_py = client_dir / "build.py"
    replace_in_file(
        build_py,
        lambda text: text.replace(
            "Maintainer: rustdesk <info@rustdesk.com>",
            f"Maintainer: {publisher}",
        ).replace(
            "Homepage: https://rustdesk.com",
            f"Homepage: {upstream_repository}",
        ).replace(
            "Description: A remote control software.",
            f"Description: {description}.",
        ).replace(
            '"RustDesk Installer"',
            f'"{app_name} Installer"',
        ).replace(
            '"--icon RustDesk.app',
            f'"--icon {app_name}.app',
        ).replace(
            'Products/Release/RustDesk.app',
            f'Products/Release/{app_name}.app',
        ),
    )
    for rpm_file in client_dir.glob("res/rpm*.spec"):
        replace_in_file(
            rpm_file,
            lambda text: text.replace("URL:        https://rustdesk.com", f"URL:        {upstream_repository}")
            .replace("Vendor:     rustdesk <info@rustdesk.com>", f"Vendor:     {publisher}"),
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
            destination_dir = android_res / directory
            for name in ("ic_launcher.png", "ic_launcher_round.png", "ic_launcher_foreground.png"):
                copy_if_available(source, destination_dir / name)
            # Android notification icons are also ignored by the upstream
            # checkout but are referenced by MainService.kt.
            copy_if_available(icon_32, destination_dir / "ic_stat_logo.png")

    required_branding_assets = [
        client_dir / "libs" / "portable" / "src" / "res" / "label.png",
        *(
            android_res / directory / "ic_launcher_foreground.png"
            for directory in mipmap_sizes
        ),
    ]
    missing_assets = [str(path) for path in required_branding_assets if not path.is_file()]
    if missing_assets:
        raise RuntimeError(
            "No se pudieron generar los recursos de branding requeridos:\n"
            + "\n".join(missing_assets)
        )

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
