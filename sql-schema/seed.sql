-- ============================================================================
-- OptiGo Canonical Supabase Database Seed (PostgreSQL + PostGIS)
-- 24 Stations (Nodes) & 26 Network Edges
-- ============================================================================

-- 1. PostGIS Extension
CREATE EXTENSION IF NOT EXISTS postgis;

-- 2. Schema DDL
CREATE TABLE IF NOT EXISTS nodes (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    location GEOMETRY(Point, 4326) NOT NULL,
    type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS edges (
    id SERIAL PRIMARY KEY,
    from_node INT NOT NULL REFERENCES nodes(id),
    to_node INT NOT NULL REFERENCES nodes(id),
    mode TEXT NOT NULL
        CHECK (mode IN ('walking', 'bike', 'car', 'bus', 'train', 'metro')),
    distance DOUBLE PRECISION NOT NULL
        CHECK (distance >= 0),
    time DOUBLE PRECISION NOT NULL
        CHECK (time >= 0),
    cost DOUBLE PRECISION NOT NULL DEFAULT 0
        CHECK (cost >= 0),
    road_name TEXT
);

-- 3. PostGIS Geometry Unpacker Function (RPC)
CREATE OR REPLACE FUNCTION get_nodes_with_coords()
RETURNS TABLE(id INT, name TEXT, lat DOUBLE PRECISION, lng DOUBLE PRECISION, type TEXT)
LANGUAGE sql
AS $$
  SELECT id, name, ST_Y(location) AS lat, ST_X(location) AS lng, type
  FROM nodes;
$$;

-- 4. Nodes (24 stations). Coordinates are Point(lng, lat) in SRID 4326.
INSERT INTO nodes (name, location, type) VALUES
('Vashi',            ST_SetSRID(ST_MakePoint(72.9988553, 19.0632517), 4326), 'rail'),
('Sanpada',           ST_SetSRID(ST_MakePoint(73.0094849, 19.0659637), 4326), 'rail'),
('Juinagar',          ST_SetSRID(ST_MakePoint(73.0178235, 19.0562946), 4326), 'rail'),
('Nerul',             ST_SetSRID(ST_MakePoint(73.0183566, 19.0333801), 4326), 'rail_uran_origin'),
('Seawoods-Darave',   ST_SetSRID(ST_MakePoint(73.0193133, 19.0219794), 4326), 'rail'),
('Belapur CBD',       ST_SetSRID(ST_MakePoint(73.0388390, 19.0188208), 4326), 'rail_metro_uran_interchange'),
('Sagar Sangam',      ST_SetSRID(ST_MakePoint(73.0247210, 19.0106630), 4326), 'rail_junction'),
('Kharghar',          ST_SetSRID(ST_MakePoint(73.0594488, 19.0263639), 4326), 'rail'),
('Mansarovar',        ST_SetSRID(ST_MakePoint(73.0806949, 19.0165576), 4326), 'rail'),
('Khandeshwar',       ST_SetSRID(ST_MakePoint(73.0952632, 19.0073656), 4326), 'rail'),
('Panvel',            ST_SetSRID(ST_MakePoint(73.1206460, 18.9911172), 4326), 'rail'),
('Targhar',           ST_SetSRID(ST_MakePoint(73.0370475, 18.9918840), 4326), 'rail'),
('Bamandongri',       ST_SetSRID(ST_MakePoint(73.0243313, 18.9751506), 4326), 'rail'),
('Kharkopar',         ST_SetSRID(ST_MakePoint(73.0141460, 18.9599051), 4326), 'rail'),
('Belpada',           ST_SetSRID(ST_MakePoint(73.0552703, 19.0254324), 4326), 'metro'),
('Utsav Chowk',       ST_SetSRID(ST_MakePoint(73.0590980, 19.0327270), 4326), 'metro'),
('Kendriya Vihar',    ST_SetSRID(ST_MakePoint(73.0641924, 19.0376857), 4326), 'metro'),
('Kharghar Village',  ST_SetSRID(ST_MakePoint(73.0744660, 19.0433150), 4326), 'metro'),
('Central Park',      ST_SetSRID(ST_MakePoint(73.0760829, 19.0536592), 4326), 'metro'),
('Pethpada',          ST_SetSRID(ST_MakePoint(73.0774620, 19.0640100), 4326), 'metro'),
('Amandoot',          ST_SetSRID(ST_MakePoint(73.0818660, 19.0737820), 4326), 'metro'),
('Pethali-Taloja',    ST_SetSRID(ST_MakePoint(73.0907640, 19.0746640), 4326), 'metro'),
('Pendhar',           ST_SetSRID(ST_MakePoint(73.0981910, 19.0719003), 4326), 'metro'),
('RBI',               ST_SetSRID(ST_MakePoint(73.0468000, 19.0217000), 4326), 'metro');

-- 5. Edges (26 network hops)

-- Main Harbour corridor (Vashi → Panvel) - 9 hops
INSERT INTO edges (from_node, to_node, mode, distance, time, cost) VALUES
((SELECT id FROM nodes WHERE name='Vashi'),           (SELECT id FROM nodes WHERE name='Sanpada'),         'train', 1.0, 3, 5),
((SELECT id FROM nodes WHERE name='Sanpada'),          (SELECT id FROM nodes WHERE name='Juinagar'),        'train', 2.0, 3, 5),
((SELECT id FROM nodes WHERE name='Juinagar'),         (SELECT id FROM nodes WHERE name='Nerul'),           'train', 2.0, 3, 5),
((SELECT id FROM nodes WHERE name='Nerul'),            (SELECT id FROM nodes WHERE name='Seawoods-Darave'), 'train', 1.0, 3, 5),
((SELECT id FROM nodes WHERE name='Seawoods-Darave'),  (SELECT id FROM nodes WHERE name='Belapur CBD'),     'train', 3.0, 4, 5),
((SELECT id FROM nodes WHERE name='Belapur CBD'),      (SELECT id FROM nodes WHERE name='Kharghar'),        'train', 2.0, 5, 5),
((SELECT id FROM nodes WHERE name='Kharghar'),         (SELECT id FROM nodes WHERE name='Mansarovar'),      'train', 3.0, 4, 5),
((SELECT id FROM nodes WHERE name='Mansarovar'),       (SELECT id FROM nodes WHERE name='Khandeshwar'),     'train', 2.0, 4, 5),
((SELECT id FROM nodes WHERE name='Khandeshwar'),      (SELECT id FROM nodes WHERE name='Panvel'),          'train', 3.0, 5, 5);

-- Uran-Ulwe branch — two feeders (Belapur CBD & Seawoods-Darave) converging at Sagar Sangam, then onward to Kharkopar - 5 hops
INSERT INTO edges (from_node, to_node, mode, distance, time, cost) VALUES
((SELECT id FROM nodes WHERE name='Belapur CBD'),      (SELECT id FROM nodes WHERE name='Sagar Sangam'),  'train', 2.0, 3, 5),
((SELECT id FROM nodes WHERE name='Seawoods-Darave'),  (SELECT id FROM nodes WHERE name='Sagar Sangam'),  'train', 3.0, 3, 5),
((SELECT id FROM nodes WHERE name='Sagar Sangam'),     (SELECT id FROM nodes WHERE name='Targhar'),       'train', 2.0, 3, 5),
((SELECT id FROM nodes WHERE name='Targhar'),          (SELECT id FROM nodes WHERE name='Bamandongri'),   'train', 3.0, 3, 5),
((SELECT id FROM nodes WHERE name='Bamandongri'),      (SELECT id FROM nodes WHERE name='Kharkopar'),     'train', 2.0, 4, 5);

-- Metro Line 1 (Belapur CBD → Pendhar via RBI) - 10 hops
INSERT INTO edges (from_node, to_node, mode, distance, time, cost) VALUES
((SELECT id FROM nodes WHERE name='Belapur CBD'),      (SELECT id FROM nodes WHERE name='RBI'),              'metro', 1.0, 2, 4),
((SELECT id FROM nodes WHERE name='RBI'),              (SELECT id FROM nodes WHERE name='Belpada'),          'metro', 1.0, 2, 4),
((SELECT id FROM nodes WHERE name='Belpada'),           (SELECT id FROM nodes WHERE name='Utsav Chowk'),     'metro', 0.7, 3, 4),
((SELECT id FROM nodes WHERE name='Utsav Chowk'),       (SELECT id FROM nodes WHERE name='Kendriya Vihar'),  'metro', 0.8, 3, 4),
((SELECT id FROM nodes WHERE name='Kendriya Vihar'),    (SELECT id FROM nodes WHERE name='Kharghar Village'),'metro', 1.3, 3, 4),
((SELECT id FROM nodes WHERE name='Kharghar Village'),  (SELECT id FROM nodes WHERE name='Central Park'),    'metro', 1.4, 3, 4),
((SELECT id FROM nodes WHERE name='Central Park'),      (SELECT id FROM nodes WHERE name='Pethpada'),        'metro', 1.6, 3, 4),
((SELECT id FROM nodes WHERE name='Pethpada'),          (SELECT id FROM nodes WHERE name='Amandoot'),        'metro', 1.2, 3, 4),
((SELECT id FROM nodes WHERE name='Amandoot'),          (SELECT id FROM nodes WHERE name='Pethali-Taloja'),  'metro', 1.1, 3, 4),
((SELECT id FROM nodes WHERE name='Pethali-Taloja'),    (SELECT id FROM nodes WHERE name='Pendhar'),         'metro', 1.1, 3, 4);

-- Walking transfers (Belpada ↔ Kharghar interchange) - 2 hops
INSERT INTO edges (from_node, to_node, mode, distance, time, cost) VALUES
((SELECT id FROM nodes WHERE name='Belpada'),  (SELECT id FROM nodes WHERE name='Kharghar'), 'walking', 0.6, 8, 0),
((SELECT id FROM nodes WHERE name='Kharghar'), (SELECT id FROM nodes WHERE name='Belpada'),  'walking', 0.6, 8, 0);
