from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse
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


@app.get("/metrics_html", response_class=HTMLResponse)
def metrics_html():
    raw = generate_latest(register).decode("utf-8")

    metrics = {}  # name -> {type, desc}

    for line in raw.splitlines():
        if line.startswith("# HELP"):
            _, _, name, desc = line.split(" ", 3)
            metrics.setdefault(name, {})["desc"] = desc
        elif line.startswith("# TYPE"):
            _, _, name, mtype = line.split(" ", 3)
            metrics.setdefault(name, {})["type"] = mtype

    html = """
    <html>
    <head>
        <meta charset="utf-8">
        <title>Metrics</title>
        <style>
            body { font-family: Arial, sans-serif; }
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #ddd; padding: 8px; }
            th { background-color: #f4f4f4; text-align: left; }
            tr:hover { background-color: #fafafa; }
        </style>
    </head>
    <body>
        <h1>Metrics List</h1>
        <table>
            <tr>
                <th>Metric Name</th>
                <th>Type</th>
                <th>Description</th>
            </tr>
    """

    for name, info in sorted(metrics.items()):
        html += f"""
            <tr>
                <td>{name}</td>
                <td>{info.get("type", "-")}</td>
                <td>{info.get("desc", "-")}</td>
            </tr>
        """

    html += """
        </table>
    </body>
    </html>
    """

    return HTMLResponse(content=html)


if settings.DEV:
    app.add_middleware(CORSMiddleware, allow_origins=["*"])

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)
