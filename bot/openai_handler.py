import re
import json
from openai import AsyncOpenAI
from typing import Tuple, Optional

from .config import config
from .db import DB_SCHEMA_CONTEXT

client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)

FORBIDDEN_KEYWORDS = [
    "DROP", "TRUNCATE", "ALTER", "CREATE", "GRANT", "REVOKE",
    "DELETE FROM clients", "DELETE FROM orders", "DELETE FROM products",
    "DELETE FROM order_items"
]

ALLOWED_OPERATIONS = ["INSERT", "UPDATE", "SELECT"]

SYSTEM_PROMPT = f"""Eres un asistente de base de datos para Pika Snacks, una empresa de snacks y comida.
Tu trabajo es interpretar mensajes en español y generar consultas SQL para PostgreSQL.

{DB_SCHEMA_CONTEXT}

## Reglas:
1. Genera SOLO SQL válido para PostgreSQL
2. Para nuevos clientes, genera un source_client_id único usando: 'telegram_' + nombre_sin_espacios + '_' + timestamp
3. Para insertar pedidos, primero busca el client_id por nombre o teléfono
4. Usa transacciones cuando sea necesario (BEGIN/COMMIT)
5. Siempre retorna el resultado de la operación (RETURNING *)
6. Si no puedes generar SQL, responde con un mensaje explicativo comenzando con "ERROR:"
7. Para consultas, usa las vistas cuando sea apropiado
8. Los precios están en pesos colombianos (sin decimales generalmente)

## Formato de respuesta:
Responde SOLO con un JSON válido con esta estructura:
{{
    "tipo": "query" | "mensaje",
    "sql": "SQL aquí si tipo es query",
    "descripcion": "Descripción breve de la acción",
    "mensaje": "Mensaje para el usuario si tipo es mensaje"
}}

## Ejemplos:

Usuario: "Agregar cliente Juan Pérez, teléfono 3001234567"
{{
    "tipo": "query",
    "sql": "INSERT INTO clients (name, phone, source_client_id) VALUES ('Juan Pérez', '3001234567', 'telegram_juanperez_' || EXTRACT(EPOCH FROM NOW())::BIGINT) RETURNING *",
    "descripcion": "Insertar nuevo cliente"
}}

Usuario: "Venta a Juan: 2kg pollo, 1kg chicharrón, total 85000"
{{
    "tipo": "query",
    "sql": "WITH cliente AS (SELECT id FROM clients WHERE name ILIKE '%Juan%' LIMIT 1), nuevo_pedido AS (INSERT INTO orders (client_id, order_date, total, status) SELECT id, CURRENT_DATE, 85000, 'pending' FROM cliente RETURNING id) INSERT INTO order_items (order_id, product_name, quantity, unit) SELECT id, unnest(ARRAY['pollo', 'chicharrón']), unnest(ARRAY[2, 1]), 'kg' FROM nuevo_pedido RETURNING *",
    "descripcion": "Registrar venta con items"
}}

Usuario: "Hola, cómo estás?"
{{
    "tipo": "mensaje",
    "mensaje": "¡Hola! Soy el bot de Pika Snacks. Puedo ayudarte a:\\n- Agregar clientes\\n- Registrar ventas\\n- Consultar información\\n\\n¿Qué necesitas?"
}}
"""


def validate_sql(sql: str) -> Tuple[bool, str]:
    """Valida que el SQL sea seguro para ejecutar."""
    sql_upper = sql.upper()
    
    for keyword in FORBIDDEN_KEYWORDS:
        if keyword in sql_upper:
            return False, f"Operación no permitida: {keyword}"
    
    has_allowed = any(op in sql_upper for op in ALLOWED_OPERATIONS)
    if not has_allowed:
        return False, "Solo se permiten operaciones SELECT, INSERT o UPDATE"
    
    return True, "OK"


async def process_message(user_message: str) -> Tuple[str, Optional[str], str]:
    """
    Procesa un mensaje del usuario y genera SQL si corresponde.
    
    Returns:
        Tuple[tipo, sql, descripcion_o_mensaje]
    """
    try:
        response = await client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            temperature=0.1,
            max_tokens=1000
        )
        
        content = response.choices[0].message.content.strip()
        
        if content.startswith("```"):
            content = re.sub(r"```json?\n?", "", content)
            content = content.replace("```", "")
        
        result = json.loads(content)
        
        tipo = result.get("tipo", "mensaje")
        
        if tipo == "query":
            sql = result.get("sql", "")
            descripcion = result.get("descripcion", "Ejecutar consulta")
            
            is_valid, error = validate_sql(sql)
            if not is_valid:
                return "mensaje", None, f"⚠️ {error}"
            
            return "query", sql, descripcion
        else:
            mensaje = result.get("mensaje", "No entendí tu mensaje.")
            return "mensaje", None, mensaje
            
    except json.JSONDecodeError:
        return "mensaje", None, "❌ Error procesando la respuesta. Intenta de nuevo."
    except Exception as e:
        return "mensaje", None, f"❌ Error: {str(e)}"
