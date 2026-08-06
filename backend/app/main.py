from fastapi import FastAPI

app = FastAPI(title="Optigo API")

@app.get("/health")
def health():
    return {"status": "ok"}