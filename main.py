from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse
from collector.main import register
from core.config import settings
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="FastAPI + Prometheus Exporter")


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
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Metrics Dashboard</title>
        <style>
            * {
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }
            
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
                color: #333;
            }
            
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 12px;
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15);
                overflow: hidden;
            }
            
            .header {
                background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }
            
            .header h1 {
                font-size: 2.5rem;
                margin-bottom: 10px;
                font-weight: 700;
            }
            
            .header p {
                font-size: 1.1rem;
                opacity: 0.9;
            }
            
            .search-container {
                padding: 20px 30px;
                background: #f8f9fa;
                border-bottom: 1px solid #e9ecef;
            }
            
            #searchInput {
                width: 100%;
                padding: 12px 15px;
                border: 2px solid #e9ecef;
                border-radius: 8px;
                font-size: 1rem;
                transition: border-color 0.3s ease;
            }
            
            #searchInput:focus {
                outline: none;
                border-color: #4facfe;
                box-shadow: 0 0 0 3px rgba(79, 172, 254, 0.1);
            }
            
            .table-container {
                padding: 30px;
                overflow-x: auto;
            }
            
            table {
                width: 100%;
                border-collapse: collapse;
                font-size: 0.95rem;
            }
            
            th {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 15px;
                text-align: left;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                border: none;
            }
            
            td {
                padding: 15px;
                border-bottom: 1px solid #e9ecef;
                vertical-align: top;
            }
            
            tr {
                transition: all 0.3s ease;
                background: white;
            }
            
            tr:hover {
                background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
            }
            
            tr:nth-child(even) {
                background: #f8f9fa;
            }
            
            tr:nth-child(even):hover {
                background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            }
            
            .metric-name-cell {
                display: flex;
                align-items: center;
                gap: 10px;
            }
            
            .metric-name {
                font-weight: 600;
                color: #495057;
            }
            
            .copy-btn {
                background: #6c757d;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 10px;
                cursor: pointer;
                font-size: 0.8rem;
                transition: all 0.3s ease;
                opacity: 0.7;
            }
            
            .copy-btn:hover {
                background: #495057;
                opacity: 1;
                transform: scale(1.05);
            }
            
            .copy-btn:active {
                transform: scale(0.95);
            }
            
            .metric-type {
                display: inline-block;
                padding: 4px 10px;
                border-radius: 20px;
                font-size: 0.8rem;
                font-weight: 600;
                text-transform: uppercase;
            }
            
            .metric-type.counter {
                background: #d4edda;
                color: #155724;
            }
            
            .metric-type.gauge {
                background: #d1ecf1;
                color: #0c5460;
            }
            
            .metric-type.histogram {
                background: #fff3cd;
                color: #856404;
            }
            
            .metric-type.summary {
                background: #f8d7da;
                color: #721c24;
            }
            
            .metric-desc {
                color: #6c757d;
                line-height: 1.4;
            }
            
            .toast {
                position: fixed;
                top: 20px;
                right: 20px;
                background: #28a745;
                color: white;
                padding: 15px 20px;
                border-radius: 8px;
                box-shadow: 0 5px 15px rgba(0, 0, 0, 0.3);
                font-size: 1rem;
                transform: translateX(100%);
                transition: transform 0.3s ease;
                z-index: 1000;
            }
            
            .toast.show {
                transform: translateX(0);
            }
            
            @media (max-width: 768px) {
                body {
                    padding: 10px;
                }
                
                .header h1 {
                    font-size: 2rem;
                }
                
                .table-container {
                    padding: 15px;
                }
                
                th, td {
                    padding: 10px;
                    font-size: 0.85rem;
                }
                
                .metric-name-cell {
                    flex-direction: column;
                    align-items: flex-start;
                    gap: 5px;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Metrics Board</h1>
            </div>
            
            <div class="search-container">
                <input type="text" id="searchInput" placeholder="Search metrics...">
            </div>
            
            <div class="table-container">
                <table id="metricsTable">
                    <tr>
                        <th>Metric Name</th>
                        <th>Type</th>
                        <th>Description</th>
                    </tr>
    """

    for name, info in sorted(metrics.items()):
        mtype = info.get("type", "-")
        desc = info.get("desc", "-")
        html += f"""
                    <tr>
                        <td>
                            <div class="metric-name-cell">
                                <span class="metric-name">{name}</span>
                                <button class="copy-btn" onclick="copyToClipboard('{name}')">Copy</button>
                            </div>
                        </td>
                        <td>
                            <span class="metric-type {mtype}">{mtype}</span>
                        </td>
                        <td>
                            <span class="metric-desc">{desc}</span>
                        </td>
                    </tr>
        """

    html += """
                </table>
            </div>
        </div>
        
        <div id="toast" class="toast">Copied to clipboard!</div>
        
        <script>
            // Copy to clipboard function
            function copyToClipboard(text) {
                navigator.clipboard.writeText(text).then(() => {
                    // Show toast notification
                    const toast = document.getElementById('toast');
                    toast.classList.add('show');
                    
                    // Hide toast after 2 seconds
                    setTimeout(() => {
                        toast.classList.remove('show');
                    }, 2000);
                });
            }
            
            // Search functionality
            document.getElementById('searchInput').addEventListener('input', function() {
                const searchTerm = this.value.toLowerCase();
                const rows = document.querySelectorAll('#metricsTable tr:not(:first-child)');
                
                rows.forEach(row => {
                    const metricName = row.querySelector('.metric-name').textContent.toLowerCase();
                    const metricType = row.querySelector('.metric-type').textContent.toLowerCase();
                    const metricDesc = row.querySelector('.metric-desc').textContent.toLowerCase();
                    
                    if (metricName.includes(searchTerm) || metricType.includes(searchTerm) || metricDesc.includes(searchTerm)) {
                        row.style.display = '';
                    } else {
                        row.style.display = 'none';
                    }
                });
            });
        </script>
    </body>
    </html>
    """

    return HTMLResponse(content=html)


if settings.DEV:
    app.add_middleware(CORSMiddleware, allow_origins=["*"])

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)
