# DxDesk - Tu Servidor Propio y Cliente Personalizado de RustDesk

Sistema completo de escritorio remoto de alto rendimiento, 100% privado y optimizado para desplegar en tu **Oracle Cloud VPS (Ampere A1 ARM64 / AMD64 con Ubuntu)** junto con el empaquetado de clientes con la marca e icono de **DxDesk**.

## Landing page

La landing está en `docs/` y muestra descargas directas de la release estable más reciente disponible para cada sistema operativo. Detecta la plataforma del visitante y la pone primero. Los assets y sus versiones se consultan en GitHub Releases, así que la página no necesita actualizarse al publicar una nueva versión.

Para verla localmente, desde la raíz del repositorio ejecuta:

```bash
python -m http.server 8000 --directory docs
```

Después abre `http://localhost:8000`. Para publicarla con GitHub Pages, selecciona **Settings > Pages > Deploy from a branch**, la rama `main` y la carpeta `/docs`.

---

## Estructura del Proyecto

```
DxDesk/
├── logo.png                       # Logo original del proyecto
├── generate_assets.py             # Generador de iconos (.ico multi-resolución y PNGs)
├── branding.json                  # Nombre, servidor y rama upstream
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
├── source-build/                  # Utilidades de compilación desde código fuente
├── scripts/sync_rustdesk.py       # Sincroniza la última release numerada y reaplica la marca
└── .github/workflows/              # Sincronización y builds nativos por plataforma
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

## 🔄 Actualización automática desde RustDesk

El workflow **Sync RustDesk upstream** consulta diariamente la última release
numerada de `rustdesk/rustdesk` (omite `nightly`). Sólo cuando aparece un tag de
versión nuevo,
reemplaza la copia de `client/`, reaplica `branding.json` y sube un commit a
`main`; entonces inicia las compilaciones de fuente de Windows, Android, Linux y
macOS. Los commits diarios de `master` no disparan compilaciones.

`client/` se considera una copia vendorizada generada: cualquier cambio manual
que no forme parte de la configuración de marca se sobrescribirá en la siguiente
sincronización.

La marca se aplica dentro de la interfaz Flutter, recursos nativos de cada
plataforma, metadatos, iconos, instaladores y servidor predeterminado. Los
nombres internos de protocolo, paquetes, binarios compatibles y esquemas
`rustdesk://` se conservan únicamente donde son necesarios para mantener la
compatibilidad.

También se puede ejecutar manualmente desde **Actions > Sync RustDesk upstream**.

El workflow de compilación desde fuente genera para Windows:

- `DxDesk-Windows-x64.exe`: ejecutable portable de un solo archivo.
- `DxDesk-Windows-Setup.exe`: instalador de Inno Setup.
- `DxDesk-Windows-x64-Source.zip`: bundle con DLL y assets, útil para diagnóstico.

GitHub siempre descarga los artefactos de `actions/upload-artifact` como un ZIP,
aunque dentro haya un `.exe`. Para descargar archivos individuales hay que abrir
la sección **Releases** y usar los assets publicados allí.

El workflow `Build DxDesk Other Platforms From Source` compila desde la release
numerada sincronizada:

- Android: APK universal y APK ARM64 con nombre, logo y etiqueta personalizados.
- Linux: paquete `.deb` y AppImage con interfaz, iconos y archivos `.desktop` personalizados.
- macOS: DMG Intel y Apple Silicon con `DxDesk.app`, `PRODUCT_NAME` e icono personalizados.

Estos paquetes se publican individualmente en una release `source-*`. Windows se
publica individualmente en la release `RustDesk main` del workflow de Windows.

---

## 🔒 Seguridad y Privacidad

- **Cifrado Punto a Punto (E2E):** Todo el tráfico remoto (pantalla, ratón, teclado, archivos) está cifrado usando Ed25519 y ChaCha20-Poly1305.
- **Acceso Exclusivo:** El servidor arranca con el parámetro `-k _`, lo que significa que **ninguna persona u otro cliente RustDesk público podrá usar tu servidor** a menos que posea tu clave pública.
