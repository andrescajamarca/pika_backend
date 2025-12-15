"""
Extrae información de ventas de conversaciones usando GPT-4o-mini.

Uso:
    python scripts/extraer_ventas.py [--limit N] [--dry-run]

Opciones:
    --limit N    Procesar solo las primeras N conversaciones (para pruebas)
    --dry-run    Mostrar qué se procesaría sin llamar a la API
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

# ─────────────────────────────────────────────────────────────────────────────
# Configuración
# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parents[1]
PROCESSED_DIR = BASE_DIR / "data" / "processed"
EXPORTS_DIR = BASE_DIR / "data" / "exports"

CONVERSACIONES_FILE = PROCESSED_DIR / "conversaciones.jsonl"

# Cargar variables de entorno
load_dotenv(BASE_DIR / ".env", override=True)

# TODO: Reemplazar con tu prompt personalizado
SYSTEM_PROMPT = """\
Eres un asistente experto en análisis de conversaciones de WhatsApp para un
emprendimiento de snacks saludables (arepas, waffles, muffins, brownies, etc.).

TU ÚNICO OBJETIVO:
A partir de UNA sola conversación de WhatsApp entre un cliente y el negocio,
debes detectar si hay una VENTA / PEDIDO y devolver SOLO la información
estructurada del pedido en formato JSON.

FORMATO DEL MENSAJE QUE RECIBIRÁS:
- El contenido del usuario tendrá este formato de texto:

  CONVERSATION_ID: <id_de_conversacion>
  CLIENT_ID: <id_o_telefono_del_cliente>
  Cliente: <mensaje del cliente>
  Negocio: <mensaje del negocio>
  Cliente: <otro mensaje>
  ...

- Donde:
  - Las líneas que empiezan con "Cliente:" son mensajes del cliente (equivalente a rol "user").
  - Las líneas que empiezan con "Negocio:" son mensajes del negocio (equivalente a rol "assistant").
  - "CONVERSATION_ID" y "CLIENT_ID" son metadatos que debes usar para llenar el JSON de salida.

REGLAS GENERALES:
- SOLO respondes con JSON válido. NO incluyas explicaciones, texto suelto ni comentarios.
- Usa SIEMPRE el esquema dado abajo.
- Si no sabes un dato, usa null.
- NO inventes precios, direcciones, ciudades ni métodos de pago si no aparecen en la conversación.
- Siempre que armes el campo "products", debes usar SOLO los nombres oficiales del catálogo para el campo "name" y corregir errores de ortografía, plurales o abreviaciones. 
- Catálogo de nombres oficiales ("name"): "Muffin", "Arepa", "Brownie", "Waffle"
- Las Variantes por porducto son: 
- Muffin: "chocolate", "Banano", "Zanahora"
- Arepa: "Yuca y Queso", "Maduro y Queso", "Maiz Multigranos", "Maiz Queso y Semillas","Maiz Multigranos" 
- Brownie, no tiene variantes. 
- Waffle: "Yuca y Queso", "Platano y Queso"
- Si en la conversación aparecen variantes mal escritas, en plural o con letras cambiadas, debes MAPEARLAS al nombre correcto del catálogo. Ejemplos:
- Todo lo que parezca "Muffin":
  - "Muffin", "Muffins", "Mufin", "Mufi", "Mufins", "Mufinss" → usar "Muffin"
- Todo lo que parezca "Arepa":
  - "Arepa", "Arepas", "Arepita", "Arepitas", "Arepitas integrales" → usar "Arepa"
    (el detalle como "integrales" va en el campo "variant")
- Todo lo que parezca "Brownie":
  - "Brownie", "Brownies", "Browni", "Bronwie" → usar "Brownie"
- Todo lo que parezca "Waffle":
  - "Waffle", "Waffles", "Wafle", "Wafles" → usar "Waffle"
- El campo "name" debe ser SIEMPRE uno de los nombres del catálogo anterior.
- El campo "variant" debe ser SIEMPRE una de las variantes del catálogo anterior o null si no hay variantes.



FORMATO DE SALIDA (JSON):

{
  "conversation_id": string,          // Toma el valor de la línea "CONVERSATION_ID: ..."
  "customer": {
    "phone": string | null,          // Idealmente toma el valor de "CLIENT_ID: ..." si parece un número
    "name": string | null            // Nombre del cliente si aparece (ej: "Soy Ana", "Hola, habla Juan")
  },
  "order": {
    "has_order": boolean,            // true si hay venta/pedido claro, false en caso contrario
    "order_type": string | null,     // uno de: "quotation", "confirmed",
                                     // "delivery_followup", "cancelled", "unclear"
    "order_date": string | null,     // formato "YYYY-MM-DD" si se puede deducir, si no null
    "city": string | null,           // ciudad si se menciona (ej: "Medellín", "Bogotá")
    "address": string | null,        // dirección textual o instrucciones detalladas de entrega
    "payment_method": string | null, // ej: "Nequi", "Daviplata", "transferencia", "efectivo"
    "approx_total": number | null,   // valor total aproximado si se menciona (sin puntos de mil),
                                     // por ejemplo 45000. Si no se menciona, null.
    "products": [
      {
        "name": string,              // ej: "Muffins", "Arepas de maíz"
        "variant": string | null,    // ej: "chocolate", "integrales", "sin azúcar"
        "presentation": string | null, // ej: "caja x6", "paquete x10"
        "quantity_units": number | null, // cantidad de unidades o cajas, ej: 2
        "unit": string | null,       // ej: "caja", "unidad", "paquete"
        "unit_price_approx": number | null // precio aproximado por unidad o caja
      }
    ]
  }
}

CRITERIOS DETALLADOS PARA "has_order":

Marca "has_order": true si se cumple ALGUNA de estas condiciones:

1) INTENCIÓN CLARA DE COMPRA / CONFIRMACIÓN:
   - El cliente expresa claramente que quiere comprar, pedir, encargar o reservar productos.
     Ejemplos:
     - "Quiero hacer un pedido"
     - "Entonces mándame 2 cajas"
     - "Te encargo 3 paquetes para mañana"
     - "Sí, déjalo así, confírmame el pedido"
     - "Listo, me quedo con esos"

2) DETALLE DE PRODUCTOS + CANTIDAD (aunque no haya total):
   - Se acuerdan productos y cantidades concretas, incluso si no hay precio final.
     Ejemplos:
     - "Serían 2 cajas de muffins y 1 de brownies"
     - "Déjame 10 arepas integrales"
     - "Apúntame 3 paquetes para el viernes"

3) PROCESO DE ENTREGA (DIRECCIÓN O INSTRUCCIONES ESPECÍFICAS):
   - Hay una coordinación clara de entrega, incluyendo al menos una dirección,
     barrio, edificio, apartamento, local, referencia o punto de encuentro.
   - O se dan instrucciones específicas de entrega.
     Ejemplos:
     - "Es en el barrio Laureles, carrera 80 #xx-xx, apto 302"
     - "Entrégalo en el edificio X, torre 2, portería"
     - "Te espero en la portería del conjunto Y"
     - "Nos vemos en la estación del metro Floresta"
   - Si aparecen estas instrucciones junto con productos/cantidades, considéralo pedido.

4) PROCESO DE PAGO / TRANSFERENCIA:
   - Se menciona pago realizado o por realizar, con método concreto:
     Ejemplos:
     - "¿Por dónde te puedo pagar?"
     - "Te hago la transferencia por Nequi"
     - "Ya te envié el comprobante"
     - "Listo, ya te transferí"
     - "Te pago en efectivo cuando llegue"
   - Si se habla de pago y también hay productos/cantidades o entrega, es pedido.

5) SEGUIMIENTO A UN PEDIDO EXISTENTE (DELIVERY FOLLOW-UP):
   - Hablan de un pedido ya hecho y su entrega:
     Ejemplos:
     - "A qué hora llega el pedido?"
     - "El domiciliario ya viene en camino"
     - "El pedido llegó bien, gracias"
     - "No me ha llegado todavía"
   - En estos casos, usar order_type: "delivery_followup" y has_order: true.

Marca "has_order": false cuando:

- Solo piden información, catálogo, fotos o precios, sin confirmar ni cantidades.
  Ejemplos:
  - "¿Qué productos tienes?"
  - "Mándame la carta y los precios"
- Hay conversación amigable o de interés, pero sin decisión clara de compra.
- Hay dudas o comparaciones, pero NO hay:
  - Confirmación del cliente,
  - Ni productos + cantidades,
  - Ni dirección/instrucciones concretas,
  - Ni proceso de pago.

CRITERIOS PARA "order_type":

- "quotation":
  - Solo se piden precios o información.
  - Puede haber productos mencionados, pero el cliente NO confirma el pedido.
  - No hay dirección ni pago ni instrucciones de entrega.

- "confirmed":
  - El cliente confirma que quiere el pedido (o continúa un pedido ya acordado),
    CON ALGUNO de estos elementos:
    - Productos + cantidades claras,
    - Y/O dirección o instrucciones de entrega,
    - Y/O método de pago o confirmación de pago.

- "delivery_followup":
  - La conversación trata sobre el estado, entrega o recepción de un pedido ya hecho.

- "cancelled":
  - El cliente cancela el pedido o dice que ya no lo necesita.
    Ej:
    - "Mejor cancélalo"
    - "Ya no lo necesito, gracias"

- "unclear":
  - Hay señales de posible pedido pero insuficientes para estar seguro.

REGLAS DE EXTRACCIÓN:

- "order_date":
  - Usa una fecha explícita si aparece y conviértela a "YYYY-MM-DD" si puedes.
  - Si no se puede deducir, usa null.

- "city":
  - Solo llena si se menciona claramente (ej: "Medellín", "Bogotá", "Envigado").
  - No asumas ciudad por defecto; si no se ve, pon null.

- "address":
  - Pon aquí la dirección completa o texto donde se dan instrucciones de ubicación,
    aunque no sea un formato formal de dirección.

- "payment_method":
  - Llena solo si se menciona explícitamente (Nequi, Daviplata, Bancolombia, tarjeta, efectivo, etc.).
  - Si solo se dice "transferencia" sin especificar, puedes usar "transferencia".

- "products":
  - Cada tipo de producto debe ser un objeto en el array.
  - "name": tipo general (ej: "Muffins", "Arepas", "Brownies").
  - "variant": sabor o atributo (ej: "chocolate", "integrales", "sin azúcar").
  - "presentation": paquete/caja, si se menciona (ej: "caja x6", "paquete x10").
  - "quantity_units": número de cajas/paquetes/unidades, si se menciona.
  - "unit": tipo de cantidad (ej: "caja", "unidad", "paquete").
  - "unit_price_approx": llénalo solo si se ve claramente el precio por unidad/caja.

SIEMPRE:
- Devuelve un JSON válido con TODOS los campos indicados.
- Si no hay pedido (has_order = false), igual devuelve el objeto "order"
  con "order_type" adecuado ("quotation" o "unclear") y el resto de campos en null o [].
- NO agregues ningún texto fuera del JSON.
"""

MAX_CONCURRENT = 5  # Límite de llamadas concurrentes a la API
MAX_RETRIES = 5  # Reintentos en caso de rate limit
RETRY_BASE_DELAY = 1.0  # Segundos base para backoff exponencial


# ─────────────────────────────────────────────────────────────────────────────
# Funciones de análisis
# ─────────────────────────────────────────────────────────────────────────────


def cargar_conversaciones(limit: int | None = None) -> list[dict]:
    """Carga conversaciones desde el archivo JSONL."""
    conversaciones = []
    with CONVERSACIONES_FILE.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if limit and i >= limit:
                break
            conversaciones.append(json.loads(line))
    return conversaciones


def formatear_conversacion(conv: dict) -> str:
    """Convierte una conversación a texto legible para el LLM."""
    lines = [
        f"CONVERSATION_ID: {conv.get('conversation_id', 'desconocido')}",
        f"CLIENT_ID: {conv.get('client_id', 'desconocido')}",
    ]
    for msg in conv.get("messages", []):
        role = "Cliente" if msg["role"] == "user" else "Negocio"
        content = msg.get("content", "").strip()
        timestamp = msg.get("timestamp", "")
        if content:
            # Incluir fecha/hora para que el LLM pueda extraer order_date
            if timestamp:
                lines.append(f"[{timestamp}] {role}: {content}")
            else:
                lines.append(f"{role}: {content}")
    return "\n".join(lines)


async def analizar_conversacion(
    client: AsyncOpenAI,
    conv: dict,
    semaphore: asyncio.Semaphore,
) -> dict:
    """Analiza una conversación con el LLM, con retry en caso de rate limit."""
    async with semaphore:
        texto = formatear_conversacion(conv)
        resultado = None

        for attempt in range(MAX_RETRIES):
            try:
                response = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": texto},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0,
                    max_tokens=1000,
                )

                resultado = json.loads(response.choices[0].message.content)
                break  # Éxito, salir del loop

            except Exception as e:
                error_str = str(e)
                # Si es rate limit, hacer retry con backoff
                if "429" in error_str or "rate_limit" in error_str.lower():
                    delay = RETRY_BASE_DELAY * (2 ** attempt)  # Backoff exponencial
                    await asyncio.sleep(delay)
                    continue
                else:
                    # Otro tipo de error, no reintentar
                    print(f"  ⚠️  Error en {conv.get('session_id', '?')}: {e}")
                    resultado = {"error": error_str}
                    break

        if resultado is None:
            resultado = {"error": "Max retries exceeded (rate limit)"}

        # Agregar metadatos de la conversación original
        resultado["_session_id"] = conv.get("session_id")
        resultado["_conversation_id"] = conv.get("conversation_id")
        resultado["_client_id"] = conv.get("client_id")

        return resultado


async def procesar_batch(conversaciones: list[dict]) -> list[dict]:
    """Procesa un lote de conversaciones en paralelo."""
    load_dotenv(BASE_DIR / ".env", override=True)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("❌ OPENAI_API_KEY no configurada en .env")

    client = AsyncOpenAI(api_key=api_key)
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    tasks = [
        analizar_conversacion(client, conv, semaphore) for conv in conversaciones
    ]

    resultados = []
    total = len(tasks)

    for i, coro in enumerate(asyncio.as_completed(tasks), 1):
        resultado = await coro
        resultados.append(resultado)
        print(f"\r  Procesando: {i}/{total}", end="", flush=True)

    print()
    return resultados


def guardar_resultados(resultados: list[dict]) -> None:
    """Guarda los resultados en archivo JSONL."""
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Guardar análisis completo
    output_file = EXPORTS_DIR / "ventas_llm.jsonl"
    with output_file.open("w", encoding="utf-8") as f:
        for r in resultados:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  📄 Resultados: {output_file}")

    # Contar resultados válidos (sin error)
    validos = [r for r in resultados if "error" not in r]
    print(f"  ✓ {len(validos)} conversaciones analizadas correctamente")
    print(f"  ✗ {len(resultados) - len(validos)} con errores")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Extrae ventas con LLM")
    parser.add_argument(
        "--limit", type=int, default=None, help="Procesar solo N conversaciones"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Solo mostrar qué se procesaría"
    )
    args = parser.parse_args()

    if not CONVERSACIONES_FILE.exists():
        raise SystemExit(f"❌ No existe: {CONVERSACIONES_FILE}")

    print("🔍 Cargando conversaciones...")
    conversaciones = cargar_conversaciones(limit=args.limit)
    print(f"  {len(conversaciones)} conversaciones cargadas")

    if args.dry_run:
        print("\n📋 Modo dry-run. Ejemplo de conversación a procesar:")
        if conversaciones:
            print("-" * 40)
            print(formatear_conversacion(conversaciones[0]))
            print("-" * 40)
        return

    print("\n🤖 Analizando con GPT-4o-mini...")
    resultados = asyncio.run(procesar_batch(conversaciones))

    print("\n💾 Guardando resultados...")
    guardar_resultados(resultados)

    print("\n✅ Proceso completado")


if __name__ == "__main__":
    main()
