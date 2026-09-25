#!/usr/bin/env bash
# ==============================================================================
# DxDesk Server - Script de Despliegue Automatizado para Oracle Cloud (Ubuntu ARM64/AMD64)
# ==============================================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=====================================================${NC}"
echo -e "${GREEN}    Iniciando instalación y despliegue de DxDesk Server    ${NC}"
echo -e "${BLUE}=====================================================${NC}"

# 1. Detectar IP pública
DETECTED_IP=$(curl -s -4 https://ifconfig.me || curl -s https://api.ipify.org || echo "")

if [ -f .env ]; then
    source .env
fi

if [ -z "$RELAY_HOST" ] || [ "$RELAY_HOST" == "127.0.0.1" ]; then
    if [ -n "$DETECTED_IP" ]; then
        echo -e "${YELLOW}Detectada IP pública: ${DETECTED_IP}${NC}"
        RELAY_HOST="$DETECTED_IP"
    else
        read -p "Ingresa la IP pública o Dominio de este servidor: " RELAY_HOST
    fi
    echo "RELAY_HOST=$RELAY_HOST" > .env
else
    echo -e "${GREEN}Usando RELAY_HOST configurado: ${RELAY_HOST}${NC}"
fi

# 2. Actualizar paquetes e instalar dependencias básicas
echo -e "\n${BLUE}[1/5] Actualizando paquetes del sistema...${NC}"
sudo apt-get update -y
sudo apt-get install -y curl git ufw iptables-persistent netfilter-persistent

# 3. Instalar Docker y Docker Compose si no están instalados
echo -e "\n${BLUE}[2/5] Verificando instalación de Docker...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}Docker no encontrado. Instalando Docker oficial...${NC}"
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker "$USER"
    rm get-docker.sh
    echo -e "${GREEN}Docker instalado exitosamente.${NC}"
else
    echo -e "${GREEN}Docker ya está instalado.${NC}"
fi

# 4. Solucionar el Firewall interno de Oracle Cloud Ubuntu (iptables)
echo -e "\n${BLUE}[3/5] Configurando reglas de Firewall interno de Ubuntu/Oracle...${NC}"
# Oracle Cloud Ubuntu por defecto rechaza tráfico en iptables antes de que Docker o UFW lo procesen.
sudo iptables -I INPUT 6 -p tcp -m multiport --dports 21115,21116,21117,21118,21119 -j ACCEPT || true
sudo iptables -I INPUT 6 -p udp --dport 21116 -j ACCEPT || true

if command -v ufw &> /dev/null; then
    sudo ufw allow 21115:21119/tcp || true
    sudo ufw allow 21116/udp || true
fi

# Guardar reglas persistentes
sudo netfilter-persistent save || true
echo -e "${GREEN}Reglas de firewall interno aplicadas.${NC}"

# 5. Crear directorio de datos y levantar contenedores
echo -e "\n${BLUE}[4/5] Levantando servicios con Docker Compose...${NC}"
mkdir -p data

if docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
else
    echo -e "${RED}Error: docker compose no está disponible.${NC}"
    exit 1
fi

$DOCKER_COMPOSE_CMD down || true
$DOCKER_COMPOSE_CMD up -d

# 6. Esperar a que se genere la clave pública
echo -e "\n${BLUE}[5/5] Obteniendo clave pública de cifrado...${NC}"
KEY_PATH="./data/id_ed25519.pub"
RETRIES=15
while [ ! -f "$KEY_PATH" ] && [ $RETRIES -gt 0 ]; do
    sleep 1
    RETRIES=$((RETRIES - 1))
done

if [ -f "$KEY_PATH" ]; then
    PUB_KEY=$(cat "$KEY_PATH")
    echo -e "\n${GREEN}=====================================================${NC}"
    echo -e "${GREEN}       ¡DxDesk Server levantado con éxito!          ${NC}"
    echo -e "${GREEN}=====================================================${NC}"
    echo -e "Host / Servidor ID & Relay: ${YELLOW}${RELAY_HOST}${NC}"
    echo -e "Clave Pública (Key):       ${YELLOW}${PUB_KEY}${NC}"
    echo -e "-----------------------------------------------------"
    echo -e "Cadena de configuración para clientes DxDesk:"
    echo -e "${YELLOW}host=${RELAY_HOST},key=${PUB_KEY}${NC}"
    echo -e "=====================================================\n"
    echo -e "${RED}IMPORTANTE (Oracle Cloud):${NC}"
    echo -e "Asegúrate de haber abierto los siguientes puertos en las"
    echo -e "Reglas de Entrada (Ingress Rules) de tu VCN en Oracle Console:"
    echo -e "  - TCP: 21115, 21116, 21117, 21118, 21119"
    echo -e "  - UDP: 21116"
else
    echo -e "${YELLOW}Los contenedores están iniciando, pero la clave aún se está generando.${NC}"
    echo -e "Puedes ver tu clave en unos segundos con: ${GREEN}cat ./data/id_ed25519.pub${NC}"
fi
