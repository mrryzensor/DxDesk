#!/usr/bin/env python3
"""
DxDesk - Empaquetador Multiplataforma
Descarga, personaliza y organiza los clientes oficiales para:
- Windows (Ejecutable portable .exe + Instalador .exe con icono)
- Android (APK Universal y ARM64 para teléfonos y tablets)
- Linux (Paquete Debian .deb y binario universal .AppImage)
- macOS (Imagen de disco .dmg para procesadores Apple Silicon M1-M4 e Intel)
- Generación de Código QR para vincular celulares en 1 segundo.
"""

import os
import sys
import json
import shutil
import urllib.request
import subprocess
import base64
import tempfile
import zipfile

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOOLS_DIR = os.path.join(os.path.dirname(__file__), "tools")
OUTPUT_DIR = os.path.join(ROOT_DIR, "dist-all-platforms")
RCEDIT_PATH = os.path.join(TOOLS_DIR, "rcedit-x64.exe")
ICO_PATH = os.path.join(ROOT_DIR, "assets", "dxdesk.ico")
ASSETS_DIR = os.path.join(ROOT_DIR, "assets")

def generate_svg_wrapper(png_path: str, svg_dest: str):
    with open(png_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="100%" height="100%">
  <image href="data:image/png;base64,{b64}" width="512" height="512"/>
</svg>'''
    with open(svg_dest, "w", encoding="utf-8") as f:
        f.write(svg_content)

def patch_and_sign_apk(apk_path):
    print(f"  Inyectando logo y marca de DxDesk en {os.path.basename(apk_path)}...")
    uber_jar = os.path.join(TOOLS_DIR, "uber-apk-signer.jar")
    if not os.path.exists(uber_jar):
        try:
            print("  Descargando uber-apk-signer...")
            url = "https://github.com/patrickfav/uber-apk-signer/releases/download/v1.3.0/uber-apk-signer-1.3.0.jar"
            urllib.request.urlretrieve(url, uber_jar)
        except Exception as e:
            print(f"  Aviso: no se pudo descargar uber-apk-signer: {e}")

    logo_square = os.path.join(ASSETS_DIR, "logo_square.png")
    temp_dir = tempfile.mkdtemp()
    unpacked_dir = os.path.join(temp_dir, "apk_contents")

    try:
        with zipfile.ZipFile(apk_path, 'r') as zf:
            zf.extractall(unpacked_dir)

        # 1. Reemplazar assets internos de Flutter (logo y SVG)
        flutter_assets = os.path.join(unpacked_dir, "assets", "flutter_assets", "assets")
        if os.path.exists(flutter_assets) and os.path.exists(logo_square):
            for name in ["logo.png", "logo_light.png", "logo_dark.png", "icon.png"]:
                dest = os.path.join(flutter_assets, name)
                if os.path.exists(dest):
                    shutil.copyfile(logo_square, dest)
            svg_dest = os.path.join(flutter_assets, "logo.svg")
            if os.path.exists(svg_dest):
                generate_svg_wrapper(logo_square, svg_dest)

        # 2. Reemplazar iconos mipmap del launcher
        mipmap_map = {
            "mipmap-mdpi": "icon_48x48.png",
            "mipmap-hdpi": "icon_64x64.png",
            "mipmap-xhdpi": "icon_128x128.png",
            "mipmap-xxhdpi": "icon_128x128.png",
            "mipmap-xxxhdpi": "icon_256x256.png",
        }
        res_dir = os.path.join(unpacked_dir, "res")
        if os.path.exists(res_dir):
            for mdir, icon_file in mipmap_map.items():
                target_icon = os.path.join(ASSETS_DIR, "icons", icon_file)
                if not os.path.exists(target_icon):
                    target_icon = logo_square
                for d in os.listdir(res_dir):
                    if mdir in d:
                        for target_name in ["ic_launcher.png", "ic_launcher_foreground.png"]:
                            fpath = os.path.join(res_dir, d, target_name)
                            if os.path.exists(fpath):
                                shutil.copyfile(target_icon, fpath)

        # 3. Eliminar firmas anteriores en META-INF
        meta_inf = os.path.join(unpacked_dir, "META-INF")
        if os.path.exists(meta_inf):
            for fname in os.listdir(meta_inf):
                if any(fname.endswith(ext) for ext in [".SF", ".RSA", ".DSA", ".EC", ".MF"]):
                    try:
                        os.remove(os.path.join(meta_inf, fname))
                    except Exception:
                        pass

        # 4. Volver a comprimir en zip
        unsigned_apk = os.path.join(temp_dir, "unsigned.apk")
        with zipfile.ZipFile(unsigned_apk, 'w', compression=zipfile.ZIP_DEFLATED) as zf_out:
            for root, dirs, files in os.walk(unpacked_dir):
                for file in files:
                    full_p = os.path.join(root, file)
                    rel_p = os.path.relpath(full_p, unpacked_dir)
                    zf_out.write(full_p, rel_p)

        # 5. Firmar con uber-apk-signer si está disponible
        if os.path.exists(uber_jar):
            cmd = ["java", "-jar", uber_jar, "-a", unsigned_apk, "--allowResign", "--overwrite", "-o", temp_dir]
            res = subprocess.run(cmd, capture_output=True, text=True)
            signed_apk = None
            for f in os.listdir(temp_dir):
                if f.endswith(".apk") and "signed" in f.lower():
                    signed_apk = os.path.join(temp_dir, f)
                    break
            if signed_apk and os.path.exists(signed_apk):
                shutil.copyfile(signed_apk, apk_path)
                print(f"  -> {os.path.basename(apk_path)} personalizado y firmado con el logo DxDesk con éxito.")
            else:
                shutil.copyfile(unsigned_apk, apk_path)
                print(f"  -> {os.path.basename(apk_path)} personalizado con el logo DxDesk.")
        else:
            shutil.copyfile(unsigned_apk, apk_path)
    except Exception as e:
        print(f"  Aviso al personalizar APK: {e}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def ensure_tools():
    os.makedirs(TOOLS_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if not os.path.exists(RCEDIT_PATH):
        print("Descargando herramienta rcedit...")
        url = "https://github.com/electron/rcedit/releases/download/v2.0.0/rcedit-x64.exe"
        urllib.request.urlretrieve(url, RCEDIT_PATH)

def get_release_assets():
    api_url = "https://api.github.com/repos/rustdesk/rustdesk/releases/latest"
    req = urllib.request.Request(api_url, headers={"User-Agent": "DxDesk-Multiplatform"})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            tag = data.get("tag_name", "1.4.9")
            return tag, data.get("assets", [])
    except Exception as e:
        print(f"Aviso al consultar GitHub API: {e}. Usando versión 1.4.9")
        return "1.4.9", []

def download_asset(url, dest_path):
    if os.path.exists(dest_path):
        print(f"  [Cache] {os.path.basename(dest_path)} ya existe.")
        return
    print(f"  Descargando {os.path.basename(dest_path)}...")
    urllib.request.urlretrieve(url, dest_path)

def generate_qr_code(config_str, dest_path):
    try:
        import qrcode
        qr = qrcode.QRCode(box_size=10, border=3)
        qr.add_data(config_str)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(dest_path)
        print(f"  -> Código QR para celulares generado en: {dest_path}")
    except ImportError:
        # Fallback usando API pública de QR
        encoded_url = urllib.parse.quote(config_str)
        api_qr = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={encoded_url}"
        try:
            urllib.request.urlretrieve(api_qr, dest_path)
            print(f"  -> Código QR descargado en: {dest_path}")
        except Exception as e:
            print(f"  Aviso: no se pudo generar QR ({e})")

def build_all(host="204.216.171.102", key=""):
    ensure_tools()
    tag, assets = get_release_assets()
    formatted_tag = tag if tag.startswith("v") else f"v{tag}"
    print(f"\n=======================================================")
    print(f"  Preparando paquetes multiplataforma DxDesk {formatted_tag}")
    print(f"  Servidor: {host}")
    print(f"=======================================================\n")

    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a", encoding="utf-8") as f:
            f.write(f"version={formatted_tag}\n")

    gh_env = os.environ.get("GITHUB_ENV")
    if gh_env:
        with open(gh_env, "a", encoding="utf-8") as f:
            f.write(f"DXDESK_VERSION={formatted_tag}\n")

    # Mapeo de archivos deseados
    targets = {
        "windows_exe": ("-x86_64.exe", "DxDesk-Windows-x64.exe"),
        "android_universal": ("universal-signed.apk", "DxDesk-Android-Universal.apk"),
        "android_arm64": ("aarch64-signed.apk", "DxDesk-Android-arm64.apk"),
        "linux_deb": ("-x86_64.deb", "DxDesk-Linux-x64.deb"),
        "linux_appimage": ("-x86_64.AppImage", "DxDesk-Linux-x64.AppImage"),
        "macos_arm": ("-aarch64.dmg", "DxDesk-macOS-AppleSilicon.dmg"),
        "macos_intel": ("-x86_64.dmg", "DxDesk-macOS-Intel.dmg"),
    }

    # 1. Descargar binarios correspondientes
    for asset in assets:
        name = asset.get("name", "")
        url = asset.get("browser_download_url", "")
        for key_t, (suffix, out_name) in targets.items():
            if name.endswith(suffix) and not "sciter" in name:
                cache_file = os.path.join(TOOLS_DIR, name)
                download_asset(url, cache_file)
                dest_file = os.path.join(OUTPUT_DIR, out_name)
                shutil.copyfile(cache_file, dest_file)
                
                # Si es Windows, inyectar icono y metadatos
                if out_name.endswith(".exe"):
                    print(f"  Inyectando icono y metadatos de DxDesk en {out_name}...")
                    cmd = [
                        RCEDIT_PATH, dest_file,
                        "--set-icon", ICO_PATH,
                        "--set-version-string", "ProductName", "DxDesk",
                        "--set-version-string", "FileDescription", "DxDesk Remote Desktop",
                        "--set-version-string", "CompanyName", "DxDesk"
                    ]
                    subprocess.run(cmd, capture_output=True)
                elif out_name.endswith(".apk"):
                    patch_and_sign_apk(dest_file)

    # 2. Generar archivos de configuración multiplataforma
    config_str = f"host={host},key={key},relay={host}"
    
    # TOML estándar de RustDesk
    toml_content = f"""# Configuración automática de DxDesk
custom-rendezvous-server = '{host}'
key = '{key}'
relay-server = '{host}'
api-server = ''
"""
    with open(os.path.join(OUTPUT_DIR, "RustDesk2.toml"), "w", encoding="utf-8") as f:
        f.write(toml_content)

    # Generar QR para la App móvil de Android
    generate_qr_code(config_str, os.path.join(OUTPUT_DIR, "DxDesk-Android-QR-Config.png"))

    # Script para Linux / Mac
    sh_script = f"""#!/usr/bin/env bash
# Configuración automática de DxDesk en Linux o macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    DIR="$HOME/Library/Application Support/RustDesk/config"
else
    DIR="$HOME/.config/rustdesk"
fi
mkdir -p "$DIR"
cat << 'EOF' > "$DIR/RustDesk2.toml"
{toml_content}
EOF
echo "DxDesk configurado exitosamente en $DIR/RustDesk2.toml"
"""
    with open(os.path.join(OUTPUT_DIR, "configure_linux_mac.sh"), "w", encoding="utf-8") as f:
        f.write(sh_script)

    # Script para Windows
    ps1_script = f"""# Configuración automática de DxDesk en Windows
$Dir = "$env:APPDATA\\RustDesk\\config"
if (!(Test-Path $Dir)) {{ New-Item -ItemType Directory -Path $Dir -Force | Out-Null }}
@'
{toml_content}
'@ | Set-Content -Path (Join-Path $Dir "RustDesk2.toml") -Encoding UTF8
Write-Host "DxDesk configurado exitosamente en Windows." -ForegroundColor Green
"""
    with open(os.path.join(OUTPUT_DIR, "configure_windows.ps1"), "w", encoding="utf-8") as f:
        f.write(ps1_script)

    # Guía de uso rápido
    readme = f"""=======================================================
           GUÍA DE CLIENTES MULTIPLATAFORMA DxDesk
=======================================================
Servidor: {host}
Clave Pública: {key}

1. WINDOWS:
   - Ejecuta 'DxDesk-Windows-x64.exe'.
   - O corre con PowerShell 'configure_windows.ps1' para dejarlo preconfigurado.

2. ANDROID:
   - Instala 'DxDesk-Android-Universal.apk' (o arm64).
   - Abre la app, ve a Ajustes > Red > Escanear QR.
   - Escanea la imagen 'DxDesk-Android-QR-Config.png' para que se conecte solo.
   - (O en Configuración copia la cadena: {config_str})

3. LINUX:
   - En Ubuntu/Debian: sudo dpkg -i DxDesk-Linux-x64.deb
   - O usa el portable: chmod +x DxDesk-Linux-x64.AppImage && ./DxDesk-Linux-x64.AppImage
   - Ejecuta: bash configure_linux_mac.sh

4. macOS:
   - Abre 'DxDesk-macOS-AppleSilicon.dmg' (M1/M2/M3/M4) o 'DxDesk-macOS-Intel.dmg'.
   - Arrastra a Aplicaciones y ejecuta 'bash configure_linux_mac.sh'.
=======================================================
"""
    with open(os.path.join(OUTPUT_DIR, "LEEME_INSTALACION.txt"), "w", encoding="utf-8") as f:
        f.write(readme)

    print("\n" + "="*55)
    print("   ¡PAQUETE MULTIPLATAFORMA GENERADO CON ÉXITO!   ")
    print("="*55)
    print(f"Carpeta: {OUTPUT_DIR}")
    for item in os.listdir(OUTPUT_DIR):
        size = os.path.getsize(os.path.join(OUTPUT_DIR, item)) / 1024 / 1024
        print(f" - {item} ({size:.2f} MB)")
    print("="*55 + "\n")

if __name__ == "__main__":
    h = sys.argv[1] if (len(sys.argv) > 1 and sys.argv[1].strip()) else "204.216.171.102"
    k = sys.argv[2] if (len(sys.argv) > 2 and sys.argv[2].strip()) else ""
    build_all(h, k)
