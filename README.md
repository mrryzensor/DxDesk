# DxDesk - Tu Servidor Propio y Cliente Personalizado de RustDesk

Sistema completo de escritorio remoto de alto rendimiento, 100% privado y optimizado para desplegar en tu **Oracle Cloud VPS (Ampere A1 ARM64 / AMD64 con Ubuntu)** junto con el empaquetado de clientes con la marca e icono de **DxDesk**.

---

## Estructura del Proyecto

```
DxDesk/
├── logo.png                       # Logo original del proyecto
├── generate_assets.py             # Generador de iconos (.ico multi-resolución y PNGs)
├── assets/
│   ├── dxdesk.ico                 # Icono Windows multi-capa (16x16 hasta 256x256)
│   ├── logo_square.png            # Logo maestro cuadrado y transparente
│   └── icons/                     # Iconos PNG en resoluciones 16 a 512px
├── server/                        # Despliegue en Oracle Cloud VPS
│   ├── docker-compose.yml         # Configuración hbbs y hbbr (modo red host, nativo ARM64)
│   ├── deploy.sh                  # Script de instalación 1-clic con fix de firewall iptables
│   ├── .env.example               # Variables de entorno (IP / Dominio)
│   └── ORACLE_FIREWALL_GUIDE.md   # Guía paso a paso para abrir puertos en Oracle Console
├── client-packager/               # Generador del ejecutable Windows con tu marca
│   ├── build_client.py            # Descarga el core, inyecta dxdesk.ico y metadatos PE
│   ├── config_encoder.py          # Codificador de configuración y generador de RustDesk2.toml
│   ├── inno_setup_dxdesk.iss      # Script para compilar el instalador DxDesk-Setup.exe
│   └── tools/                     # Utilidades PE (rcedit-x64)
├── dist/
│   └── DxDesk.exe                 # Ejecutable listo para Windows con tu logo y marca
└── source-build/                  # Para compilación 100% nativa desde código fuente
    ├── patch_branding.py          # Script de reemplazo automático de marca en el repo
    └── .github/workflows/         # Workflow de GitHub Actions (Windows, Android, Linux)
```

---

## 🚀 Paso 1: Desplegar en tu Oracle Cloud VPS (Ubuntu Ampere ARM64)

### 1.1. Abrir los puertos en la consola web de Oracle Cloud
En Oracle Cloud existe un firewall a nivel hipervisor (VCN Security Lists). Antes de iniciar el servidor, debes abrir los puertos:
1. Ve a **Networking** > **Virtual Cloud Networks (VCN)** en [Oracle Cloud Console](https://cloud.oracle.com).
2. Entra en tu **VCN** > **Security Lists** > **Default Security List**.
3. Añade las siguientes **Ingress Rules** (Reglas de Entrada):
   - **TCP**: `21115-21119` (Origen: `0.0.0.0/0`)
   - **UDP**: `21116` (Origen: `0.0.0.0/0`)

*(Consulta [server/ORACLE_FIREWALL_GUIDE.md](file:///e:/CrearApps/DxDesk/server/ORACLE_FIREWALL_GUIDE.md) para ver la guía ilustrada).*

### 1.2. Ejecutar la instalación en el servidor
Copia la carpeta `server/` a tu VPS (por ejemplo vía SCP, Git o SFTP) y ejecuta:

```bash
cd server
chmod +x deploy.sh
./deploy.sh
```

El script se encargará automáticamente de:
- Instalar **Docker** y **Docker Compose** nativo para ARM64.
- **Corregir el bloqueo de iptables propio de Ubuntu en Oracle Cloud** (que normalmente descarta el tráfico en puertos no estándar).
- Levantar `hbbs` y `hbbr`.
- Extraer tu **Clave Pública de Cifrado (`id_ed25519.pub`)** y mostrarte la cadena de configuración.

Guarda los dos datos que imprimirá en pantalla:
1. **Tu IP pública** (ej: `129.151.x.x` o tu dominio).
2. **Tu clave pública** (ej: `rU7+x5...`).

---

## 💻 Paso 2: Generar y Preconfigurar el Cliente DxDesk

Ya hemos generado tu ejecutable base con el icono de tu logo en:
👉 `dist/DxDesk.exe`

### 2.1. Conectar el cliente a tu servidor
Para que tus clientes no tengan que escribir IPs ni claves manualmente, tienes 2 opciones sencillas:

#### Opción A: Generar archivo de configuración rápida (Recomendado)
En tu computadora ejecuta:
```bash
python client-packager/config_encoder.py <TU_IP_ORACLE> <TU_CLAVE_PUBLICA>
```
Esto creará en `client-packager/output/`:
1. `RustDesk2.toml`: Archivo de configuración listo.
2. `configure_client.ps1`: Script PowerShell de un clic para preconfigurar cualquier máquina cliente.
3. La cadena codificada `--config`: Para lanzar `DxDesk.exe --config <CADENA>` o usarla en despliegues desatendidos.

#### Opción B: Crear un instalador formal (DxDesk-Setup.exe)
Si tienes instalado [Inno Setup](https://jrsoftware.org/isdl.php), abre el archivo `client-packager/inno_setup_dxdesk.iss` y haz clic en **Compile**. Creará un instalador que copia `DxDesk.exe`, crea el icono en el Escritorio con tu logo e instala silenciosamente la configuración en `%APPDATA%\RustDesk\config\RustDesk2.toml`.

---

## 🛠️ Paso 3: Regenerar Iconos o Reconstruir el Cliente

Si en algún momento actualizas `logo.png`:
1. **Regenerar iconos:**
   ```bash
   python generate_assets.py
   ```
2. **Reconstruir el binario de Windows:**
   ```bash
   python client-packager/build_client.py
   ```

---

## 🔒 Seguridad y Privacidad

- **Cifrado Punto a Punto (E2E):** Todo el tráfico remoto (pantalla, ratón, teclado, archivos) está cifrado usando Ed25519 y ChaCha20-Poly1305.
- **Acceso Exclusivo:** El servidor arranca con el parámetro `-k _`, lo que significa que **ninguna persona u otro cliente RustDesk público podrá usar tu servidor** a menos que posea tu clave pública.
