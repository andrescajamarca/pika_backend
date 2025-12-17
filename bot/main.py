import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Header, HTTPException
from typing import Optional

from .config import config
from .db import db
from .security import require_telegram_auth, is_user_allowed
from .telegram_client import telegram
from .conversation import conversations, ConversationState, SaleData
from .products import (
    get_product_display_name, find_product_by_button_id,
    get_productos_keyboard, get_cantidad_keyboard, get_confirmacion_keyboard
)
from .sale_handler import buscar_cliente_por_telefono, insertar_venta

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
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    # Manejar callback_query (botones)
    if "callback_query" in data:
        return await handle_callback(data["callback_query"])
    
    # Manejar mensaje normal
    if "message" not in data:
        return {"ok": True}
    
    message = data["message"]
    chat_id = message["chat"]["id"]
    user_name = message["from"].get("first_name", "Usuario")
    message_id = message["message_id"]
    text = message.get("text", "").strip()
    
    if not text:
        return {"ok": True}
    
    logger.info(f"Mensaje de {user_name} ({chat_id}): {text[:50]}...")
    
    # Verificar usuario autorizado
    if not is_user_allowed(chat_id):
        await telegram.send_message(
            chat_id,
            "⛔ No tienes permiso para usar este bot.\n"
            f"Tu ID es: <code>{chat_id}</code>\n"
            "Contacta al administrador para solicitar acceso.",
            reply_to_message_id=message_id
        )
        return {"ok": True}
    
    # Comandos especiales
    if text == "/start":
        conversations.reset(chat_id)
        await telegram.send_message(
            chat_id,
            "🐷 <b>¡Bienvenido a Pika Snacks Bot!</b>\n\n"
            "Soy tu asistente para registrar ventas.\n\n"
            "Usa /venta para iniciar un nuevo registro.",
            reply_to_message_id=message_id
        )
        return {"ok": True}
    
    if text == "/cancelar":
        conversations.reset(chat_id)
        await telegram.send_message(
            chat_id,
            "❌ Operación cancelada.",
            reply_to_message_id=message_id
        )
        return {"ok": True}
    
    if text == "/venta":
        conversations.reset(chat_id)
        conversations.set_state(chat_id, ConversationState.ESPERANDO_TELEFONO)
        await telegram.send_message(
            chat_id,
            "📱 <b>Nueva venta</b>\n\nIngresa el teléfono del cliente:",
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
    
    if text == "/ayuda" or text == "/help":
        await telegram.send_message(
            chat_id,
            "📖 <b>Cómo registrar una venta:</b>\n\n"
            "1. Usa /venta para iniciar\n"
            "2. Ingresa el teléfono del cliente\n"
            "3. Si es nuevo, ingresa su nombre\n"
            "4. Selecciona productos con los botones\n"
            "5. Ingresa el total\n"
            "6. Confirma la venta\n\n"
            "<b>Otros comandos:</b>\n"
            "• /cancelar - Cancela la operación actual\n"
            "• /id - Muestra tu ID de Telegram",
            reply_to_message_id=message_id
        )
        return {"ok": True}
    
    # Procesar según estado de conversación
    conv = conversations.get(chat_id)
    
    if conv.state == ConversationState.ESPERANDO_TELEFONO:
        return await handle_telefono(chat_id, text, message_id)
    
    elif conv.state == ConversationState.ESPERANDO_NOMBRE:
        return await handle_nombre(chat_id, text, message_id)
    
    elif conv.state == ConversationState.ESPERANDO_TOTAL:
        return await handle_total(chat_id, text, message_id)
    
    else:
        await telegram.send_message(
            chat_id,
            "Usa /venta para registrar una nueva venta.",
            reply_to_message_id=message_id
        )
        return {"ok": True}


async def handle_telefono(chat_id: int, telefono: str, message_id: int):
    """Procesa el teléfono ingresado."""
    # Limpiar teléfono (solo números)
    telefono_limpio = "".join(filter(str.isdigit, telefono))
    
    if len(telefono_limpio) < 7:
        await telegram.send_message(
            chat_id,
            "⚠️ Teléfono inválido. Ingresa al menos 7 dígitos:",
            reply_to_message_id=message_id
        )
        return {"ok": True}
    
    conv = conversations.get(chat_id)
    conv.sale_data.telefono = telefono_limpio
    
    # Buscar cliente existente
    client_id, nombre = await buscar_cliente_por_telefono(telefono_limpio)
    
    if client_id:
        conv.sale_data.client_id = client_id
        conv.sale_data.nombre = nombre
        conv.sale_data.es_cliente_nuevo = False
        conv.state = ConversationState.SELECCIONANDO_PRODUCTOS
        
        await telegram.send_message_with_keyboard(
            chat_id,
            f"✅ <b>Cliente encontrado:</b> {nombre}\n\n"
            "🛒 Selecciona los productos:",
            get_productos_keyboard(),
            reply_to_message_id=message_id
        )
    else:
        conv.sale_data.es_cliente_nuevo = True
        conv.state = ConversationState.ESPERANDO_NOMBRE
        
        await telegram.send_message(
            chat_id,
            "👤 <b>Cliente nuevo</b>\n\nIngresa el nombre del cliente:",
            reply_to_message_id=message_id
        )
    
    return {"ok": True}


async def handle_nombre(chat_id: int, nombre: str, message_id: int):
    """Procesa el nombre del cliente nuevo."""
    if len(nombre) < 2:
        await telegram.send_message(
            chat_id,
            "⚠️ Nombre muy corto. Ingresa el nombre completo:",
            reply_to_message_id=message_id
        )
        return {"ok": True}
    
    conv = conversations.get(chat_id)
    conv.sale_data.nombre = nombre
    conv.state = ConversationState.SELECCIONANDO_PRODUCTOS
    
    await telegram.send_message_with_keyboard(
        chat_id,
        f"👤 Cliente: <b>{nombre}</b>\n\n"
        "🛒 Selecciona los productos:",
        get_productos_keyboard(),
        reply_to_message_id=message_id
    )
    
    return {"ok": True}


async def handle_total(chat_id: int, total_str: str, message_id: int):
    """Procesa el total ingresado."""
    # Limpiar: quitar $, puntos, comas, espacios
    total_limpio = total_str.replace("$", "").replace(".", "").replace(",", "").replace(" ", "")
    
    try:
        total = int(total_limpio)
        if total <= 0:
            raise ValueError()
    except ValueError:
        await telegram.send_message(
            chat_id,
            "⚠️ Total inválido. Ingresa solo el número (ej: 66000):",
            reply_to_message_id=message_id
        )
        return {"ok": True}
    
    conv = conversations.get(chat_id)
    conv.sale_data.total = total
    conv.state = ConversationState.CONFIRMACION
    
    # Mostrar resumen
    resumen = generar_resumen(conv.sale_data)
    
    await telegram.send_message_with_keyboard(
        chat_id,
        resumen,
        get_confirmacion_keyboard(),
        reply_to_message_id=message_id
    )
    
    return {"ok": True}


async def handle_callback(callback_query: dict):
    """Maneja los callbacks de botones inline."""
    callback_id = callback_query["id"]
    chat_id = callback_query["message"]["chat"]["id"]
    message_id = callback_query["message"]["message_id"]
    data = callback_query.get("data", "")
    
    # Verificar usuario autorizado
    if not is_user_allowed(chat_id):
        await telegram.answer_callback_query(callback_id, "⛔ No autorizado")
        return {"ok": True}
    
    conv = conversations.get(chat_id)
    
    # Callback de producto
    if data.startswith("prod_"):
        producto_id = data[5:]  # Quitar "prod_"
        
        if producto_id == "finalizar":
            if not conv.sale_data.productos:
                await telegram.answer_callback_query(
                    callback_id, 
                    "⚠️ Agrega al menos un producto",
                    show_alert=True
                )
                return {"ok": True}
            
            conv.state = ConversationState.ESPERANDO_TOTAL
            await telegram.answer_callback_query(callback_id)
            await telegram.edit_message_text(
                chat_id,
                message_id,
                generar_lista_productos(conv.sale_data) + "\n\n💰 <b>Ingresa el total de la venta:</b>"
            )
            return {"ok": True}
        
        # Seleccionó un producto
        producto = find_product_by_button_id(producto_id)
        if producto:
            conv.sale_data.producto_actual = producto
            conv.state = ConversationState.SELECCIONANDO_CANTIDAD
            
            nombre_producto = get_product_display_name(producto)
            await telegram.answer_callback_query(callback_id)
            await telegram.edit_message_text(
                chat_id,
                message_id,
                f"📦 <b>{nombre_producto}</b>\n\n¿Cuántas cajas?",
                {"inline_keyboard": get_cantidad_keyboard()}
            )
        return {"ok": True}
    
    # Callback de cantidad
    if data.startswith("cant_"):
        cantidad_str = data[5:]
        
        if cantidad_str == "cancelar":
            conv.sale_data.producto_actual = None
            conv.state = ConversationState.SELECCIONANDO_PRODUCTOS
            await telegram.answer_callback_query(callback_id)
            await telegram.edit_message_text(
                chat_id,
                message_id,
                generar_lista_productos(conv.sale_data) + "\n\n🛒 Selecciona productos:",
                {"inline_keyboard": get_productos_keyboard()}
            )
            return {"ok": True}
        
        cantidad = int(cantidad_str)
        producto = conv.sale_data.producto_actual
        
        if producto:
            conv.sale_data.productos.append({
                "name": producto["name"],
                "variant": producto.get("variant"),
                "cantidad": cantidad
            })
            conv.sale_data.producto_actual = None
        
        conv.state = ConversationState.SELECCIONANDO_PRODUCTOS
        nombre_producto = get_product_display_name(producto)
        
        await telegram.answer_callback_query(callback_id, f"✅ {cantidad}x {nombre_producto}")
        await telegram.edit_message_text(
            chat_id,
            message_id,
            generar_lista_productos(conv.sale_data) + "\n\n🛒 Selecciona más productos o finaliza:",
            {"inline_keyboard": get_productos_keyboard()}
        )
        return {"ok": True}
    
    # Callback de confirmación
    if data.startswith("confirm_"):
        if data == "confirm_si":
            success, mensaje = await insertar_venta(conv.sale_data)
            conversations.reset(chat_id)
            await telegram.answer_callback_query(callback_id)
            await telegram.edit_message_text(chat_id, message_id, mensaje)
        else:
            conversations.reset(chat_id)
            await telegram.answer_callback_query(callback_id)
            await telegram.edit_message_text(chat_id, message_id, "❌ Venta cancelada.")
        return {"ok": True}
    
    await telegram.answer_callback_query(callback_id)
    return {"ok": True}


def generar_lista_productos(sale_data: SaleData) -> str:
    """Genera texto con lista de productos agregados."""
    if not sale_data.productos:
        return "🛒 <b>Carrito vacío</b>"
    
    lineas = ["🛒 <b>Productos:</b>"]
    for item in sale_data.productos:
        nombre = item["name"]
        if item.get("variant"):
            nombre += f" {item['variant']}"
        lineas.append(f"  • {item['cantidad']}x {nombre}")
    
    return "\n".join(lineas)


def generar_resumen(sale_data: SaleData) -> str:
    """Genera resumen completo de la venta."""
    cliente_info = f"👤 <b>Cliente:</b> {sale_data.nombre}"
    if sale_data.es_cliente_nuevo:
        cliente_info += " (nuevo)"
    cliente_info += f"\n📱 <b>Tel:</b> {sale_data.telefono}"
    
    productos = generar_lista_productos(sale_data)
    total = f"💰 <b>Total:</b> ${sale_data.total:,} COP"
    
    return f"📦 <b>Confirmar venta:</b>\n\n{cliente_info}\n\n{productos}\n\n{total}"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "bot.main:app",
        host=config.HOST,
        port=config.PORT,
        reload=True
    )
