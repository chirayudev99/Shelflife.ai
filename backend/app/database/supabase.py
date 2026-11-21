"""Supabase client construction for server-side database and auth access."""

from collections.abc import AsyncIterator

import httpx
from fastapi import Depends, Request
from supabase import AsyncClient, acreate_client
from supabase.lib.client_options import AsyncClientOptions

from app.auth.dependencies import get_access_token
from app.config import settings


def _server_client_options(
    *,
    access_token: str | None = None,
    http_client: httpx.AsyncClient,
) -> AsyncClientOptions:
    headers: dict[str, str] = {}
    if access_token is not None:
        headers["Authorization"] = f"Bearer {access_token}"

    return AsyncClientOptions(
        headers=headers,
        auto_refresh_token=False,
        persist_session=False,
        httpx_client=http_client,
    )


def _normalize_access_token(access_token: str) -> str:
    prefix = "Bearer "
    if access_token.startswith(prefix):
        return access_token.removeprefix(prefix)
    return access_token


def get_service_role_client(request: Request) -> AsyncClient:
    """Return the lifespan-managed client that bypasses RLS."""
    return request.app.state.supabase_service_client


async def create_user_client(
    access_token: str,
    *,
    http_client: httpx.AsyncClient,
) -> AsyncClient:
    return await acreate_client(
        settings.supabase_url,
        settings.supabase_anon_key,
        options=_server_client_options(
            access_token=_normalize_access_token(access_token),
            http_client=http_client,
        ),
    )


async def get_user_client(
    request: Request,
    access_token: str = Depends(get_access_token),
) -> AsyncIterator[AsyncClient]:
    """Create an RLS client using the shared HTTP transport."""
    yield await create_user_client(
        access_token,
        http_client=request.app.state.http_client,
    )
