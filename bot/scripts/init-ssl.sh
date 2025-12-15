#!/bin/bash

# Script para inicializar certificados SSL con Let's Encrypt
# Uso: ./init-ssl.sh tu-dominio.com tu-email@ejemplo.com

DOMAIN=$1
EMAIL=$2

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
    echo "Uso: ./init-ssl.sh <dominio> <email>"
    echo "Ejemplo: ./init-ssl.sh bot.pikasnacks.com admin@pikasnacks.com"
    exit 1
fi

# Detectar comando docker compose (nuevo) o docker-compose (legacy)
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    echo "Error: No se encontró docker-compose ni docker compose"
    exit 1
fi

echo "=== Inicializando SSL para $DOMAIN ==="
echo "Usando: $DOCKER_COMPOSE"

# Crear directorios necesarios
mkdir -p ./certbot/conf
mkdir -p ./certbot/www

# 1. Iniciar nginx con configuración básica (sin SSL)
echo "1. Iniciando Nginx en modo inicial..."
$DOCKER_COMPOSE -f docker-compose.bot.yml up -d nginx

# Esperar a que nginx esté listo
sleep 5

# 2. Obtener certificado con certbot
echo "2. Obteniendo certificado SSL..."
$DOCKER_COMPOSE -f docker-compose.bot.yml run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email $EMAIL \
    --agree-tos \
    --no-eff-email \
    --force-renewal \
    -d $DOMAIN

# 3. Crear enlace simbólico con nombre genérico
echo "3. Configurando certificados..."
$DOCKER_COMPOSE -f docker-compose.bot.yml exec nginx sh -c "
    mkdir -p /etc/letsencrypt/live/pika && \
    ln -sf /etc/letsencrypt/live/$DOMAIN/fullchain.pem /etc/letsencrypt/live/pika/fullchain.pem && \
    ln -sf /etc/letsencrypt/live/$DOMAIN/privkey.pem /etc/letsencrypt/live/pika/privkey.pem
"

# 4. Copiar configuración final de nginx
echo "4. Aplicando configuración SSL..."
$DOCKER_COMPOSE -f docker-compose.bot.yml cp bot/nginx/nginx.conf nginx:/etc/nginx/nginx.conf

# 5. Reiniciar nginx con SSL
echo "5. Reiniciando Nginx con SSL..."
$DOCKER_COMPOSE -f docker-compose.bot.yml restart nginx

echo ""
echo "=== SSL configurado correctamente ==="
echo "Tu webhook está disponible en: https://$DOMAIN/telegram/webhook"
echo ""
echo "Para registrar el webhook en Telegram, ejecuta:"
echo "curl -X POST \"https://api.telegram.org/bot\$TELEGRAM_BOT_TOKEN/setWebhook\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{\"url\": \"https://$DOMAIN/telegram/webhook\", \"secret_token\": \"\$TELEGRAM_SECRET_TOKEN\"}'"
