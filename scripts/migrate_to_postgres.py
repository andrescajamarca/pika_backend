#!/usr/bin/env python3
"""
Script para migrar datos JSON a PostgreSQL
Tablas: clients, orders, products, order_items
Ejecutar después de tener el contenedor de PostgreSQL corriendo.
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    print("Error: psycopg2 no está instalado.")
    print("Instala con: pip install psycopg2-binary")
    sys.exit(1)

# Configuración de conexión (usa variables de entorno o valores por defecto)
DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": os.getenv("POSTGRES_PORT", "5432"),
    "database": os.getenv("POSTGRES_DB", "pika_db"),
    "user": os.getenv("POSTGRES_USER", "pika_user"),
    "password": os.getenv("POSTGRES_PASSWORD", "pika_secret_2024"),
}

# Rutas de datos
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
TABLES_DIR = DATA_DIR / "exports" / "tables"


def get_connection():
    """Crear conexión a PostgreSQL"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = False
        return conn
    except psycopg2.Error as e:
        print(f"Error conectando a PostgreSQL: {e}")
        sys.exit(1)


def load_json(filepath: Path) -> list:
    """Cargar archivo JSON"""
    if not filepath.exists():
        print(f"Archivo no encontrado: {filepath}")
        return []
    
    with open(filepath, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error parseando JSON: {e}")
            return []


def migrate_clients(conn):
    """Migrar clientes desde clients.json"""
    print("\n👥 Migrando clients...")
    filepath = TABLES_DIR / "clients.json"
    clients = load_json(filepath)
    
    if not clients:
        print("  No hay clientes para migrar")
        return 0
    
    cursor = conn.cursor()
    count = 0
    
    for client in clients:
        # Parsear fecha
        created_at = None
        if client.get("created_at"):
            try:
                created_at = datetime.fromisoformat(client["created_at"])
            except ValueError:
                created_at = None
        
        cursor.execute(
            """
            INSERT INTO clients (id, phone, name, source_client_id, created_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                phone = COALESCE(EXCLUDED.phone, clients.phone),
                name = COALESCE(EXCLUDED.name, clients.name),
                source_client_id = EXCLUDED.source_client_id
            """,
            (
                client.get("id"),
                client.get("phone"),
                client.get("name"),
                client.get("source_client_id"),
                created_at,
            )
        )
        count += 1
    
    conn.commit()
    print(f"  ✅ {count} clientes migrados")
    return count


def migrate_orders(conn):
    """Migrar pedidos desde orders.json"""
    print("\n📦 Migrando orders...")
    filepath = TABLES_DIR / "orders.json"
    orders = load_json(filepath)
    
    if not orders:
        print("  No hay pedidos para migrar")
        return 0
    
    cursor = conn.cursor()
    count = 0
    
    for order in orders:
        # Parsear fecha de pedido
        order_date = None
        if order.get("order_date"):
            try:
                order_date = datetime.strptime(order["order_date"], "%Y-%m-%d").date()
            except ValueError:
                order_date = None
        
        # Parsear created_at
        created_at = None
        if order.get("created_at"):
            try:
                created_at = datetime.fromisoformat(order["created_at"])
            except ValueError:
                created_at = None
        
        cursor.execute(
            """
            INSERT INTO orders (id, client_id, order_date, city, address, payment_method, total, status, source_session_id, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                client_id = EXCLUDED.client_id,
                order_date = EXCLUDED.order_date,
                city = EXCLUDED.city,
                address = EXCLUDED.address,
                payment_method = EXCLUDED.payment_method,
                total = EXCLUDED.total,
                status = EXCLUDED.status,
                source_session_id = EXCLUDED.source_session_id
            """,
            (
                order.get("id"),
                order.get("client_id"),
                order_date,
                order.get("city"),
                order.get("address"),
                order.get("payment_method"),
                order.get("total"),
                order.get("status", "pending"),
                order.get("source_session_id"),
                created_at,
            )
        )
        count += 1
    
    conn.commit()
    print(f"  ✅ {count} pedidos migrados")
    return count


def migrate_products(conn):
    """Migrar catálogo de productos desde products.json"""
    print("\n🍿 Migrando products...")
    filepath = TABLES_DIR / "products.json"
    products = load_json(filepath)
    
    if not products:
        print("  No hay productos para migrar")
        return 0
    
    cursor = conn.cursor()
    count = 0
    
    for product in products:
        cursor.execute(
            """
            INSERT INTO products (id, name, variant)
            VALUES (%s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                variant = EXCLUDED.variant
            """,
            (
                product.get("id"),
                product.get("name"),
                product.get("variant"),
            )
        )
        count += 1
    
    conn.commit()
    print(f"  ✅ {count} productos migrados")
    return count


def migrate_order_items(conn):
    """Migrar items de pedido desde order_items.json"""
    print("\n🛒 Migrando order_items...")
    filepath = TABLES_DIR / "order_items.json"
    items = load_json(filepath)
    
    if not items:
        print("  No hay items para migrar")
        return 0
    
    cursor = conn.cursor()
    count = 0
    
    skipped = 0
    for item in items:
        # Filtrar items sin product_name
        if not item.get("product_name"):
            skipped += 1
            continue
        
        cursor.execute(
            """
            INSERT INTO order_items (id, order_id, product_name, variant, quantity, unit, unit_price)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                order_id = EXCLUDED.order_id,
                product_name = EXCLUDED.product_name,
                variant = EXCLUDED.variant,
                quantity = EXCLUDED.quantity,
                unit = EXCLUDED.unit,
                unit_price = EXCLUDED.unit_price
            """,
            (
                item.get("id"),
                item.get("order_id"),
                item.get("product_name", ""),
                item.get("variant"),
                item.get("quantity", 1),
                item.get("unit"),
                item.get("unit_price"),
            )
        )
        count += 1
    
    conn.commit()
    print(f"  ✅ {count} items migrados")
    if skipped:
        print(f"  ⚠️  {skipped} items omitidos (sin product_name)")
    return count


def show_stats(conn):
    """Mostrar estadísticas de la base de datos"""
    print("\n📊 Estadísticas de la base de datos:")
    cursor = conn.cursor()
    
    tables = ["clients", "orders", "products", "order_items"]
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  • {table}: {count} registros")
    
    # Mostrar algunas estadísticas adicionales
    print("\n📈 Estadísticas adicionales:")
    
    # Total de ventas
    cursor.execute("SELECT COALESCE(SUM(total), 0) FROM orders WHERE total IS NOT NULL")
    total_sales = cursor.fetchone()[0]
    print(f"  • Total ventas: ${total_sales:,.0f} COP")
    
    # Producto más vendido
    cursor.execute("""
        SELECT product_name, SUM(quantity) as total_qty 
        FROM order_items 
        WHERE product_name != '' 
        GROUP BY product_name 
        ORDER BY total_qty DESC 
        LIMIT 1
    """)
    top_product = cursor.fetchone()
    if top_product:
        print(f"  • Producto más vendido: {top_product[0]} ({top_product[1]} unidades)")


def main():
    print("=" * 50)
    print("🚀 Migración de datos a PostgreSQL")
    print("   Tablas: clients, orders, products, order_items")
    print("=" * 50)
    print(f"\nConectando a: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    print(f"Datos desde: {TABLES_DIR}")
    
    conn = get_connection()
    print("✅ Conexión establecida")
    
    try:
        migrate_clients(conn)
        migrate_orders(conn)
        migrate_products(conn)
        migrate_order_items(conn)
        show_stats(conn)
        
        print("\n" + "=" * 50)
        print("✅ Migración completada exitosamente!")
        print("=" * 50)
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error durante la migración: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
