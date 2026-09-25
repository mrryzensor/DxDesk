#!/usr/bin/env python3
"""
DxDesk - Creador de Ejecutable Personalizado para Windows
Descarga el cliente base oficial, reemplaza los recursos (icono de DxDesk,
metadatos de versión y descripción) y prepara el paquete listo para distribuir.
"""

import os
import sys
import json
import shutil
import subprocess
import urllib.request

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOOLS_DIR = os.path.join(os.path.dirname(__file__), "tools")
OUTPUT_DIR = os.path.join(ROOT_DIR, "dist")
RCEDIT_PATH = os.path.join(TOOLS_DIR, "rcedit-x64.exe")
ICO_PATH = os.path.join(ROOT_DIR, "assets", "dxdesk.ico")

def ensure_tools():
    """Verifica y descarga rcedit si no existe."""
    os.makedirs(TOOLS_DIR, exist_ok=True)
    if not os.path.exists(RCEDIT_PATH):
        print("Descargando herramienta de recursos PE (rcedit)...")
        url = "https://github.com/electron/rcedit/releases/download/v2.0.0/rcedit-x64.exe"
        urllib.request.urlretrieve(url, RCEDIT_PATH)
        print("rcedit listo.")

    if not os.path.exists(ICO_PATH):
        print("Generando iconos desde logo.png...")
        from generate_assets import generate_all_assets
        generate_all_assets(os.path.join(ROOT_DIR, "logo.png"))

def get_latest_rustdesk_windows():
    """Obtiene la URL del último release oficial de RustDesk para Windows x86_64."""
    api_url = "https://api.github.com/repos/rustdesk/rustdesk/releases/latest"
    req = urllib.request.Request(api_url, headers={"User-Agent": "DxDesk-Builder"})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            tag = data.get("tag_name", "1.4.9")
            for asset in data.get("assets", []):
                name = asset.get("name", "")
                if name.endswith("-x86_64.exe"):
                    return tag, asset.get("browser_download_url"), name
    except Exception as e:
        print(f"Aviso al consultar API de GitHub ({e}). Usando versión por defecto 1.4.9...")
        tag = "1.4.9"
        url = f"https://github.com/rustdesk/rustdesk/releases/download/{tag}/rustdesk-{tag}-x86_64.exe"
        return tag, url, f"rustdesk-{tag}-x86_64.exe"

def download_file(url, target_path):
    print(f"Descargando binario base desde:\n  {url}")
    print(f"Guardando en: {target_path} ...")
    
    def report(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            percent = downloaded * 100 / total_size
            sys.stdout.write(f"\r  Progreso: {percent:.1f}% ({downloaded / 1024 / 1024:.1f} MB de {total_size / 1024 / 1024:.1f} MB)")
            sys.stdout.flush()

    urllib.request.urlretrieve(url, target_path, reporthook=report)
    print("\nDescarga completada con éxito.")

def patch_executable(exe_path, app_name="DxDesk"):
    """Inyecta el icono de DxDesk y personaliza los metadatos del ejecutable."""
    print("\nModificando ejecutable con la identidad de DxDesk...")
    
    commands = [
        RCEDIT_PATH,
        exe_path,
        "--set-icon", ICO_PATH,
        "--set-version-string", "ProductName", app_name,
        "--set-version-string", "FileDescription", f"{app_name} - Escritorio Remoto Seguro",
        "--set-version-string", "CompanyName", app_name,
        "--set-version-string", "LegalCopyright", f"Copyright (C) 2026 {app_name}",
        "--set-version-string", "InternalName", f"{app_name}.exe",
        "--set-version-string", "OriginalFilename", f"{app_name}.exe"
    ]
    
    res = subprocess.run(commands, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Aviso en rcedit: {res.stderr}")
    else:
        print(f"¡Icono y metadatos inyectados con éxito en {exe_path}!")

def main():
    ensure_tools()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    tag, url, original_name = get_latest_rustdesk_windows()
    cache_path = os.path.join(TOOLS_DIR, original_name)
    
    if not os.path.exists(cache_path):
        download_file(url, cache_path)
    else:
        print(f"Usando binario base cacheado: {cache_path}")
        
    final_exe = os.path.join(OUTPUT_DIR, "DxDesk.exe")
    shutil.copyfile(cache_path, final_exe)
    
    patch_executable(final_exe, app_name="DxDesk")
    
    print("\n" + "="*50)
    print(f"   ¡EJECUTABLE DxDesk GENERADO CON ÉXITO!   ")
    print("="*50)
    print(f"Ruta: {final_exe}")
    print(f"Tamaño: {os.path.getsize(final_exe) / 1024 / 1024:.2f} MB")
    print(f"Icono: {ICO_PATH}")
    print("="*50 + "\n")

if __name__ == "__main__":
    main()
