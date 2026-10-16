-- ============================================================================
-- Phase B Migration: railway_edges + road_edges + hot/warm node tiers
-- ============================================================================
-- SAFE MIGRATION GUARANTEE:
-- 1. All DDL runs inside a single transaction (BEGIN ... COMMIT).
-- 2. `edges` is renamed to `railway_edges` and replaced by a read-compatible
--    VIEW named `edges` with the exact same columns. Existing code calling
--    `supabase.table("edges").select("*")` continues to work untouched.
-- 3. `get_nodes_with_coords()` keeps its exact 5-column return signature
--    (id, name, lat, lng, type) and filters `WHERE tier = 'hot'`, so existing
--    `/nodes` and `lat,lng` nearest-station lookups never see warm nodes.
-- 4. A new RPC `get_all_nodes_with_coords()` is added for opt-in callers
--    (`road=true` or `include_warm=true`). Note: Postgres requires
--    DROP FUNCTION before CREATE FUNCTION whenever return columns change,
--    which is why RPC definitions live inside this transaction block.
-- 5. Directionality choice (Correction C): `road_edges` stores directed edges
--    in BOTH directions ((u, v) and (v, u)) so SQL queries see the complete
--    bidirectional road graph directly.
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- 1. Extend `nodes` with tier, kind, source, confidence, and optional osm_id
-- ----------------------------------------------------------------------------
ALTER TABLE nodes
    ADD COLUMN IF NOT EXISTS tier TEXT NOT NULL DEFAULT 'hot'
        CHECK (tier IN ('hot', 'warm')),
    ADD COLUMN IF NOT EXISTS kind TEXT NOT NULL DEFAULT 'rail'
        CHECK (kind IN ('rail', 'metro', 'bus_depot', 'bus_stop', 'auto_stand')),
    ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'seed',
    ADD COLUMN IF NOT EXISTS confidence TEXT NOT NULL DEFAULT 'high'
        CHECK (confidence IN ('high', 'medium', 'low')),
    ADD COLUMN IF NOT EXISTS osm_id BIGINT;

-- Backfill `kind` on existing 24 hot nodes based on their `type` column
UPDATE nodes
SET kind = CASE
    WHEN type = 'metro' THEN 'metro'
    ELSE 'rail'
END
WHERE tier = 'hot';

-- ----------------------------------------------------------------------------
-- 2. Rename `edges` -> `railway_edges` and create compatibility VIEW `edges`
-- ----------------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = 'edges'
          AND table_type = 'BASE TABLE'
    ) THEN
        ALTER TABLE edges RENAME TO railway_edges;
    END IF;
END $$;

CREATE OR REPLACE VIEW edges AS
SELECT id, from_node, to_node, mode, distance, time, cost, road_name
FROM railway_edges;

-- ----------------------------------------------------------------------------
-- 3. Create `road_edges` table (bidirectional rows stored explicitly)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS road_edges (
    id SERIAL PRIMARY KEY,
    from_node INT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    to_node INT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    distance DOUBLE PRECISION NOT NULL CHECK (distance >= 0),
    distance_source TEXT NOT NULL DEFAULT 'estimated'
        CHECK (distance_source IN ('estimated', 'osrm', 'surveyed')),
    road_name TEXT,
    CONSTRAINT road_edges_no_self_loop CHECK (from_node <> to_node),
    CONSTRAINT road_edges_unique_pair UNIQUE (from_node, to_node)
);

-- ----------------------------------------------------------------------------
-- 4. Keep `get_nodes_with_coords()` signature unchanged, filtering hot nodes
-- ----------------------------------------------------------------------------
-- NOTE: Because the 5-column return table is unchanged, CREATE OR REPLACE works
-- without breaking dependent views/callers. It filters to `tier = 'hot'` so
-- default `/nodes` and default `build_graph()` remain byte-identical.
CREATE OR REPLACE FUNCTION get_nodes_with_coords()
RETURNS TABLE(id INT, name TEXT, lat DOUBLE PRECISION, lng DOUBLE PRECISION, type TEXT)
LANGUAGE sql
STABLE
AS $$
  SELECT id, name, ST_Y(location) AS lat, ST_X(location) AS lng, type
  FROM nodes
  WHERE tier = 'hot'
  ORDER BY id;
$$;

-- ----------------------------------------------------------------------------
-- 5. New RPC `get_all_nodes_with_coords()` for `road=true` / `include_warm=true`
-- ----------------------------------------------------------------------------
-- NOTE: In PostgreSQL, changing a function's OUT/RETURNS TABLE columns requires
-- DROP FUNCTION first. Keeping DROP + CREATE inside BEGIN...COMMIT ensures
-- zero downtime if this migration is re-run.
DROP FUNCTION IF EXISTS get_all_nodes_with_coords();

CREATE FUNCTION get_all_nodes_with_coords()
RETURNS TABLE(
    id INT,
    name TEXT,
    lat DOUBLE PRECISION,
    lng DOUBLE PRECISION,
    type TEXT,
    tier TEXT,
    kind TEXT,
    source TEXT,
    confidence TEXT,
    osm_id BIGINT
)
LANGUAGE sql
STABLE
AS $$
  SELECT
      id,
      name,
      ST_Y(location) AS lat,
      ST_X(location) AS lng,
      type,
      tier,
      kind,
      source,
      confidence,
      osm_id
  FROM nodes
  ORDER BY id;
$$;

ALTER TABLE road_edges ENABLE ROW LEVEL SECURITY;
COMMIT;
NOTIFY pgrst, 'reload schema';
