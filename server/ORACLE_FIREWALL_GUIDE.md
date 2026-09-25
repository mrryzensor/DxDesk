# Guía de Configuración de Firewall en Oracle Cloud Console

Para que tu servidor DxDesk pueda recibir conexiones desde cualquier parte del mundo, debes abrir los puertos en el panel web de Oracle Cloud (Security List / Network Security Group), además del firewall interno de Linux.

---

### Paso a Paso en Oracle Cloud Console

1. Inicia sesión en tu cuenta de **Oracle Cloud**.
2. Ve al menú hamburguesa (arriba a la izquierda) y navega a:
   **Networking (Redes)** > **Virtual Cloud Networks (Redes virtuales en la nube - VCN)**.
3. Haz clic en la **VCN** asociada a tu instancia Ubuntu Ampere.
4. En el menú lateral izquierdo de Recursos, haz clic en **Security Lists (Listas de seguridad)**.
5. Haz clic en la lista de seguridad predeterminada (generalmente llamada **Default Security List for...**).
6. Haz clic en el botón azul **Add Ingress Rules (Agregar reglas de entrada)**.

---

### Regla 1: Tráfico TCP (Señalización, Relay y Web)
* **Stateless (Sin estado):** Desmarcado (No).
* **Source Type (Tipo de origen):** CIDR.
* **Source CIDR (CIDR de origen):** `0.0.0.0/0`
* **IP Protocol (Protocolo IP):** `TCP`
* **Source Port Range:** Dejar en blanco (All).
* **Destination Port Range (Rango de puertos de destino):** `21115-21119`
* **Description:** `DxDesk TCP Ports (hbbs, hbbr, web)`

---

### Regla 2: Tráfico UDP (Registro, latencia y Hole Punching P2P)
* **Stateless (Sin estado):** Desmarcado (No).
* **Source Type (Tipo de origen):** CIDR.
* **Source CIDR (CIDR de origen):** `0.0.0.0/0`
* **IP Protocol (Protocolo IP):** `UDP`
* **Source Port Range:** Dejar en blanco (All).
* **Destination Port Range (Rango de puertos de destino):** `21116`
* **Description:** `DxDesk UDP Hole Punching (hbbs)`

---

### Resumen de Puertos y sus Funciones

| Puerto | Protocolo | Servicio | Descripción |
| :--- | :--- | :--- | :--- |
| **21115** | TCP | `hbbs` | Prueba de tipo NAT |
| **21116** | TCP | `hbbs` | Conexión TCP y servicio de punch hole |
| **21116** | UDP | `hbbs` | Registro de clientes, latencia y señalización |
| **21117** | TCP | `hbbr` | Servicio de retransmisión / Relay (cuando falla P2P) |
| **21118** | TCP | `hbbs` | Cliente Web WebSocket (opcional) |
| **21119** | TCP | `hbbr` | Cliente Web Relay WebSocket (opcional) |
