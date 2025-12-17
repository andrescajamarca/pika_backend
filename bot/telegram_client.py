import httpx
from typing import Optional, List, Dict

from .config import config


class TelegramClient:
    def __init__(self):
        self.base_url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"
    
    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_to_message_id: Optional[int] = None,
        reply_markup: Optional[Dict] = None
    ) -> dict:
        """Envía un mensaje de texto, opcionalmente con botones inline."""
        async with httpx.AsyncClient() as client:
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML"
            }
            if reply_to_message_id:
                payload["reply_to_message_id"] = reply_to_message_id
            if reply_markup:
                payload["reply_markup"] = reply_markup
            
            response = await client.post(
                f"{self.base_url}/sendMessage",
                json=payload
            )
            return response.json()
    
    async def send_message_with_keyboard(
        self,
        chat_id: int,
        text: str,
        keyboard: List[List[Dict]],
        reply_to_message_id: Optional[int] = None
    ) -> dict:
        """Envía mensaje con teclado inline."""
        reply_markup = {"inline_keyboard": keyboard}
        return await self.send_message(chat_id, text, reply_to_message_id, reply_markup)
    
    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: Optional[str] = None,
        show_alert: bool = False
    ) -> dict:
        """Responde a un callback query (cuando usuario toca botón)."""
        async with httpx.AsyncClient() as client:
            payload = {"callback_query_id": callback_query_id}
            if text:
                payload["text"] = text
                payload["show_alert"] = show_alert
            
            response = await client.post(
                f"{self.base_url}/answerCallbackQuery",
                json=payload
            )
            return response.json()
    
    async def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup: Optional[Dict] = None
    ) -> dict:
        """Edita un mensaje existente."""
        async with httpx.AsyncClient() as client:
            payload = {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": "HTML"
            }
            if reply_markup:
                payload["reply_markup"] = reply_markup
            
            response = await client.post(
                f"{self.base_url}/editMessageText",
                json=payload
            )
            return response.json()
    
    async def send_typing_action(self, chat_id: int) -> dict:
        """Envía indicador de 'escribiendo...'"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/sendChatAction",
                json={
                    "chat_id": chat_id,
                    "action": "typing"
                }
            )
            return response.json()


telegram = TelegramClient()
