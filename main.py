
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

import logging
from dotenv import load_dotenv
from api.routers import base, cotizaciones, inversiones, drive, finanzas

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