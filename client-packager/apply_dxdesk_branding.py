#!/usr/bin/env python3
"""
DxDesk - Aplicador de Marca Total sobre client/
Aplica el logo, iconos, nombres y servidor en todo el código fuente:
- Flutter UI (iconos, logos, appName, pantallas y diálogos)
- Rust Core (libs/hbb_common/src/config.rs, src/common.rs)
- Windows Runner (main.cpp, Runner.rc, app_icon.ico)
- Linux / Android / macOS assets
"""

import os
import shutil
import re
import sys
import base64

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CLIENT_DIR = os.path.join(ROOT_DIR, "client")
ASSETS_DIR = os.path.join(ROOT_DIR, "assets")

def generate_svg_wrapper(png_path: str, svg_dest: str):
    """Genera un archivo SVG que incrusta el PNG en base64 para reemplazar los SVGs de RustDesk."""
    with open(png_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="100%" height="100%">
  <image href="data:image/png;base64,{b64}" width="512" height="512"/>
</svg>'''
    with open(svg_dest, "w", encoding="utf-8") as f:
        f.write(svg_content)

def apply_branding(app_name="DxDesk", host="204.216.171.102", key=""):
    print(f"\n=======================================================")
    print(f"  Aplicando Marca Profunda '{app_name}' en client/")
    print(f"  Servidor predeterminado: {host}")
    print(f"=======================================================\n")

    ico_path = os.path.join(ASSETS_DIR, "dxdesk.ico")
    logo_square = os.path.join(ASSETS_DIR, "logo_square.png")
    icon_128 = os.path.join(ASSETS_DIR, "icons", "icon_128x128.png")
    icon_64 = os.path.join(ASSETS_DIR, "icons", "icon_64x64.png")
    icon_32 = os.path.join(ASSETS_DIR, "icons", "icon_32x32.png")

    # 1. Modificar libs/hbb_common/src/config.rs
    config_rs = os.path.join(CLIENT_DIR, "libs", "hbb_common", "src", "config.rs")
    if os.path.exists(config_rs):
        print("[1/5] Modificando libs/hbb_common/src/config.rs...")
        with open(config_rs, "r", encoding="utf-8") as f:
            c = f.read()

        # APP_NAME
        c = re.sub(
            r'pub static ref APP_NAME: RwLock<String> = RwLock::new\("[^"]+"\..*?\);',
            f'pub static ref APP_NAME: RwLock<String> = RwLock::new("{app_name}".to_owned());',
            c
        )
        
        # Servidor por defecto
        c = re.sub(
            r'pub const RENDEZVOUS_SERVERS: &\[&str\] = &\[[^\]]*\];',
            f'pub const RENDEZVOUS_SERVERS: &[&str] = &["{host}"];',
            c
        )
        if key:
            c = re.sub(
                r'pub const RS_PUB_KEY: &str = "[^"]*";',
                f'pub const RS_PUB_KEY: &str = "{key}";',
                c
            )

        with open(config_rs, "w", encoding="utf-8") as f:
            f.write(c)
        print("  -> APP_NAME y RENDEZVOUS_SERVERS configurados.")

    # 2. Modificar src/common.rs
    common_rs = os.path.join(CLIENT_DIR, "src", "common.rs")
    if os.path.exists(common_rs):
        print("[2/5] Modificando src/common.rs (get_app_name)...")
        with open(common_rs, "r", encoding="utf-8") as f:
            c = f.read()
        c = re.sub(
            r'pub fn get_app_name\(\) -> String \{[^}]*\}',
            f'pub fn get_app_name() -> String {{\n    "{app_name}".to_string()\n}}',
            c
        )
        with open(common_rs, "w", encoding="utf-8") as f:
            f.write(c)
        print("  -> get_app_name() forzado a devolver DxDesk.")

    # 3. Modificar flutter/lib/common.dart
    common_dart = os.path.join(CLIENT_DIR, "flutter", "lib", "common.dart")
    if os.path.exists(common_dart):
        print("[3/5] Modificando flutter/lib/common.dart (appName getter)...")
        with open(common_dart, "r", encoding="utf-8") as f:
            dart = f.read()
        # Forzar getter appName
        dart = re.sub(
            r'String get appName \{[^}]*return _appName;\s*\}',
            f'String get appName => "{app_name}";',
            dart
        )
        with open(common_dart, "w", encoding="utf-8") as f:
            f.write(dart)
        print("  -> Flutter appName getter actualizado a DxDesk.")

    # 4. Reemplazar logos e iconos en flutter/assets/
    flutter_assets = os.path.join(CLIENT_DIR, "flutter", "assets")
    if os.path.exists(flutter_assets):
        print("[4/5] Reemplazando imágenes de la interfaz en flutter/assets/...")
        for name in ["logo.png", "logo_light.png", "logo_dark.png", "icon.png"]:
            shutil.copyfile(logo_square, os.path.join(flutter_assets, name))
        generate_svg_wrapper(logo_square, os.path.join(flutter_assets, "logo.svg"))
        print("  -> Todos los logos de la ventana de Flutter reemplazados por tu logo.")

    # 5. Modificar Runner de Windows (barra de título y metadatos)
    print("[5/5] Actualizando Runner de Windows...")
    win_res = os.path.join(CLIENT_DIR, "flutter", "windows", "runner", "resources")
    if os.path.exists(win_res) and os.path.exists(ico_path):
        shutil.copyfile(ico_path, os.path.join(win_res, "app_icon.ico"))
        
    main_cpp = os.path.join(CLIENT_DIR, "flutter", "windows", "runner", "main.cpp")
    if os.path.exists(main_cpp):
        with open(main_cpp, "r", encoding="utf-8") as f:
            cpp = f.read()
        cpp = re.sub(r'CreateAndShow\(L"[^"]+"', f'CreateAndShow(L"{app_name}"', cpp)
        with open(main_cpp, "w", encoding="utf-8") as f:
            f.write(cpp)

    runner_rc = os.path.join(CLIENT_DIR, "flutter", "windows", "runner", "Runner.rc")
    if os.path.exists(runner_rc):
        with open(runner_rc, "r", encoding="utf-8") as f:
            rc = f.read()
        rc = rc.replace("RustDesk", app_name)
        with open(runner_rc, "w", encoding="utf-8") as f:
            f.write(rc)

    # 6. Reemplazar en res/
    res_dir = os.path.join(CLIENT_DIR, "res")
    if os.path.exists(res_dir):
        if os.path.exists(ico_path):
            shutil.copyfile(ico_path, os.path.join(res_dir, "icon.ico"))
        shutil.copyfile(logo_square, os.path.join(res_dir, "128x128@2x.png"))
        if os.path.exists(icon_32):
            shutil.copyfile(icon_32, os.path.join(res_dir, "32x32.png"))
        shutil.copyfile(logo_square, os.path.join(res_dir, "logo.png"))
        generate_svg_wrapper(logo_square, os.path.join(res_dir, "logo.svg"))

    print("\n" + "="*55)
    print(f"  ¡MARCA '{app_name}' APLICADA AL 100% EN TODO EL CÓDIGO!")
    print("="*55 + "\n")

if __name__ == "__main__":
    h = sys.argv[1] if len(sys.argv) > 1 else "204.216.171.102"
    k = sys.argv[2] if len(sys.argv) > 2 else ""
    apply_branding(app_name="DxDesk", host=h, key=k)
