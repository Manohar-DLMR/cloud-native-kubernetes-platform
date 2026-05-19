import os
import time
import random
import socket
import json
from fastapi import FastAPI, Request, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = FastAPI()

SERVICE_NAME = os.getenv("SERVICE_NAME", "platform-demo")
APP_VERSION = os.getenv("APP_VERSION", "v1")
SLOW_MODE = os.getenv("SLOW_MODE", "false").lower() == "true"
ERROR_RATE = float(os.getenv("ERROR_RATE", "0.0"))
CPU_BURN = os.getenv("CPU_BURN", "false").lower() == "true"

REQUEST_COUNT = Counter(
    "app_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "http_status"]
)

REQUEST_LATENCY = Histogram(
    "app_request_latency_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"]
)


def structured_log(data: dict):
    print(json.dumps(data), flush=True)


@app.middleware("http")
async def metrics_and_logging(request: Request, call_next):
    start_time = time.time()
    endpoint = request.url.path
    method = request.method

    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception:
        status_code = 500
        raise
    finally:
        latency = time.time() - start_time
        REQUEST_COUNT.labels(
            method=method,
            endpoint=endpoint,
            http_status=str(status_code)
        ).inc()

        REQUEST_LATENCY.labels(
            method=method,
            endpoint=endpoint
        ).observe(latency)

        structured_log({
            "service": SERVICE_NAME,
            "version": APP_VERSION,
            "method": method,
            "endpoint": endpoint,
            "status": status_code,
            "latency_ms": round(latency * 1000, 2),
            "hostname": socket.gethostname()
        })

    return response


@app.get("/")
def root():
    return {
        "service": SERVICE_NAME,
        "version": APP_VERSION,
        "message": "Cloud Native Platform Demo is running"
    }


@app.get("/healthz")
def healthz():
    return {
        "status": "ok"
    }


@app.get("/readyz")
def readyz():
    return {
        "status": "ready"
    }


@app.get("/work")
def work():
    if SLOW_MODE:
        time.sleep(1.5)

    if CPU_BURN:
        end_time = time.time() + 0.3
        while time.time() < end_time:
            _ = 12345 * 67890

    if random.random() < ERROR_RATE:
        return Response(
            content=json.dumps({
                "service": SERVICE_NAME,
                "version": APP_VERSION,
                "status": "error",
                "message": "simulated error",
                "hostname": socket.gethostname()
            }),
            status_code=500,
            media_type="application/json"
        )

    return {
        "service": SERVICE_NAME,
        "version": APP_VERSION,
        "status": "success",
        "message": "work completed",
        "hostname": socket.gethostname(),
        "slow_mode": SLOW_MODE,
        "error_rate": ERROR_RATE,
        "cpu_burn": CPU_BURN
    }


@app.get("/metrics")
def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
