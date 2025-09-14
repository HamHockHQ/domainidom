from __future__ import annotations

import os
from fastapi import FastAPI
from .config import load_env

load_env()
app = FastAPI(title="domainidom")


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "env": bool(os.getenv("OPENAI_API_KEY"))}
