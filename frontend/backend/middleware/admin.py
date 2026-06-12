import os
import httpx
from fastapi import Request, HTTPException

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://yvpjfmjxunoxmfljixwo.supabase.co")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
ADMIN_EMAIL = "sefanlazar7@gmail.com"


async def require_admin(request: Request):
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(status_code=403, detail="Acces interzis")

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": SUPABASE_SERVICE_KEY,
            },
            timeout=10,
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=403, detail="Token invalid")

    user_data = resp.json()
    if user_data.get("email") != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Necesită cont de admin")

    return user_data
