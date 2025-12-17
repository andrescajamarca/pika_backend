from typing import List, Dict, Optional

PRODUCTOS = [
    {"name": "Arepa", "variant": "Maíz Multigranos", "emoji": "🫓"},
    {"name": "Arepa", "variant": "Maíz Queso y Semillas", "emoji": "🫓"},
    {"name": "Arepa", "variant": "Yuca y Queso", "emoji": "🫓"},
    {"name": "Arepa", "variant": "Maduro y Queso", "emoji": "🫓"},
    {"name": "Brownie", "variant": None, "emoji": "🍫"},
    {"name": "Muffin", "variant": "Chocolate", "emoji": "🧁"},
    {"name": "Muffin", "variant": "Banano", "emoji": "🧁"},
    {"name": "Muffin", "variant": "Zanahoria", "emoji": "🧁"},
    {"name": "Waffle", "variant": "Yuca y Queso", "emoji": "🧇"},
    {"name": "Waffle", "variant": "Plátano y Queso", "emoji": "🧇"},
]


def get_product_display_name(product: Dict) -> str:
    """Retorna nombre para mostrar: 'Muffin Banano' o 'Brownie'"""
    if product.get("variant"):
        return f"{product['name']} {product['variant']}"
    return product["name"]


def get_product_button_id(product: Dict) -> str:
    """Retorna ID único para callback: 'muffin_banano' o 'brownie_'"""
    variant = product.get("variant") or ""
    return f"{product['name'].lower()}_{variant.lower().replace(' ', '_')}"


def find_product_by_button_id(button_id: str) -> Optional[Dict]:
    """Busca producto por su button_id"""
    for p in PRODUCTOS:
        if get_product_button_id(p) == button_id:
            return p
    return None


def get_productos_keyboard() -> List[List[Dict]]:
    """Genera el teclado inline con productos (2 columnas)"""
    keyboard = []
    row = []
    
    for product in PRODUCTOS:
        display = f"{product['emoji']} {get_product_display_name(product)}"
        callback = f"prod_{get_product_button_id(product)}"
        
        row.append({"text": display, "callback_data": callback})
        
        if len(row) == 2:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    keyboard.append([{"text": "✅ Finalizar pedido", "callback_data": "prod_finalizar"}])
    
    return keyboard


def get_cantidad_keyboard() -> List[List[Dict]]:
    """Genera teclado para seleccionar cantidad"""
    return [
        [
            {"text": "1", "callback_data": "cant_1"},
            {"text": "2", "callback_data": "cant_2"},
            {"text": "3", "callback_data": "cant_3"},
            {"text": "4", "callback_data": "cant_4"},
            {"text": "5", "callback_data": "cant_5"},
        ],
        [
            {"text": "6", "callback_data": "cant_6"},
            {"text": "7", "callback_data": "cant_7"},
            {"text": "8", "callback_data": "cant_8"},
            {"text": "9", "callback_data": "cant_9"},
            {"text": "10", "callback_data": "cant_10"},
        ],
        [{"text": "❌ Cancelar", "callback_data": "cant_cancelar"}]
    ]


def get_confirmacion_keyboard() -> List[List[Dict]]:
    """Genera teclado de confirmación"""
    return [
        [
            {"text": "✅ Confirmar", "callback_data": "confirm_si"},
            {"text": "❌ Cancelar", "callback_data": "confirm_no"},
        ]
    ]
