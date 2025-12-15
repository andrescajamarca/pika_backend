import asyncpg
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from .config import config


class Database:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        """Crea el pool de conexiones."""
        self.pool = await asyncpg.create_pool(
            config.DATABASE_URL,
            min_size=2,
            max_size=10
        )
    
    async def disconnect(self):
        """Cierra el pool de conexiones."""
        if self.pool:
            await self.pool.close()
    
    @asynccontextmanager
    async def acquire(self):
        """Context manager para obtener una conexión."""
        async with self.pool.acquire() as conn:
            yield conn
    
    async def execute(self, query: str, *args) -> str:
        """Ejecuta una query sin retorno."""
        async with self.acquire() as conn:
            return await conn.execute(query, *args)
    
    async def fetch(self, query: str, *args) -> List[Dict[str, Any]]:
        """Ejecuta una query y retorna resultados."""
        async with self.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]
    
    async def fetchrow(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Ejecuta una query y retorna una fila."""
        async with self.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None
    
    async def fetchval(self, query: str, *args) -> Any:
        """Ejecuta una query y retorna un valor."""
        async with self.acquire() as conn:
            return await conn.fetchval(query, *args)


db = Database()


DB_SCHEMA_CONTEXT = """
## Esquema de Base de Datos PostgreSQL - Pika Snacks

### Tabla: clients
- id: UUID (PK, auto-generado)
- phone: VARCHAR(20) - Teléfono del cliente
- name: VARCHAR(255) - Nombre del cliente
- source_client_id: VARCHAR(255) UNIQUE NOT NULL - Identificador único externo
- created_at: TIMESTAMP
- updated_at: TIMESTAMP

### Tabla: orders
- id: UUID (PK, auto-generado)
- client_id: UUID (FK -> clients.id)
- order_date: DATE - Fecha del pedido
- city: VARCHAR(100) - Ciudad de entrega
- address: TEXT - Dirección de entrega
- payment_method: VARCHAR(50) - Método de pago
- total: DECIMAL(12,2) - Total del pedido
- status: VARCHAR(50) DEFAULT 'pending' - Estado: pending, confirmed, delivered, cancelled
- source_session_id: VARCHAR(255)
- created_at: TIMESTAMP
- updated_at: TIMESTAMP

### Tabla: products
- id: UUID (PK, auto-generado)
- name: VARCHAR(100) NOT NULL - Nombre del producto
- variant: VARCHAR(100) - Variante (sabor, tamaño, etc.)
- created_at: TIMESTAMP
- UNIQUE(name, variant)

### Tabla: order_items
- id: UUID (PK, auto-generado)
- order_id: UUID (FK -> orders.id)
- product_id: UUID (FK -> products.id)
- product_name: VARCHAR(255) NOT NULL
- variant: VARCHAR(255)
- quantity: INTEGER DEFAULT 1
- unit: VARCHAR(50) - Unidad: kg, unidad, paquete, etc.
- unit_price: DECIMAL(10,2)
- created_at: TIMESTAMP

### Vistas disponibles:
- v_client_summary: Resumen de clientes con total de pedidos
- v_orders_with_client: Pedidos con datos del cliente
- v_sales_by_month: Ventas agrupadas por mes
- v_top_products: Productos más vendidos
"""
