# Inversiones

Original definitions (from inversiones.txt):

1. Table Instrumento
2. id: guid
3. nombre: varchar 256
4. codigo: varchar 50 optional
5. tipo: 'CEDEAR', 'FCI', 'ON', 'ACCION_LOCAL', 'ACCION_INTERNACIONAL', 'BONO', 'FCI_EXTERIOR', 'ETF'
6. clase_renta: 'FIJA', 'VARIABLE'
7. broker: varchar 256
8. active: boolean

Table Precio

- id: guid
- active: boolean
- monto: numeric 12,2
- fecha: timestamp
- Instrumento: FK table Instrumento
- moneda: 'PESO', 'DOLAR'

Table Inversion

- id
- active
- cantidad: numeric
- instrumento: FK Instrumento
- broker: varchar 256
- fecha: timestamp (opcional)

---

## SQL scripts

Run these scripts in a PostgreSQL database. They create schema `inversiones` and the tables. The scripts use the pgcrypto extension for gen_random_uuid().

### Instrumento (docs/01_instrumento.sql)

```sql
-- Schema and extension (safe to run multiple times)
CREATE SCHEMA IF NOT EXISTS inversiones;
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Table: inversiones.instrumento
CREATE TABLE IF NOT EXISTS inversiones.instrumento (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre VARCHAR(256) NOT NULL,
  codigo VARCHAR(50),
  tipo VARCHAR(30) NOT NULL CHECK (tipo IN ('CEDEAR','FCI','ON','ACCION_LOCAL','ACCION_INTERNACIONAL','BONO','FCI_EXTERIOR','ETF')),
  clase_renta VARCHAR(10) NOT NULL CHECK (clase_renta IN ('FIJA','VARIABLE')),
  broker VARCHAR(256),
  moneda VARCHAR(10) NOT NULL CHECK (moneda IN ('PESO','DOLAR')),
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Optional: index on codigo for fast lookup
CREATE INDEX IF NOT EXISTS idx_instrumento_codigo ON inversiones.instrumento(codigo);
```

### Precio (docs/02_precio.sql)

```sql
-- Ensure schema and extension exist
CREATE SCHEMA IF NOT EXISTS inversiones;
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Table: inversiones.precio
CREATE TABLE IF NOT EXISTS inversiones.precio (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  active BOOLEAN NOT NULL DEFAULT TRUE,
  monto NUMERIC(12,2) NOT NULL,
  fecha TIMESTAMP WITH TIME ZONE NOT NULL,
  instrumento_id UUID NOT NULL REFERENCES inversiones.instrumento(id) ON DELETE CASCADE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_precio_instrumento_fecha ON inversiones.precio(instrumento_id, fecha DESC);
```

### Inversion (docs/03_inversion.sql)

```sql
-- Ensure schema and extension exist
CREATE SCHEMA IF NOT EXISTS inversiones;
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Table: inversiones.inversion
CREATE TABLE IF NOT EXISTS inversiones.inversion (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  active BOOLEAN NOT NULL DEFAULT TRUE,
  cantidad NUMERIC NOT NULL,
  instrumento_id UUID NOT NULL REFERENCES inversiones.instrumento(id),
  broker VARCHAR(256),
  fecha TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);
```

---

Notes:

- If the database does not have pgcrypto available, replace gen_random_uuid() with uuid_generate_v4() and enable the uuid-ossp extension instead.
- Adjust numeric precision for `cantidad` if required.
