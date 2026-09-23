from typing import Literal

from fastapi import FastAPI, Query, Request
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
    list_nodes,
    shortest_path,
)
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
def compare(source: int = Query(1), target: int = Query(5), live: bool = Query(False)):
    result = compare_routes(source, target)
    if live:
        for route in result:
            annotate_route_with_live_status(route, limit=3)
    return result
