"""
DxDesk - Generador y Codificador de Configuración para Clientes
Permite generar la cadena de configuración oficial de RustDesk, 
el archivo RustDesk2.toml y scripts de aprovisionamiento automatizado.
"""

import base64
import os
import sys

def encode_rustdesk_config(host: str, key: str, relay: str = None) -> tuple[str, str]:
    """
    Codifica los parámetros según el estándar de RustDesk:
    Cadena original -> inversión de caracteres -> Base64 URL Safe sin relleno.
    """
    if not relay:
        relay = host
    raw_str = f"host={host},key={key},relay={relay}"
    reversed_str = raw_str[::-1]
    encoded = base64.urlsafe_b64encode(reversed_str.encode("utf-8")).decode("utf-8").rstrip("=")
    return encoded, raw_str

def decode_rustdesk_config(encoded: str) -> str:
    """Decodifica una cadena de configuración existente de RustDesk."""
    pad = len(encoded) % 4
    if pad != 0:
        encoded += "=" * (4 - pad)
    decoded_reversed = base64.urlsafe_b64decode(encoded.encode("utf-8")).decode("utf-8")
    return decoded_reversed[::-1]

def generate_toml_content(host: str, key: str, relay: str = None) -> str:
    """Genera el contenido del archivo RustDesk2.toml para preconfigurar el cliente."""
    if not relay:
        relay = host
    toml = f"""# Configuración de DxDesk Cliente
custom-rendezvous-server = '{host}'
key = '{key}'
relay-server = '{relay}'
api-server = ''
"""
    return toml

def create_config_files(host: str, key: str, output_dir: str = "."):
    encoded, raw = encode_rustdesk_config(host, key)
    toml_content = generate_toml_content(host, key)
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Guardar archivo TOML
    toml_path = os.path.join(output_dir, "RustDesk2.toml")
    with open(toml_path, "w", encoding="utf-8") as f:
        f.write(toml_content)
        
    # 2. Guardar script de configuración rápida para Windows (PowerShell)
    ps1_content = f"""# Script de configuración automática de DxDesk
$ConfigDir = "$env:APPDATA\\RustDesk\\config"
if (!(Test-Path $ConfigDir)) {{
    New-Item -ItemType Directory -Path $ConfigDir -Force | Out-Null
}}

$TomlContent = @'
{toml_content}
'@

$TomlPath = Join-Path $ConfigDir "RustDesk2.toml"
Set-Content -Path $TomlPath -Value $TomlContent -Encoding UTF8
Write-Host "DxDesk preconfigurado con éxito en: $TomlPath" -ForegroundColor Green
"""
    ps1_path = os.path.join(output_dir, "configure_client.ps1")
    with open(ps1_path, "w", encoding="utf-8") as f:
        f.write(ps1_content)

    print("\n" + "="*50)
    print("      CONFIGURACIÓN GENERADA PARA DxDesk")
    print("="*50)
    print(f"Host / Servidor:   {host}")
    print(f"Clave Pública:     {key}")
    print(f"Cadena codificada: {encoded}")
    print(f"Comando manual:    DxDesk.exe --config {encoded}")
    print(f"Archivos creados:")
    print(f"  -> {toml_path}")
    print(f"  -> {ps1_path}")
    print("="*50 + "\n")
    return encoded

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        host = sys.argv[1]
        key = sys.argv[2]
        create_config_files(host, key, output_dir="client-packager/output")
    else:
        print("Uso interactivo:")
        h = input("Ingresa la IP o Dominio de tu servidor Oracle: ").strip()
        k = input("Ingresa la clave pública (id_ed25519.pub): ").strip()
        if h and k:
            create_config_files(h, k, output_dir="client-packager/output")
        else:
            print("Datos incompletos. Cancelando.")
