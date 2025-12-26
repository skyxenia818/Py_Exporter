from fastapi import FastAPI, Response
from collector.main import register
from core.config import settings
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="FastAPI + Prometheus CPU Exporter")

@app.get("/metrics")
def metrics():
    data = generate_latest(register)
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)

if settings.DEV:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"]
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)
