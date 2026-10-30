from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from sqlalchemy import text
from app.db.session import engine
from app.db.lifecycle import lifespan
from app.users.router import router as router_users
from app.messages.router import router as router_messages
from app.messages.websocket import router as router_websocket

app = FastAPI(lifespan=lifespan)
static_directory = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_directory), name="static")
app.include_router(router_users)
app.include_router(router_messages)
app.include_router(router_websocket)


@app.get("/", include_in_schema=False)
async def get_index():
    return FileResponse(static_directory / "index.html")


@app.get("/health/db")
async def health():
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            return {"status": "ok", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail="Database unavailable")