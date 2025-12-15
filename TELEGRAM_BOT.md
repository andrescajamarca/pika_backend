# Bot de Telegram para Pika Snacks

## Resumen Ejecutivo

Bot de Telegram que permite actualizar la base de datos de Pika Snacks mediante mensajes de texto natural. Utiliza OpenAI para interpretar los mensajes y generar las sentencias SQL correspondientes.

---

## Arquitectura

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Usuario      │     │    Telegram     │     │   Tu Servidor   │
│    (Móvil)      │     │    Servers      │     │   (SSH/Docker)  │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         │  "Registrar venta     │                       │
         │   a Juan, 2kg pollo"  │                       │
         │──────────────────────▶│                       │
         │                       │                       │
         │                       │  POST /webhook        │
         │                       │  + Secret Token       │
         │                       │  + IP Validation      │
         │                       │──────────────────────▶│
         │                       │                       │
         │                       │              ┌────────┴────────┐
         │                       │              │                 │
         │                       │              ▼                 │
         │                       │      ┌───────────────┐         │
         │                       │      │   OpenAI API  │         │
         │                       │      │  (GPT-4o-mini)│         │
         │                       │      └───────┬───────┘         │
         │                       │              │                 │
         │                       │              ▼                 │
         │                       │      ┌───────────────┐         │
         │                       │      │  PostgreSQL   │         │
         │                       │      │   (pika_db)   │         │
         │                       │      └───────────────┘         │
         │                       │                       │
         │                       │  "✅ Venta registrada"│
         │◀──────────────────────│◀──────────────────────│
```

---

## Estructura de Archivos

```
Pika_backend/
├── docker-compose.yml          # Solo PostgreSQL + red compartida
├── docker-compose.bot.yml      # Bot + Nginx + Certbot (independiente)
├── bot/
│   ├── __init__.py
│   ├── main.py                 # Entry point FastAPI
│   ├── config.py               # Configuración y variables de entorno
│   ├── security.py             # Validación de requests (IP + Secret Token)
│   ├── openai_handler.py       # Integración con OpenAI
│   ├── db.py                   # Conexión a PostgreSQL
│   ├── telegram_client.py      # Cliente para enviar mensajes
│   ├── Dockerfile              # Dockerfile del bot
│   ├── nginx/
│   │   ├── nginx.conf          # Configuración Nginx con SSL
│   │   └── nginx-init.conf     # Configuración inicial (sin SSL)
│   └── scripts/
│       └── init-ssl.sh         # Script para configurar SSL
├── certbot/                    # Certificados SSL (auto-generado)
│   ├── conf/                   # Configuración Let's Encrypt
│   └── www/                    # Challenge ACME
├── .env                        # Variables de entorno (NO commitear)
└── requirements.txt            # Dependencias actualizadas
```

---

## Paso a Paso de Implementación

### Paso 1: Crear el Bot en Telegram

1. Abrir Telegram y buscar `@BotFather`
2. Enviar `/newbot`
3. Seguir instrucciones (nombre y username)
4. **Guardar el TOKEN** que te da BotFather

```
Ejemplo: 7123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### Paso 2: Configurar Variables de Entorno

Actualizar el archivo `.env` en el servidor:

```bash
# Base de datos (ya existentes)
POSTGRES_USER=pika_user
POSTGRES_PASSWORD=pika_secret_2024
POSTGRES_DB=pika_db
POSTGRES_HOST=db
POSTGRES_PORT=5432

# OpenAI (ya existente)
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx

# Telegram Bot (NUEVAS)
TELEGRAM_BOT_TOKEN=7123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxx
TELEGRAM_SECRET_TOKEN=pika_webhook_secret_2024_muy_largo_y_seguro
TELEGRAM_ALLOWED_USERS=123456789,987654321

# Webhook
WEBHOOK_HOST=https://tu-dominio.com
WEBHOOK_PATH=/telegram/webhook
```

### Paso 3: Desplegar en el Servidor (vía SSH)

```bash
# 1. Conectar al servidor
ssh usuario@tu-servidor

# 2. Ir al directorio del proyecto
cd /ruta/a/Pika_backend

# 1. Levantar BD primero (crea la red)
docker-compose up -d
# 2. Levantar bot después (usa la red existente)
docker-compose -f docker-compose.bot.yml up -d --build
# Reiniciar solo el bot (BD no se toca)
docker-compose -f docker-compose.bot.yml restart
# Ver logs del bot
docker-compose -f docker-compose.bot.yml logs -f
```

### Paso 4: Registrar el Webhook

Ejecutar una sola vez después del deploy:

```bash
# Desde el servidor o localmente
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://tu-dominio.com/telegram/webhook",
    "secret_token": "pika_webhook_secret_2024_muy_largo_y_seguro",
    "allowed_updates": ["message"]
  }'
```

Verificar registro:
```bash
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

---

## Seguridad Implementada

### 1. Secret Token (Header)
Telegram envía `X-Telegram-Bot-Api-Secret-Token` en cada request.

### 2. Validación de IPs de Telegram
Solo se aceptan requests de:
- `149.154.160.0/20`
- `91.108.4.0/22`

### 3. Lista Blanca de Usuarios
Solo usuarios autorizados pueden ejecutar comandos (por `chat_id`).

### 4. Validación de SQL
- OpenAI genera SQL pero se valida antes de ejecutar
- Solo se permiten: `INSERT`, `UPDATE`, `SELECT`
- Prohibido: `DROP`, `DELETE`, `TRUNCATE`, `ALTER`

---

## Flujo de Procesamiento de Mensajes

```
1. Usuario envía: "Agregar cliente María, teléfono 3001234567"
                           │
                           ▼
2. Webhook recibe y valida seguridad
                           │
                           ▼
3. Se envía a OpenAI con contexto del esquema de BD:
   ┌─────────────────────────────────────────────────────┐
   │ PROMPT:                                             │
   │ Eres un asistente que genera SQL para PostgreSQL.  │
   │ Esquema disponible: clients, orders, products...   │
   │ Usuario dice: "Agregar cliente María, tel 300..."  │
   │ Genera SOLO el SQL, sin explicaciones.             │
   └─────────────────────────────────────────────────────┘
                           │
                           ▼
4. OpenAI responde:
   INSERT INTO clients (name, phone, source_client_id)
   VALUES ('María', '3001234567', 'telegram_maria_300');
                           │
                           ▼
5. Se valida el SQL (no contiene DROP, DELETE, etc.)
                           │
                           ▼
6. Se ejecuta en PostgreSQL
                           │
                           ▼
7. Se responde al usuario: "✅ Cliente María agregado"
```

---

## Comandos Disponibles

| Comando | Ejemplo | Descripción |
|---------|---------|-------------|
| Texto libre | "Agregar cliente Juan tel 300123" | OpenAI interpreta y ejecuta |
| `/ayuda` | `/ayuda` | Muestra comandos disponibles |
| `/resumen` | `/resumen` | Ventas del día |
| `/clientes` | `/clientes` | Lista últimos 10 clientes |
| `/cancelar` | `/cancelar` | Cancela operación pendiente |

---

## Ejemplos de Uso

### Agregar Cliente
```
Usuario: Nuevo cliente Pedro García, celular 3109876543, de Bogotá
Bot: ✅ Cliente agregado:
     - Nombre: Pedro García
     - Teléfono: 3109876543
```

### Registrar Venta
```
Usuario: Venta a Pedro García: 2kg pollo asado, 1kg chicharrón, total 85000
Bot: ✅ Pedido registrado:
     - Cliente: Pedro García
     - Items: 2kg pollo asado, 1kg chicharrón
     - Total: $85,000
```

### Actualizar Estado
```
Usuario: Marcar como entregado el pedido de Pedro
Bot: ✅ Pedido actualizado a "entregado"
```

### Consultar
```
Usuario: Cuánto ha comprado María este mes?
Bot: 📊 María ha realizado 3 pedidos por un total de $245,000
```

---

## Arquitectura Docker (Servicios Independientes)

Los servicios están separados en dos docker-compose independientes que se comunican via red Docker compartida.

### docker-compose.yml (Base de Datos)

```yaml
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    container_name: pika_db
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-pika_user}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-pika_secret_2024}
      POSTGRES_DB: ${POSTGRES_DB:-pika_db}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./db/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-pika_user} -d ${POSTGRES_DB:-pika_db}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - pika_network

networks:
  pika_network:
    name: pika_network
    driver: bridge

volumes:
  postgres_data:
```

### docker-compose.bot.yml (Bot de Telegram)

```yaml
version: '3.8'

services:
  bot:
    build:
      context: .
      dockerfile: bot/Dockerfile
    container_name: pika_telegram_bot
    restart: unless-stopped
    environment:
      - POSTGRES_USER=${POSTGRES_USER:-pika_user}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-pika_secret_2024}
      - POSTGRES_DB=${POSTGRES_DB:-pika_db}
      - POSTGRES_HOST=${POSTGRES_HOST:-pika_db}
      - POSTGRES_PORT=${POSTGRES_PORT:-5432}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - TELEGRAM_SECRET_TOKEN=${TELEGRAM_SECRET_TOKEN}
      - TELEGRAM_ALLOWED_USERS=${TELEGRAM_ALLOWED_USERS}
    ports:
      - "8080:8080"
    networks:
      - pika_network

networks:
  pika_network:
    external: true
    name: pika_network
```

### Comandos de Despliegue

```bash
# 1. Primero levantar la BD (crea la red pika_network)
docker-compose up -d

# 2. Luego levantar el bot (usa la red existente)
docker-compose -f docker-compose.bot.yml up -d --build

# Ver logs de cada servicio
docker-compose logs -f db
docker-compose -f docker-compose.bot.yml logs -f bot

# Reiniciar solo el bot (sin afectar la BD)
docker-compose -f docker-compose.bot.yml restart

# Detener solo el bot
docker-compose -f docker-compose.bot.yml down

# Detener todo
docker-compose -f docker-compose.bot.yml down
docker-compose down
```

---

## Configuración SSL (HTTPS)

El SSL está integrado en el docker-compose del bot usando Nginx + Let's Encrypt.

### Arquitectura

```
Internet (HTTPS:443)
        │
        ▼
┌───────────────┐
│     Nginx     │ ← SSL termination
│   (puerto 443)│
└───────┬───────┘
        │ HTTP interno
        ▼
┌───────────────┐
│      Bot      │
│  (puerto 8080)│
└───────────────┘
```

### Paso 1: Configurar DNS

Apuntar tu dominio al servidor:
```
bot.tudominio.com  →  IP_DEL_SERVIDOR
```

### Paso 2: Inicializar SSL

```bash
# En el servidor, ir al directorio del proyecto
cd /ruta/a/Pika_backend

# Dar permisos al script
chmod +x bot/scripts/init-ssl.sh

# Ejecutar (reemplazar con tu dominio y email)
./bot/scripts/init-ssl.sh bot.tudominio.com tu-email@ejemplo.com
```

El script automáticamente:
1. Inicia Nginx en modo HTTP
2. Obtiene certificado de Let's Encrypt
3. Configura Nginx con SSL
4. Reinicia con HTTPS habilitado

### Paso 3: Verificar

```bash
# Verificar que HTTPS funciona
curl https://bot.tudominio.com/health

# Debería responder: {"status": "ok", "service": "pika-telegram-bot"}
```

### Renovación Automática

El contenedor `certbot` renueva automáticamente los certificados cada 12 horas (si están próximos a expirar).

### Alternativa: Ngrok (Desarrollo/Pruebas)

```bash
# Sin SSL propio, usar ngrok
ngrok http 8080

# Usar la URL generada: https://abc123.ngrok.io/telegram/webhook
```

---

## Checklist de Despliegue

- [ ] Crear bot con @BotFather y obtener TOKEN
- [ ] Configurar `.env` con todas las variables
- [ ] Subir código al servidor (git push)
- [ ] Levantar BD: `docker-compose up -d`
- [ ] Levantar bot: `docker-compose -f docker-compose.bot.yml up -d --build`
- [ ] Configurar DNS (dominio → IP servidor)
- [ ] Ejecutar script SSL: `./bot/scripts/init-ssl.sh dominio email`
- [ ] Verificar HTTPS: `curl https://dominio/health`
- [ ] Registrar webhook con Telegram API
- [ ] Verificar webhook: `getWebhookInfo`
- [ ] Probar enviando mensaje al bot
- [ ] Agregar usuarios autorizados a `TELEGRAM_ALLOWED_USERS`

---

## Troubleshooting

### El bot no responde
```bash
# Verificar logs
docker-compose logs -f bot

# Verificar webhook
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

### Error de conexión a BD
```bash
# Verificar que PostgreSQL está corriendo
docker-compose ps
docker-compose logs db
```

### Error 403 en webhook
- Verificar `TELEGRAM_SECRET_TOKEN` coincide
- Verificar que el request viene de IPs de Telegram

---

## Costos Estimados

| Servicio | Costo |
|----------|-------|
| Telegram Bot API | **Gratis** |
| OpenAI GPT-4o-mini | ~$0.15 / 1M tokens input |
| Servidor (ya tienes) | $0 adicional |

**Estimado mensual**: $1-5 USD dependiendo del uso

---

## Próximos Pasos

1. **Ejecutar**: Crear los archivos del bot en `bot/`
2. **Configurar**: Variables de entorno en servidor
3. **Desplegar**: `docker-compose up -d --build`
4. **Probar**: Enviar mensaje al bot
