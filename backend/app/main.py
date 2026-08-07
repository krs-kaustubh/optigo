from fastapi import FastAPI, Query
from app.graph import shortest_path, compare_routes

app = FastAPI(title="Optigo API")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/route")
def get_route(source: int = Query(1), target: int = Query(5), weight: str = Query("time")):
    return shortest_path(source, target, weight)

@app.get("/compare")
def compare(source: int = Query(1), target: int = Query(5)):
    return compare_routes(source, target)