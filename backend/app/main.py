from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.graph import (
    InvalidWeight,
    NoPath,
    RoutingError,
    SameNode,
    UnknownNode,
    UpstreamError,
    compare_routes,
    fetch_nodes,
    list_nodes,
    shortest_path,
)
from app.alternatives import annotate_route_with_alternatives
from app.cabs import get_all_cab_estimates
from app.railradar import annotate_route_with_live_status

app = FastAPI(title="Optigo API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Bad input -> 4xx with a JSON body the frontend can show.
ROUTING_ERROR_STATUS = {
    UnknownNode: 404,
    NoPath: 404,
    SameNode: 400,
    InvalidWeight: 422,
}


@app.exception_handler(RoutingError)
async def routing_error_handler(request: Request, exc: RoutingError):
    status = ROUTING_ERROR_STATUS.get(type(exc), 400)
    return JSONResponse(status_code=status, content={"detail": str(exc), "error": type(exc).__name__})


@app.exception_handler(UpstreamError)
async def upstream_error_handler(request: Request, exc: UpstreamError):
    return JSONResponse(status_code=502, content={"detail": str(exc), "error": "UpstreamError"})


Weight = Literal["time", "distance", "cost"]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/nodes")
def get_nodes():
    """All stations (id, name, lat, lng, type), sorted by id."""
    return list_nodes()


@app.get("/route")
def get_route(source: int = Query(1), target: int = Query(5), weight: Weight = Query("time")):
    return shortest_path(source, target, weight)


@app.get("/compare")
def compare(
    source: int = Query(1),
    target: int = Query(5),
    live: bool = Query(False),
    prefer_seat: bool = Query(False),
):
    result = compare_routes(source, target)
    if live or prefer_seat:
        for route in result:
            annotate_route_with_live_status(route, limit=3)
            if prefer_seat:
                annotate_route_with_alternatives(route, prefer_seat=True)
    return result


@app.get("/cabs/estimate")
def get_cabs_estimate(
    pickup_lat: Optional[float] = Query(None, ge=-90, le=90),
    pickup_lng: Optional[float] = Query(None, ge=-180, le=180),
    dropoff_lat: Optional[float] = Query(None, ge=-90, le=90),
    dropoff_lng: Optional[float] = Query(None, ge=-180, le=180),
    source_station_id: Optional[int] = Query(None),
    target_station_id: Optional[int] = Query(None),
):
    """Calibrated fare matrix and universal deep links for Uber, Ola, Rapido, and Auto Rickshaw."""
    pickup_name, dropoff_name = None, None

    if source_station_id is not None and target_station_id is not None:
        nodes = fetch_nodes()
        if source_station_id not in nodes:
            raise HTTPException(status_code=404, detail=f"Source station ID {source_station_id} not found")
        if target_station_id not in nodes:
            raise HTTPException(status_code=404, detail=f"Target station ID {target_station_id} not found")
        src = nodes[source_station_id]
        tgt = nodes[target_station_id]
        pickup_lat, pickup_lng, pickup_name = src["lat"], src["lng"], src["name"]
        dropoff_lat, dropoff_lng, dropoff_name = tgt["lat"], tgt["lng"], tgt["name"]
    elif all(v is not None for v in [pickup_lat, pickup_lng, dropoff_lat, dropoff_lng]):
        pickup_name = "Pickup Location"
        dropoff_name = "Dropoff Location"
    else:
        raise HTTPException(
            status_code=422,
            detail="Must provide either (pickup_lat, pickup_lng, dropoff_lat, dropoff_lng) or (source_station_id, target_station_id)",
        )

    return get_all_cab_estimates(
        pickup_lat=pickup_lat,
        pickup_lng=pickup_lng,
        dropoff_lat=dropoff_lat,
        dropoff_lng=dropoff_lng,
        pickup_name=pickup_name,
        dropoff_name=dropoff_name,
    )

