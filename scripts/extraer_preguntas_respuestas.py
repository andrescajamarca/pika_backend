"""
Extrae FAQs, ventas y datos de clientes de conversaciones usando GPT-4o-mini.

Uso:
    python scripts/extraer_preguntas_respuestas.py [--limit N] [--dry-run]

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

SYSTEM_PROMPT = """\
Eres un analista de datos que extrae información estructurada de conversaciones de WhatsApp de una tienda de snacks saludables (Pika Snacks).

Analiza la conversación y extrae:

1. **faqs**: Lista de preguntas frecuentes detectadas. Solo incluye si el cliente hace una pregunta clara y el negocio responde.
   Cada FAQ tiene:
   - "pregunta": La pregunta del cliente (normalizada, sin errores ortográficos)
   - "respuesta": La respuesta del negocio
   - "categoria": Una de [info_general, ubicacion, envio, precios, productos, proceso_compra, diabeticos, horarios, otro]

2. **venta**: Si detectas indicios de una venta/pedido, extrae:
   - "productos": Lista de productos mencionados
   - "direccion": Dirección de entrega si se menciona
   - "total": Monto total si se menciona (número sin símbolo)
   - "metodo_pago": Método de pago si se menciona (efectivo, nequi, transferencia, etc.)
   - "estado": "confirmada" si hay confirmación clara de envío/entrega, "probable" si hay indicios pero no cierre
   Si no hay venta, devuelve null.

3. **cliente**: Información del cliente si se menciona:
   - "nombre": Nombre del cliente
   - "telefono": Teléfono (ya está en client_id, pero si mencionan otro)
   - "ciudad": Ciudad o barrio
   - "notas": Cualquier preferencia o nota relevante (ej: "es diabético", "cliente frecuente")
   Si no hay info adicional, devuelve null.

Responde ÚNICAMENTE con un objeto JSON válido con las claves: faqs, venta, cliente.
Si no hay FAQs, devuelve una lista vacía para faqs."""

MAX_CONCURRENT = 10  # Límite de llamadas concurrentes a la API


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
    lines = [f"Cliente ID: {conv.get('client_id', 'desconocido')}"]
    for msg in conv.get("messages", []):
        role = "Cliente" if msg["role"] == "user" else "Negocio"
        content = msg.get("content", "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


async def analizar_conversacion(
    client: AsyncOpenAI,
    conv: dict,
    semaphore: asyncio.Semaphore,
) -> dict:
    """Analiza una conversación con el LLM."""
    async with semaphore:
        texto = formatear_conversacion(conv)

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

        except Exception as e:
            print(f"  ⚠️  Error en {conv.get('session_id', '?')}: {e}")
            resultado = {"faqs": [], "venta": None, "cliente": None, "error": str(e)}

        # Agregar metadatos de la conversación original
        resultado["_session_id"] = conv.get("session_id")
        resultado["_conversation_id"] = conv.get("conversation_id")
        resultado["_client_id"] = conv.get("client_id")

        return resultado


async def procesar_batch(conversaciones: list[dict]) -> list[dict]:
    """Procesa un lote de conversaciones en paralelo."""
    # Recargar .env por si acaso
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

    # Procesar con barra de progreso simple
    for i, coro in enumerate(asyncio.as_completed(tasks), 1):
        resultado = await coro
        resultados.append(resultado)
        print(f"\r  Procesando: {i}/{total}", end="", flush=True)

    print()  # Nueva línea después del progreso
    return resultados


def guardar_resultados(resultados: list[dict]) -> None:
    """Guarda los resultados en archivos separados."""
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Guardar análisis completo (para debug)
    raw_file = EXPORTS_DIR / "analisis_raw.jsonl"
    with raw_file.open("w", encoding="utf-8") as f:
        for r in resultados:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  📄 Análisis completo: {raw_file}")

    # 2. Extraer y agrupar FAQs
    faqs_counter: dict[str, dict] = {}  # pregunta -> {respuesta, categoria, count}
    for r in resultados:
        for faq in r.get("faqs", []):
            pregunta = faq.get("pregunta", "").strip().lower()
            if not pregunta:
                continue
            if pregunta not in faqs_counter:
                faqs_counter[pregunta] = {
                    "pregunta": faq.get("pregunta", ""),
                    "respuesta": faq.get("respuesta", ""),
                    "categoria": faq.get("categoria", "otro"),
                    "frecuencia": 0,
                }
            faqs_counter[pregunta]["frecuencia"] += 1

    # Ordenar por frecuencia
    faqs_sorted = sorted(faqs_counter.values(), key=lambda x: -x["frecuencia"])

    faq_file = EXPORTS_DIR / "faq.jsonl"
    with faq_file.open("w", encoding="utf-8") as f:
        for faq in faqs_sorted:
            f.write(json.dumps(faq, ensure_ascii=False) + "\n")
    print(f"  📄 FAQs ({len(faqs_sorted)} únicas): {faq_file}")

    # 3. Extraer ventas
    ventas = []
    for r in resultados:
        venta = r.get("venta")
        if venta:
            venta["session_id"] = r.get("_session_id")
            venta["client_id"] = r.get("_client_id")
            ventas.append(venta)

    ventas_file = EXPORTS_DIR / "ventas.jsonl"
    with ventas_file.open("w", encoding="utf-8") as f:
        for v in ventas:
            f.write(json.dumps(v, ensure_ascii=False) + "\n")
    print(f"  📄 Ventas detectadas ({len(ventas)}): {ventas_file}")

    # 4. Extraer info de clientes
    clientes = []
    for r in resultados:
        cliente = r.get("cliente")
        if cliente:
            cliente["client_id"] = r.get("_client_id")
            clientes.append(cliente)

    clientes_file = EXPORTS_DIR / "clientes.jsonl"
    with clientes_file.open("w", encoding="utf-8") as f:
        for c in clientes:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"  📄 Info de clientes ({len(clientes)}): {clientes_file}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Extrae FAQs y ventas con LLM")
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
