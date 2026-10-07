# Supabase SQL Schema & Seeds

Database: **PostgreSQL** (hosted on Supabase) with **PostGIS** extension.

## Files

| File | Purpose |
|---|---|
| [`seed.sql`](seed.sql) | **Canonical all-in-one setup script** for new Supabase projects. Creates extension, DDL, RPC function, 24 nodes, and 26 edges with verified CIDCO/CR distances. |
| [`nodes-edges`](nodes-edges) | DDL: Enables `postgis` extension and creates `nodes` and `edges` tables with check constraints. |
| [`nodes-data`](nodes-data) | DML: Inserts 24 stations with PostGIS `Point(lng, lat)` geometry in SRID 4326. |
| [`edge-data`](edge-data) | DML: Inserts 26 network edges (9 Harbour, 5 Uran, 10 Metro Line 1 via RBI, 2 walking transfers). |
| [`postgres`](postgres) | DDL/RPC: Defines `get_nodes_with_coords()` helper function used by `/nodes` API. |
| [`update-node-edge-data`](update-node-edge-data) | Migration: Idempotent migration adding RBI (node 24), splitting Metro Line 1, rewiring Uran feeder to Seawoods-Darave, and adding walking transfer edges. |
| [`6. Distance Update`](6.%20Distance%20Update) | Migration: Updates all edge distances to ground-truth values (CIDCO chainage + CR track distances). |

## Station Count & Edge Topology

- **Stations (24 nodes):**
  - **Harbour Line (10):** Vashi (1), Sanpada (2), Juinagar (3), Nerul (4), Seawoods-Darave (5), Belapur CBD (6), Kharghar (8), Mansarovar (9), Khandeshwar (10), Panvel (11).
  - **Uran Branch (4):** Sagar Sangam (7), Targhar (12), Bamandongri (13), Kharkopar (14).
  - **Metro Line 1 (10):** Belpada (15), Utsav Chowk (16), Kendriya Vihar (17), Kharghar Village (18), Central Park (19), Pethpada (20), Amandoot (21), Pethali-Taloja (22), Pendhar (23), RBI (24).
- **Edges (26 hops):**
  - 9 Harbour rail hops
  - 5 Uran rail hops
  - 10 Metro hops (including Belapur CBD ↔ RBI ↔ Belpada at 1.0 km each)
  - 2 Walking hops (Belpada ↔ Kharghar at 0.6 km each)
