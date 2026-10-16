-- ============================================================================
-- Phase B Rollback: revert road_edges, railway_edges, and warm nodes
-- ============================================================================
-- WARNING — DATA LOSS NOTICE FOR WARM NODES:
-- Running this rollback script DELETES all rows in `nodes` where `tier = 'warm'`
-- and drops the `road_edges` table.
-- Before running this rollback, export any manually curated warm nodes to CSV:
--   \copy (SELECT name, ST_Y(location) AS lat, ST_X(location) AS lng, tier, kind, source, confidence, osm_id FROM nodes WHERE tier = 'warm' ORDER BY id) TO 'sql-schema/warm_nodes_backup.csv' WITH CSV HEADER;
-- ============================================================================

BEGIN;

-- 1. Drop the new opt-in RPC
DROP FUNCTION IF EXISTS get_all_nodes_with_coords();

-- 2. Drop `road_edges` table
DROP TABLE IF EXISTS road_edges;

-- 3. Remove warm nodes so only the original 24 hot nodes remain
DELETE FROM nodes WHERE tier = 'warm';

-- 4. Restore `get_nodes_with_coords()` to its original definition (before dropping `tier`)
-- Note: Return columns are identical (id, name, lat, lng, type); if you ever
-- change return columns in Postgres, you must DROP FUNCTION then CREATE FUNCTION
-- inside a transaction.
CREATE OR REPLACE FUNCTION get_nodes_with_coords()
RETURNS TABLE(id INT, name TEXT, lat DOUBLE PRECISION, lng DOUBLE PRECISION, type TEXT)
LANGUAGE sql
AS $$
  SELECT id, name, ST_Y(location) AS lat, ST_X(location) AS lng, type
  FROM nodes;
$$;

-- 5. Drop the compatibility view `edges` and rename `railway_edges` back to `edges`
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.views
        WHERE table_schema = 'public'
          AND table_name = 'edges'
    ) THEN
        DROP VIEW edges;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = 'railway_edges'
          AND table_type = 'BASE TABLE'
    ) THEN
        ALTER TABLE railway_edges RENAME TO edges;
    END IF;
END $$;

-- 6. Drop the added columns on `nodes`
ALTER TABLE nodes
    DROP COLUMN IF EXISTS osm_id,
    DROP COLUMN IF EXISTS confidence,
    DROP COLUMN IF EXISTS source,
    DROP COLUMN IF EXISTS kind,
    DROP COLUMN IF EXISTS tier;

COMMIT;
NOTIFY pgrst, 'reload schema';