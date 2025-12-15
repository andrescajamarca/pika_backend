"""
Exporta ventas_llm.jsonl a tablas JSON normalizadas (clients, orders, order_items).
Los archivos generados pueden importarse a cualquier motor de BD.

Uso:
    python scripts/exportar_tablas_json.py

Salidas:
    data/exports/tables/clients.json
    data/exports/tables/orders.json
    data/exports/tables/order_items.json
"""

import json
import uuid
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parents[1]
EXPORTS_DIR = BASE_DIR / "data" / "exports"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
TABLES_DIR = EXPORTS_DIR / "tables"

VENTAS_LLM_FILE = EXPORTS_DIR / "ventas_llm.jsonl"
CONVERSACIONES_FILE = PROCESSED_DIR / "conversaciones.jsonl"


def cargar_timestamps_conversaciones() -> dict[str, str]:
    """Carga el timestamp del primer mensaje de cada sesión (created_at del cliente)."""
    timestamps = {}
    with CONVERSACIONES_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            conv = json.loads(line)
            session_id = conv.get("session_id", "")
            client_id = conv.get("client_id", "")
            messages = conv.get("messages", [])
            if messages:
                first_ts = messages[0].get("timestamp", "")
                if first_ts and client_id not in timestamps:
                    timestamps[client_id] = first_ts
    return timestamps


def cargar_last_message_dates() -> dict[str, str]:
    """Carga la fecha del último mensaje de cada sesión (para order_date fallback)."""
    dates = {}
    with CONVERSACIONES_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            conv = json.loads(line)
            session_id = conv.get("session_id", "")
            messages = conv.get("messages", [])
            if messages:
                last_ts = messages[-1].get("timestamp", "")
                if last_ts:
                    dates[session_id] = last_ts[:10]  # Solo fecha YYYY-MM-DD
    return dates


def main() -> None:
    print("🔍 Cargando datos...")
    
    # Crear directorio de salida
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    
    # Cargar timestamps para created_at de clientes
    client_first_contact = cargar_timestamps_conversaciones()
    print(f"  {len(client_first_contact)} clientes con fecha de primer contacto")
    
    # Cargar fechas de último mensaje para fallback de order_date
    session_last_dates = cargar_last_message_dates()
    print(f"  {len(session_last_dates)} sesiones con fechas")
    
    # Cargar resultados del LLM
    resultados = []
    with VENTAS_LLM_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            resultados.append(json.loads(line))
    print(f"  {len(resultados)} resultados del LLM")
    
    # Filtrar solo pedidos confirmados y delivery_followup
    pedidos = [
        r for r in resultados 
        if r.get("order", {}).get("order_type") in ("confirmed", "delivery_followup")
    ]
    print(f"  {len(pedidos)} pedidos a exportar")
    
    # Estructuras para las tablas
    clients_map: dict[str, dict] = {}  # source_client_id -> client record
    orders_list: list[dict] = []
    order_items_list: list[dict] = []
    
    for r in pedidos:
        order_data = r.get("order", {})
        customer_data = r.get("customer", {})
        source_client_id = r.get("_client_id", "")
        source_session_id = r.get("_session_id", "")
        
        # --- CLIENTE ---
        if source_client_id not in clients_map:
            # Extraer teléfono normalizado
            phone = customer_data.get("phone", "")
            if phone and phone.startswith("+"):
                phone_normalized = phone
            elif source_client_id.startswith("+"):
                phone_normalized = source_client_id
            else:
                phone_normalized = None
            
            # Nombre del cliente
            name = customer_data.get("name", "")
            if not name and not phone_normalized:
                # Intentar extraer nombre del source_client_id si no es teléfono
                if not source_client_id.startswith("+"):
                    name = source_client_id.replace("WhatsApp - ", "").strip()
            
            client_id = str(uuid.uuid4())
            created_at = client_first_contact.get(source_client_id, datetime.now().isoformat())
            
            clients_map[source_client_id] = {
                "id": client_id,
                "phone": phone_normalized,
                "name": name or None,
                "source_client_id": source_client_id,
                "created_at": created_at
            }
        
        client_record = clients_map[source_client_id]
        
        # --- ORDEN ---
        order_id = str(uuid.uuid4())
        
        # order_date: primero del LLM, luego fallback del último mensaje
        order_date = order_data.get("order_date") or ""
        if not order_date:
            order_date = session_last_dates.get(source_session_id, "")
        
        # Total
        total = order_data.get("approx_total")
        if isinstance(total, str):
            # Limpiar string de total (quitar $, puntos, etc.)
            total = total.replace("$", "").replace(".", "").replace(",", ".").strip()
            try:
                total = float(total)
            except ValueError:
                total = None
        
        order_record = {
            "id": order_id,
            "client_id": client_record["id"],
            "order_date": order_date or None,
            "city": order_data.get("city") or None,
            "address": order_data.get("address") or None,
            "payment_method": order_data.get("payment_method") or None,
            "total": total,
            "status": order_data.get("order_type", "confirmed"),
            "source_session_id": source_session_id,
            "created_at": datetime.now().isoformat()
        }
        orders_list.append(order_record)
        
        # --- ORDER ITEMS ---
        products = order_data.get("products", [])
        if isinstance(products, list):
            for p in products:
                if isinstance(p, dict):
                    item_id = str(uuid.uuid4())
                    
                    # Precio unitario
                    unit_price = p.get("unit_price")
                    if isinstance(unit_price, str):
                        unit_price = unit_price.replace("$", "").replace(".", "").replace(",", ".").strip()
                        try:
                            unit_price = float(unit_price)
                        except ValueError:
                            unit_price = None
                    
                    item_record = {
                        "id": item_id,
                        "order_id": order_id,
                        "product_name": p.get("name", ""),
                        "variant": p.get("variant") or None,
                        "quantity": p.get("quantity_units") or 1,
                        "unit": p.get("unit") or None,
                        "unit_price": unit_price
                    }
                    order_items_list.append(item_record)
    
    # Convertir clients_map a lista
    clients_list = list(clients_map.values())
    
    # Guardar archivos JSON
    with (TABLES_DIR / "clients.json").open("w", encoding="utf-8") as f:
        json.dump(clients_list, f, ensure_ascii=False, indent=2)
    
    with (TABLES_DIR / "orders.json").open("w", encoding="utf-8") as f:
        json.dump(orders_list, f, ensure_ascii=False, indent=2)
    
    with (TABLES_DIR / "order_items.json").open("w", encoding="utf-8") as f:
        json.dump(order_items_list, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Tablas exportadas a {TABLES_DIR}/")
    print(f"   clients.json:     {len(clients_list)} registros")
    print(f"   orders.json:      {len(orders_list)} registros")
    print(f"   order_items.json: {len(order_items_list)} registros")


if __name__ == "__main__":
    main()
