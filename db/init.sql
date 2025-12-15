-- Pika Snacks Database Schema
-- Inicialización automática al crear el contenedor
-- Basado en: clients.json, orders.json, order_items.json, products.json

-- Extensión para UUID
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Extensión para búsqueda de texto
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- =============================================
-- TABLA: clients (Clientes)
-- =============================================
CREATE TABLE IF NOT EXISTS clients (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone VARCHAR(20),
    name VARCHAR(255),
    source_client_id VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- TABLA: orders (Pedidos)
-- =============================================
CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
    order_date DATE,
    city VARCHAR(100),
    address TEXT,
    payment_method VARCHAR(50),
    total DECIMAL(12,2),
    status VARCHAR(50) DEFAULT 'pending',
    source_session_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- TABLA: products (Catálogo de productos)
-- =============================================
CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    variant VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, variant)
);

-- =============================================
-- TABLA: order_items (Items de pedido)
-- =============================================
CREATE TABLE IF NOT EXISTS order_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID REFERENCES orders(id) ON DELETE CASCADE,
    product_id UUID REFERENCES products(id) ON DELETE SET NULL,
    product_name VARCHAR(255) NOT NULL,
    variant VARCHAR(255),
    quantity INTEGER DEFAULT 1,
    unit VARCHAR(50),
    unit_price DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- ÍNDICES
-- =============================================
CREATE INDEX IF NOT EXISTS idx_clients_phone ON clients(phone);
CREATE INDEX IF NOT EXISTS idx_clients_name ON clients(name);
CREATE INDEX IF NOT EXISTS idx_clients_source_client_id ON clients(source_client_id);

CREATE INDEX IF NOT EXISTS idx_orders_client_id ON orders(client_id);
CREATE INDEX IF NOT EXISTS idx_orders_order_date ON orders(order_date);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_city ON orders(city);

CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);
CREATE INDEX IF NOT EXISTS idx_products_variant ON products(variant);

CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product_id ON order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product_name ON order_items(product_name);

-- =============================================
-- FUNCIÓN: Actualizar updated_at automáticamente
-- =============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers para updated_at
DROP TRIGGER IF EXISTS update_clients_updated_at ON clients;
CREATE TRIGGER update_clients_updated_at
    BEFORE UPDATE ON clients
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_orders_updated_at ON orders;
CREATE TRIGGER update_orders_updated_at
    BEFORE UPDATE ON orders
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================
-- VISTAS ÚTILES
-- =============================================

-- Vista: Resumen de clientes con total de pedidos
CREATE OR REPLACE VIEW v_client_summary AS
SELECT 
    c.id,
    c.name,
    c.phone,
    COUNT(o.id) as total_orders,
    COALESCE(SUM(o.total), 0) as total_spent,
    MAX(o.order_date) as last_order_date
FROM clients c
LEFT JOIN orders o ON c.id = o.client_id
GROUP BY c.id, c.name, c.phone;

-- Vista: Pedidos con detalle de cliente
CREATE OR REPLACE VIEW v_orders_with_client AS
SELECT 
    o.id as order_id,
    o.order_date,
    o.city,
    o.address,
    o.payment_method,
    o.total,
    o.status,
    c.name as client_name,
    c.phone as client_phone
FROM orders o
LEFT JOIN clients c ON o.client_id = c.id;

-- Vista: Ventas por mes
CREATE OR REPLACE VIEW v_sales_by_month AS
SELECT 
    DATE_TRUNC('month', order_date) as month,
    COUNT(*) as total_orders,
    COALESCE(SUM(total), 0) as total_revenue
FROM orders
WHERE order_date IS NOT NULL
GROUP BY DATE_TRUNC('month', order_date)
ORDER BY month DESC;

-- Vista: Productos más vendidos
CREATE OR REPLACE VIEW v_top_products AS
SELECT 
    product_name,
    variant,
    SUM(quantity) as total_quantity,
    COUNT(DISTINCT order_id) as order_count
FROM order_items
WHERE product_name IS NOT NULL AND product_name != ''
GROUP BY product_name, variant
ORDER BY total_quantity DESC;

-- =============================================
-- COMENTARIOS
-- =============================================
COMMENT ON TABLE clients IS 'Clientes de Pika Snacks';
COMMENT ON TABLE orders IS 'Pedidos realizados por clientes';
COMMENT ON TABLE products IS 'Catálogo de productos y variantes';
COMMENT ON TABLE order_items IS 'Items individuales de cada pedido';
