from contextlib import asynccontextmanager

import httpx
from google import genai
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from supabase import acreate_client
from supabase.lib.client_options import AsyncClientOptions
import uvicorn

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.config import settings
from app.database.session import create_async_session_resources


@asynccontextmanager
async def lifespan(app: FastAPI):
    gemini_client = genai.Client(api_key=settings.google_api_key)
    http_client = httpx.AsyncClient()
    engine, session_factory = create_async_session_resources(
        settings.sqlalchemy_database_url
    )
    client_options = AsyncClientOptions(
        auto_refresh_token=False,
        persist_session=False,
        httpx_client=http_client,
    )
    try:
        app.state.gemini_client = gemini_client
        app.state.http_client = http_client
        app.state.async_engine = engine
        app.state.async_session_factory = session_factory
        app.state.supabase_auth_client = await acreate_client(
            settings.supabase_url,
            settings.supabase_anon_key,
            options=client_options,
        )
        app.state.supabase_service_client = await acreate_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
            options=client_options,
        )
        yield
    finally:
        await engine.dispose()
        gemini_client.close()
        await gemini_client.aio.aclose()
        await http_client.aclose()


app = FastAPI(title="ShelfLife", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(chat_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000)
