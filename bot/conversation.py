from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class ConversationState(Enum):
    IDLE = "idle"
    ESPERANDO_TELEFONO = "esperando_telefono"
    ESPERANDO_NOMBRE = "esperando_nombre"
    SELECCIONANDO_PRODUCTOS = "seleccionando_productos"
    SELECCIONANDO_CANTIDAD = "seleccionando_cantidad"
    ESPERANDO_TOTAL = "esperando_total"
    CONFIRMACION = "confirmacion"


@dataclass
class SaleData:
    telefono: Optional[str] = None
    nombre: Optional[str] = None
    client_id: Optional[str] = None
    es_cliente_nuevo: bool = False
    productos: list = field(default_factory=list)
    producto_actual: Optional[Dict[str, str]] = None
    total: Optional[int] = None


@dataclass 
class UserConversation:
    state: ConversationState = ConversationState.IDLE
    sale_data: SaleData = field(default_factory=SaleData)


class ConversationManager:
    def __init__(self):
        self._conversations: Dict[int, UserConversation] = {}
    
    def get(self, chat_id: int) -> UserConversation:
        if chat_id not in self._conversations:
            self._conversations[chat_id] = UserConversation()
        return self._conversations[chat_id]
    
    def reset(self, chat_id: int):
        self._conversations[chat_id] = UserConversation()
    
    def set_state(self, chat_id: int, state: ConversationState):
        self.get(chat_id).state = state


conversations = ConversationManager()
