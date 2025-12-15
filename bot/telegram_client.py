import httpx
from typing import Optional

from .config import config


class TelegramClient:
    def __init__(self):
        self.base_url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"
    
    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str = "HTML",
        reply_to_message_id: Optional[int] = None
    ) -> dict:
        """Envía un mensaje a un chat."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "reply_to_message_id": reply_to_message_id
                }
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
