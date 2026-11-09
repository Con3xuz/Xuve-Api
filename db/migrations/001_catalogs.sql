-- =====================================================================
-- 001_catalogs.sql  -  Catálogos y configuración (antes hardcodeados en el código)
-- Idempotente: se puede ejecutar N veces. Los datos iniciales usan
-- ON CONFLICT DO NOTHING, así que NO pisan lo que el admin ya editó.
-- =====================================================================
CREATE SCHEMA IF NOT EXISTS xuve;

-- ---------- Categorías de comercio ----------
CREATE TABLE IF NOT EXISTS xuve.business_categories (
    slug        TEXT PRIMARY KEY,
    label       TEXT    NOT NULL,
    icon        TEXT    NOT NULL DEFAULT 'building',
    color       TEXT    NOT NULL DEFAULT '#94A3B8',
    emoji       TEXT    NOT NULL DEFAULT '🏢',
    sort_order  INTEGER NOT NULL DEFAULT 0,
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- ---------- Categorías de producto por tipo de tienda ----------
CREATE TABLE IF NOT EXISTS xuve.product_categories (
    id            BIGSERIAL PRIMARY KEY,
    store_type    TEXT    NOT NULL,
    name          TEXT    NOT NULL,
    icon          TEXT,
    subcategories JSONB   NOT NULL DEFAULT '[]'::jsonb,
    sort_order    INTEGER NOT NULL DEFAULT 0,
    active        BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (store_type, name)
);

-- ---------- Parámetros de plataforma (comisiones, fees, tasas, etc.) ----------
CREATE TABLE IF NOT EXISTS xuve.platform_settings (
    key         TEXT PRIMARY KEY,
    value       JSONB NOT NULL,
    group_name  TEXT  NOT NULL DEFAULT 'general',
    description TEXT,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    updated_by  TEXT
);

-- ---------- Tarifas planas de carga pesada ----------
CREATE TABLE IF NOT EXISTS xuve.cargo_rates (
    service_type TEXT    NOT NULL,   -- cisterna | flete | mudanza | ayudante
    tier         TEXT    NOT NULL,   -- litros (cisterna) | pequeño/mediano/grande | extra
    amount_usd   NUMERIC(12,2) NOT NULL,
    active       BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (service_type, tier)
);

INSERT INTO xuve.business_categories (slug,label,icon,color,emoji,sort_order) VALUES
  ('restaurante', 'Restaurante', 'utensils', '#F97316', '🍽️', 0),
  ('comida_rapida', 'Comida Rápida', 'burger', '#EF4444', '🍔', 1),
  ('panaderia', 'Panadería', 'cake', '#F59E0B', '🥐', 2),
  ('farmacia', 'Farmacia', 'pill', '#10B981', '💊', 3),
  ('minimarket', 'Minimarket', 'store', '#3B82F6', '🏪', 4),
  ('supermercado', 'Supermercado', 'shopping-cart', '#6366F1', '🛒', 5),
  ('ferreteria', 'Ferretería', 'wrench', '#71717A', '🔧', 6),
  ('tecnologia', 'Tecnología', 'laptop', '#8B5CF6', '💻', 7),
  ('ropa', 'Ropa y Accesorios', 'shirt', '#EC4899', '👕', 8),
  ('belleza', 'Belleza y Cuidado', 'sparkles', '#F472B6', '💄', 9),
  ('mascotas', 'Mascotas', 'paw', '#84CC16', '🐾', 10),
  ('licoreria', 'Licorería', 'wine', '#A855F7', '🍷', 11),
  ('viveres', 'Víveres', 'package', '#22C55E', '📦', 12),
  ('otros', 'Otros', 'building', '#94A3B8', '🏢', 13)
ON CONFLICT (slug) DO NOTHING;

INSERT INTO xuve.product_categories (store_type,name,icon,subcategories,sort_order) VALUES
  ('farmacia', 'Medicamentos', '💊', '["Con receta", "Sin receta", "Genéricos", "De marca"]'::jsonb, 0),
  ('farmacia', 'Cuidado Personal', '🧴', '["Higiene", "Cuidado facial", "Cuidado corporal", "Cabello"]'::jsonb, 1),
  ('farmacia', 'Bebés y Niños', '👶', '["Pañales", "Alimentación", "Cuidado", "Juguetes"]'::jsonb, 2),
  ('farmacia', 'Vitaminas y Suplementos', '💪', '["Vitaminas", "Minerales", "Proteínas", "Naturales"]'::jsonb, 3),
  ('farmacia', 'Primeros Auxilios', '🩹', '["Vendajes", "Antisépticos", "Termómetros", "Equipos"]'::jsonb, 4),
  ('farmacia', 'Belleza', '💄', '["Maquillaje", "Perfumes", "Uñas", "Accesorios"]'::jsonb, 5),
  ('farmacia', 'Equipos Médicos', '🏥', '["Monitores", "Nebulizadores", "Sillas de ruedas", "Otros"]'::jsonb, 6),
  ('restaurante', 'Entradas', '🥗', '["Ensaladas", "Sopas", "Aperitivos"]'::jsonb, 0),
  ('restaurante', 'Platos Principales', '🍽️', '["Carnes", "Pollo", "Pescados", "Vegetarianos"]'::jsonb, 1),
  ('restaurante', 'Bebidas', '🥤', '["Refrescos", "Jugos", "Calientes", "Alcohólicas"]'::jsonb, 2),
  ('restaurante', 'Postres', '🍰', '["Tortas", "Helados", "Frutas"]'::jsonb, 3),
  ('restaurante', 'Combos', '🍱', '["Individuales", "Familiares", "Especiales"]'::jsonb, 4),
  ('supermercado', 'Frutas y Verduras', '🥬', '["Frutas", "Verduras", "Orgánicos"]'::jsonb, 0),
  ('supermercado', 'Carnes y Pescados', '🥩', '["Res", "Pollo", "Cerdo", "Pescados", "Mariscos"]'::jsonb, 1),
  ('supermercado', 'Lácteos', '🥛', '["Leche", "Quesos", "Yogurt", "Mantequilla"]'::jsonb, 2),
  ('supermercado', 'Panadería', '🥖', '["Pan", "Dulces", "Tortas"]'::jsonb, 3),
  ('supermercado', 'Bebidas', '🧃', '["Agua", "Refrescos", "Jugos", "Cervezas"]'::jsonb, 4),
  ('supermercado', 'Limpieza', '🧹', '["Hogar", "Ropa", "Personal"]'::jsonb, 5),
  ('general', 'Productos', '📦', '["General"]'::jsonb, 0)
ON CONFLICT (store_type,name) DO NOTHING;

INSERT INTO xuve.platform_settings (key,value,group_name,description) VALUES
  ('activation_fee', '1.0'::jsonb, 'wallet', 'Fee de activación de socio (USD)'),
  ('min_balance_activate', '5.0'::jsonb, 'wallet', 'Saldo mínimo para activarse (USD)'),
  ('min_balance_connect', '1.0'::jsonb, 'wallet', 'Saldo mínimo para conectarse (USD)'),
  ('heavy_transport_commission', '0.1'::jsonb, 'carga', 'Comisión carga pesada (fracción)'),
  ('min_balance_heavy_transport', '10.0'::jsonb, 'carga', 'Saldo mínimo recomendado carga pesada (USD)'),
  ('exchange_rate', '50.0'::jsonb, 'fx', 'Tasa USD/VES'),
  ('toll_moto', '0.5'::jsonb, 'tolls', 'Peaje moto (USD)'),
  ('toll_others', '1.0'::jsonb, 'tolls', 'Peaje otros vehículos (USD)'),
  ('daily_subscription_fee', '1.0'::jsonb, 'subscription', 'Suscripción diaria (USD)'),
  ('free_trial_days', '3'::jsonb, 'subscription', 'Días de prueba gratis'),
  ('delivery_fee_base', '2.0'::jsonb, 'fees', 'Fee base de delivery (USD)'),
  ('line_activation_fee', '5.0'::jsonb, 'fees', 'Fee de activación de líneas (USD)'),
  ('commission_transport', '0.1'::jsonb, 'commissions', 'Comisión transport (fracción)'),
  ('commission_market', '0.12'::jsonb, 'commissions', 'Comisión market (fracción)'),
  ('commission_rent', '0.1'::jsonb, 'commissions', 'Comisión rent (fracción)'),
  ('commission_interurbano', '0.1'::jsonb, 'commissions', 'Comisión interurbano (fracción)'),
  ('commission_linea', '0.1'::jsonb, 'commissions', 'Comisión linea (fracción)'),
  ('urban_fee_fixed', '0.02'::jsonb, 'fees', 'Fee fijo transporte urbano (USD)'),
  ('fare_min_moto', '1.0'::jsonb, 'fares', 'Tarifa de viaje: fare_min_moto'),
  ('fare_min_auto', '2.0'::jsonb, 'fares', 'Tarifa de viaje: fare_min_auto'),
  ('fare_per_km_moto', '0.3'::jsonb, 'fares', 'Tarifa de viaje: fare_per_km_moto'),
  ('fare_per_km_auto', '0.5'::jsonb, 'fares', 'Tarifa de viaje: fare_per_km_auto')
ON CONFLICT (key) DO NOTHING;

INSERT INTO xuve.cargo_rates (service_type,tier,amount_usd) VALUES
  ('cisterna', '5000', 20.00),
  ('cisterna', '10000', 30.00),
  ('cisterna', '15000', 40.00),
  ('cisterna', '20000', 50.00),
  ('flete', 'pequeño', 15.00),
  ('flete', 'mediano', 25.00),
  ('flete', 'grande', 40.00),
  ('mudanza', 'pequeño', 30.00),
  ('mudanza', 'mediano', 50.00),
  ('mudanza', 'grande', 80.00),
  ('ayudante', 'extra', 5.00)
ON CONFLICT (service_type,tier) DO NOTHING;
