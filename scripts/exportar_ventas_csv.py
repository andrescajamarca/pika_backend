"""
Exporta ventas_llm.jsonl a CSV, completando order_date desde conversaciones.jsonl
cuando el LLM no lo extrajo.

Uso:
    python scripts/exportar_ventas_csv.py
"""

import csv
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
EXPORTS_DIR = BASE_DIR / "data" / "exports"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

VENTAS_LLM_FILE = EXPORTS_DIR / "ventas_llm.jsonl"
CONVERSACIONES_FILE = PROCESSED_DIR / "conversaciones.jsonl"
OUTPUT_CSV = EXPORTS_DIR / "ventas.csv"


def cargar_timestamps_conversaciones() -> dict[str, str]:
    """Carga el timestamp del último mensaje de cada sesión."""
    timestamps = {}
    with CONVERSACIONES_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            conv = json.loads(line)
            session_id = conv.get("session_id", "")
            messages = conv.get("messages", [])
            if messages:
                # Tomar el timestamp del último mensaje
                last_ts = messages[-1].get("timestamp", "")
                if last_ts:
                    # Extraer solo la fecha (YYYY-MM-DD)
                    timestamps[session_id] = last_ts[:10]
    return timestamps


def main() -> None:
    print("🔍 Cargando datos...")
    
    # Cargar timestamps de conversaciones
    timestamps = cargar_timestamps_conversaciones()
    print(f"  {len(timestamps)} sesiones con timestamps")
    
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
    
    # Contadores
    con_fecha_llm = 0
    con_fecha_fallback = 0
    sin_fecha = 0
    
    # Escribir CSV
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        
        writer.writerow([
            "conversation_id",
            "session_id",
            "client_id",
            "customer_phone",
            "customer_name",
            "order_type",
            "order_date",
            "order_date_source",  # Nueva columna para saber de dónde vino
            "city",
            "address",
            "payment_method",
            "approx_total",
            "products"
        ])
        
        for r in pedidos:
            order = r.get("order", {})
            customer = r.get("customer", {})
            session_id = r.get("_session_id", "")
            
            # Determinar order_date
            order_date = order.get("order_date") or ""
            date_source = ""
            
            if order_date:
                con_fecha_llm += 1
                date_source = "llm"
            else:
                # Fallback: usar timestamp del último mensaje
                fallback_date = timestamps.get(session_id, "")
                if fallback_date:
                    order_date = fallback_date
                    con_fecha_fallback += 1
                    date_source = "last_message"
                else:
                    sin_fecha += 1
                    date_source = "none"
            
            # Formatear productos
            products = order.get("products", [])
            if isinstance(products, list):
                prod_strs = []
                for p in products:
                    if isinstance(p, dict):
                        name = p.get("name", "")
                        variant = p.get("variant", "")
                        qty = p.get("quantity_units", "")
                        unit = p.get("unit", "")
                        parts = [name]
                        if variant:
                            parts.append(f"({variant})")
                        if qty:
                            parts.append(f"x{qty}")
                        if unit:
                            parts.append(unit)
                        prod_strs.append(" ".join(parts))
                products_str = "; ".join(prod_strs)
            else:
                products_str = ""
            
            writer.writerow([
                r.get("_conversation_id", ""),
                session_id,
                r.get("_client_id", ""),
                customer.get("phone", ""),
                customer.get("name", ""),
                order.get("order_type", ""),
                order_date,
                date_source,
                order.get("city", ""),
                order.get("address", ""),
                order.get("payment_method", ""),
                order.get("approx_total", ""),
                products_str
            ])
    
    print(f"\n✅ Exportado: {OUTPUT_CSV}")
    print(f"   {len(pedidos)} pedidos totales")
    print(f"   {con_fecha_llm} con fecha extraída por LLM")
    print(f"   {con_fecha_fallback} con fecha del último mensaje (fallback)")
    print(f"   {sin_fecha} sin fecha")


if __name__ == "__main__":
    main()
