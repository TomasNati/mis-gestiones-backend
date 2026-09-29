
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
import os

import logging
from dotenv import load_dotenv
from api.routers import base, cotizaciones, inversiones, drive, finanzas, comprobantes

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

app = FastAPI(
    title="Vercel + FastAPI",
    description="Vercel + FastAPI",
    version="1.0.0"
)

origins = [
    "http://localhost:5173", # Default Vite dev server port
    "http://localhost:9999", # Custom port for testing
    "https://mis-gestiones-admin.vercel.app",
    "https://mis-gestiones-opal-kappa.vercel.app"
]

app.add_middleware( CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


app.include_router(base.router)
app.include_router(finanzas.router)
app.include_router(inversiones.router)
app.include_router(cotizaciones.router)
app.include_router(drive.router)
app.include_router(comprobantes.router)


def _como_binario(nodo):
    if isinstance(nodo, list):
        for item in nodo:
            _como_binario(item)
    elif isinstance(nodo, dict):
        if nodo.get("contentMediaType") == "application/octet-stream":
            nodo.pop("contentMediaType")
            nodo["format"] = "binary"
        for valor in nodo.values():
            _como_binario(valor)


def _openapi() -> dict:
    if app.openapi_schema is None:
        app.openapi_schema = get_openapi(
            title=app.title, description=app.description, version=app.version, routes=app.routes
        )
        _como_binario(app.openapi_schema["components"]["schemas"])
    return app.openapi_schema


app.openapi = _openapi