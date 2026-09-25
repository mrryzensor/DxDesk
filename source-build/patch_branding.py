#!/usr/bin/env python3
"""
DxDesk - Script Integral de Rebranding para el Código Fuente de RustDesk
Modifica absolutamente todos los elementos visuales y de texto:
- Logos internos (interfaz Flutter, menú Acerca de, cabecera).
- Nombre de la aplicación (de 'RustDesk' a 'DxDesk' en ventana, barra de tareas y diálogos).
- Iconos del sistema (bandeja del sistema, barra de tareas, instalador).
- Icono en Base64 dentro del núcleo de Rust (libs/hbb_common/src/config.rs).
- Preconfiguración fija de tu Servidor Oracle/Coolify y Clave Pública.
"""

import os
import shutil
import re
import sys
import base64
from PIL import Image

def generate_svg_wrapper(png_path: str, svg_dest: str):
    """Genera un archivo SVG que incrusta el PNG en base64 para reemplazar los SVGs de RustDesk."""
    with open(png_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="100%" height="100%">
  <image href="data:image/png;base64,{b64}" width="512" height="512"/>
</svg>'''
    with open(svg_dest, "w", encoding="utf-8") as f:
        f.write(svg_content)

def apply_full_rebrand(repo_dir: str, assets_dir: str, app_name: str = "DxDesk", host: str = "", pub_key: str = ""):
    if not os.path.exists(repo_dir):
        print(f"Error: No se encontró el repositorio en '{repo_dir}'")
        return False

    ico_path = os.path.join(assets_dir, "dxdesk.ico")
    logo_square = os.path.join(assets_dir, "logo_square.png")
    icon_128 = os.path.join(assets_dir, "icons", "icon_128x128.png")
    icon_64 = os.path.join(assets_dir, "icons", "icon_64x64.png")
    icon_32 = os.path.join(assets_dir, "icons", "icon_32x32.png")

    print(f"\n=========================================================")
    print(f"   Iniciando Rebranding Completo a: '{app_name}'")
    print(f"=========================================================")

    # 1. Base64 del icono para Rust Core
    with open(icon_64 if os.path.exists(icon_64) else logo_square, "rb") as f:
        icon_b64 = base64.b64encode(f.read()).decode("utf-8")
        data_uri_icon = f"data:image/png;base64,{icon_b64}"

    # 2. Modificar libs/hbb_common/src/config.rs
    config_rs = os.path.join(repo_dir, "libs", "hbb_common", "src", "config.rs")
    if os.path.exists(config_rs):
        print("[1/6] Parcheando constantes en Rust Core (config.rs)...")
        with open(config_rs, "r", encoding="utf-8") as f:
            c = f.read()

        # Reemplazar APP_NAME (soporta formato const o Arc<RwLock>)
        c = re.sub(r'pub const APP_NAME: &str = "[^"]+";', f'pub const APP_NAME: &str = "{app_name}";', c)
        c = re.sub(r'APP_NAME: Arc<RwLock<String>> = Arc::new\(RwLock::new\("[^"]+"\..*?\)\);', 
                   f'APP_NAME: Arc<RwLock<String>> = Arc::new(RwLock::new("{app_name}".to_owned()));', c)

        # Reemplazar ICON en base64
        c = re.sub(r'pub const ICON: &str = "data:image/png;base64,[^"]+";', 
                   f'pub const ICON: &str = "{data_uri_icon}";', c)

        # Servidor y clave fija
        if host:
            c = re.sub(r'pub const RENDEZVOUS_SERVERS: &\[&str\] = &\[[^\]]*\];', 
                       f'pub const RENDEZVOUS_SERVERS: &[&str] = &["{host}"];', c)
        if pub_key:
            c = re.sub(r'pub const RS_PUB_KEY: &str = "[^"]*";', 
                       f'pub const RS_PUB_KEY: &str = "{pub_key}";', c)

        with open(config_rs, "w", encoding="utf-8") as f:
            f.write(c)
        print("  -> config.rs actualizado con éxito.")

    # 3. Reemplazar Assets de la interfaz Flutter (Logo en pantalla principal, About y Menús)
    flutter_assets = os.path.join(repo_dir, "flutter", "assets")
    if os.path.exists(flutter_assets):
        print("[2/6] Reemplazando logos e imágenes de la UI en Flutter...")
        for fname in ["logo.png", "logo_light.png", "logo_dark.png", "icon.png"]:
            shutil.copyfile(logo_square, os.path.join(flutter_assets, fname))
        generate_svg_wrapper(logo_square, os.path.join(flutter_assets, "logo.svg"))
        print("  -> flutter/assets/ reemplazado con tu logo.")

    # 4. Reemplazar Icono en el Runner de Windows (barra de título y ventana nativa)
    flutter_win_res = os.path.join(repo_dir, "flutter", "windows", "runner", "resources")
    if os.path.exists(flutter_win_res) and os.path.exists(ico_path):
        print("[3/6] Inyectando icono en el Runner de Windows...")
        shutil.copyfile(ico_path, os.path.join(flutter_win_res, "app_icon.ico"))

    # Parchear el título de la ventana de Windows
    runner_rc = os.path.join(repo_dir, "flutter", "windows", "runner", "Runner.rc")
    if os.path.exists(runner_rc):
        with open(runner_rc, "r", encoding="utf-8") as f:
            rc = f.read()
        rc = rc.replace("RustDesk", app_name)
        with open(runner_rc, "w", encoding="utf-8") as f:
            f.write(rc)
        print("  -> Runner.rc actualizado con el nombre", app_name)

    main_cpp = os.path.join(repo_dir, "flutter", "windows", "runner", "main.cpp")
    if os.path.exists(main_cpp):
        with open(main_cpp, "r", encoding="utf-8") as f:
            cpp = f.read()
        cpp = re.sub(r'CreateAndShow\(L"[^"]+"', f'CreateAndShow(L"{app_name}"', cpp)
        with open(main_cpp, "w", encoding="utf-8") as f:
            f.write(cpp)
        print("  -> main.cpp ventana principal actualizada.")

    # 5. Reemplazar recursos generales en res/
    res_dir = os.path.join(repo_dir, "res")
    if os.path.exists(res_dir):
        print("[4/6] Reemplazando iconos de sistema en res/...")
        if os.path.exists(ico_path):
            shutil.copyfile(ico_path, os.path.join(res_dir, "icon.ico"))
        shutil.copyfile(logo_square, os.path.join(res_dir, "128x128@2x.png"))
        if os.path.exists(icon_32):
            shutil.copyfile(icon_32, os.path.join(res_dir, "32x32.png"))
        shutil.copyfile(logo_square, os.path.join(res_dir, "logo.png"))
        generate_svg_wrapper(logo_square, os.path.join(res_dir, "logo.svg"))
        print("  -> res/ actualizado.")

    # 6. Parchear pubspec.yaml y Cargo.toml
    print("[5/6] Actualizando manifiestos del proyecto...")
    pubspec = os.path.join(repo_dir, "flutter", "pubspec.yaml")
    if os.path.exists(pubspec):
        with open(pubspec, "r", encoding="utf-8") as f:
            p = f.read()
        p = re.sub(r'name:\s*rustdesk', f'name: {app_name.lower()}', p)
        p = re.sub(r'description:\s*.*', f'description: {app_name} Remote Desktop Client', p)
        with open(pubspec, "w", encoding="utf-8") as f:
            f.write(p)
        print("  -> pubspec.yaml actualizado.")

    cargo_root = os.path.join(repo_dir, "Cargo.toml")
    if os.path.exists(cargo_root):
        with open(cargo_root, "r", encoding="utf-8") as f:
            cg = f.read()
        cg = re.sub(r'name\s*=\s*"rustdesk"', f'name = "{app_name.lower()}"', cg, count=1)
        with open(cargo_root, "w", encoding="utf-8") as f:
            f.write(cg)
        print("  -> Cargo.toml actualizado.")

    print(f"\n=========================================================")
    print(f"   ¡REBRANDING TOTAL A '{app_name}' COMPLETADO!")
    print(f"=========================================================\n")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python patch_branding.py <ruta_al_repo_clonado_de_rustdesk> [host] [pub_key]")
    else:
        repo = sys.argv[1]
        h = sys.argv[2] if len(sys.argv) > 2 else ""
        k = sys.argv[3] if len(sys.argv) > 3 else ""
        apply_full_rebrand(repo, assets_dir=os.path.abspath("../assets"), app_name="DxDesk", host=h, pub_key=k)
