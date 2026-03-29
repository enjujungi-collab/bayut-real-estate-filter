import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from server.routes.chat import router as chat_router
from server.routes.pdf  import router as pdf_router

app = FastAPI(title="Bayut Real Estate", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(pdf_router)

FRONTEND = os.path.join(os.path.dirname(__file__), "..", "frontend")

@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND, "index.html"))

@app.get("/ping")
def ping():
    return {"status": "ok"}
