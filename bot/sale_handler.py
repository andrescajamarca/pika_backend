from typing import Optional, Tuple
from .db import db
from .conversation import SaleData


async def buscar_cliente_por_telefono(telefono: str) -> Tuple[Optional[str], Optional[str]]:
    """Busca cliente por teléfono. Retorna (client_id, nombre) o (None, None)."""
    result = await db.fetchrow(
        "SELECT id, name FROM clients WHERE phone = $1 LIMIT 1",
        telefono
    )
    if result:
        return str(result["id"]), result["name"]
    return None, None


async def insertar_venta(sale_data: SaleData) -> Tuple[bool, str]:
    """
    Inserta la venta completa en la BD.
    - Si cliente nuevo, lo crea
    - Crea la orden
    - Crea los order_items
    
    Retorna (success, message)
    """
    try:
        async with db.acquire() as conn:
            async with conn.transaction():
                # 1. Obtener o crear cliente
                if sale_data.es_cliente_nuevo:
                    source_id = f"telegram_{sale_data.telefono}"
                    result = await conn.fetchrow(
                        """
                        INSERT INTO clients (name, phone, source_client_id)
                        VALUES ($1, $2, $3)
                        RETURNING id
                        """,
                        sale_data.nombre,
                        sale_data.telefono,
                        source_id
                    )
                    client_id = result["id"]
                else:
                    client_id = sale_data.client_id
                
                # 2. Crear orden
                order_result = await conn.fetchrow(
                    """
                    INSERT INTO orders (client_id, order_date, total, status)
                    VALUES ($1, CURRENT_DATE, $2, 'pending')
                    RETURNING id
                    """,
                    client_id,
                    sale_data.total
                )
                order_id = order_result["id"]
                
                # 3. Crear order_items
                for item in sale_data.productos:
                    # Buscar product_id si existe
                    product_result = await conn.fetchrow(
                        """
                        SELECT id FROM products 
                        WHERE name = $1 AND (variant = $2 OR (variant IS NULL AND $2 IS NULL))
                        LIMIT 1
                        """,
                        item["name"],
                        item.get("variant")
                    )
                    product_id = product_result["id"] if product_result else None
                    
                    await conn.execute(
                        """
                        INSERT INTO order_items (order_id, product_id, product_name, variant, quantity, unit)
                        VALUES ($1, $2, $3, $4, $5, 'caja')
                        """,
                        order_id,
                        product_id,
                        item["name"],
                        item.get("variant"),
                        item["cantidad"]
                    )
                
                return True, f"✅ Venta registrada correctamente (Orden #{str(order_id)[:8]})"
    
    except Exception as e:
        return False, f"❌ Error al guardar: {str(e)}"
