"""User record provisioning for Supabase Auth users."""

from __future__ import annotations

from supabase import AsyncClient

from app.auth.dependencies import CurrentUser


async def ensure_user(client: AsyncClient, user: CurrentUser) -> None:
    """Upsert the authenticated user into the users table via service role."""
    await (
        client.table("users")
        .upsert({"id": str(user.id), "email": user.email})
        .execute()
    )
