import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Header, HTTPException
from typing import Optional

from .config import config
from .db import db
from .security import require_telegram_auth, is_user_allowed
from .telegram_client import telegram
from .openai_handler import process_message

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Conectando a la base de datos...")
    await db.connect()
    logger.info("Bot iniciado correctamente")
    yield
    logger.info("Cerrando conexiones...")
    await db.disconnect()


app = FastAPI(
    title="Pika Telegram Bot",
    description="Bot de Telegram para gestionar Pika Snacks",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health_check():
    """Endpoint de salud para verificar que el servicio está corriendo."""
    return {"status": "ok", "service": "pika-telegram-bot"}


@app.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(None)
):
    """
    Webhook principal para recibir mensajes de Telegram.
    Valida seguridad y procesa mensajes.
    """
    require_telegram_auth(
        request,
        x_telegram_bot_api_secret_token,
        skip_ip_check=config.TELEGRAM_SECRET_TOKEN != ""
    )
    
    try:
        update = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    message = update.get("message")
    if not message:
        return {"ok": True}
    
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")
    message_id = message.get("message_id")
    user = message.get("from", {})
    
    if not chat_id or not text:
        return {"ok": True}
    
    logger.info(f"Mensaje de {user.get('first_name', 'Unknown')} ({chat_id}): {text[:50]}...")
    
    if not is_user_allowed(chat_id):
        await telegram.send_message(
            chat_id,
            "⛔ No tienes permiso para usar este bot.\n"
            f"Tu ID es: <code>{chat_id}</code>\n"
            "Contacta al administrador para solicitar acceso.",
            reply_to_message_id=message_id
        )
        return {"ok": True}
    
    if text == "/start":
        await telegram.send_message(
            chat_id,
            "🐷 <b>¡Bienvenido a Pika Snacks Bot!</b>\n\n"
            "Puedo ayudarte a gestionar:\n"
            "• 👤 Clientes\n"
            "• 📦 Pedidos\n"
            "• 📊 Consultas\n\n"
            "Escribe en lenguaje natural lo que necesitas.\n"
            "Ejemplo: <i>\"Agregar cliente Juan, tel 3001234567\"</i>",
            reply_to_message_id=message_id
        )
        return {"ok": True}
    
    if text == "/ayuda" or text == "/help":
        await telegram.send_message(
            chat_id,
            "📖 <b>Comandos disponibles:</b>\n\n"
            "• <b>Agregar cliente:</b>\n"
            "  <i>\"Nuevo cliente María García, cel 3109876543\"</i>\n\n"
            "• <b>Registrar venta:</b>\n"
            "  <i>\"Venta a María: 2kg pollo, total 50000\"</i>\n\n"
            "• <b>Consultar cliente:</b>\n"
            "  <i>\"Cuánto ha comprado María?\"</i>\n\n"
            "• <b>Ver resumen:</b>\n"
            "  <i>\"Ventas de hoy\"</i>\n\n"
            "• <b>Actualizar estado:</b>\n"
            "  <i>\"Marcar entregado pedido de Juan\"</i>",
            reply_to_message_id=message_id
        )
        return {"ok": True}
    
    if text == "/id":
        await telegram.send_message(
            chat_id,
            f"🆔 Tu ID de Telegram es: <code>{chat_id}</code>",
            reply_to_message_id=message_id
        )
        return {"ok": True}
    
    await telegram.send_typing_action(chat_id)
    
    tipo, sql, descripcion = await process_message(text)
    
    if tipo == "mensaje":
        await telegram.send_message(chat_id, descripcion, reply_to_message_id=message_id)
        return {"ok": True}
    
    try:
        logger.info(f"Ejecutando SQL: {sql[:100]}...")
        
        sql_upper = sql.upper().strip()
        if sql_upper.startswith("SELECT"):
            result = await db.fetch(sql)
            if result:
                response_text = f"✅ <b>{descripcion}</b>\n\n"
                for i, row in enumerate(result[:10], 1):
                    row_text = ", ".join(f"{k}: {v}" for k, v in row.items() if v is not None)
                    response_text += f"{i}. {row_text}\n"
                if len(result) > 10:
                    response_text += f"\n<i>... y {len(result) - 10} más</i>"
            else:
                response_text = "📭 No se encontraron resultados."
        else:
            result = await db.fetch(sql)
            if result:
                response_text = f"✅ <b>{descripcion}</b>\n\n"
                for key, value in result[0].items():
                    if value is not None:
                        response_text += f"• <b>{key}:</b> {value}\n"
            else:
                response_text = f"✅ {descripcion}"
        
        await telegram.send_message(chat_id, response_text, reply_to_message_id=message_id)
        
    except Exception as e:
        logger.error(f"Error ejecutando SQL: {e}")
        await telegram.send_message(
            chat_id,
            f"❌ Error al ejecutar la operación:\n<code>{str(e)[:200]}</code>",
            reply_to_message_id=message_id
        )
    
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "bot.main:app",
        host=config.HOST,
        port=config.PORT,
        reload=True
    )
