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

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOOLS_DIR = os.path.join(os.path.dirname(__file__), "tools")
OUTPUT_DIR = os.path.join(ROOT_DIR, "dist-all-platforms")
RCEDIT_PATH = os.path.join(TOOLS_DIR, "rcedit-x64.exe")
ICO_PATH = os.path.join(ROOT_DIR, "assets", "dxdesk.ico")

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

def build_all(host="2mail.us", key=""):
    ensure_tools()
    tag, assets = get_release_assets()
    print(f"\n=======================================================")
    print(f"  Preparando paquetes multiplataforma DxDesk v{tag}")
    print(f"  Servidor: {host}")
    print(f"=======================================================\n")

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
    h = sys.argv[1] if (len(sys.argv) > 1 and sys.argv[1].strip()) else "2mail.us"
    k = sys.argv[2] if (len(sys.argv) > 2 and sys.argv[2].strip()) else ""
    build_all(h, k)
