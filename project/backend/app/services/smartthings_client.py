import httpx

from app.config import settings

_BASE = "https://api.smartthings.com/v1"


async def get_power_w(device_id: str) -> float:
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(
            f"{_BASE}/devices/{device_id}/status",
            headers={"Authorization": f"Bearer {settings.smartthings_pat}"},
        )
        r.raise_for_status()
        return float(r.json()["components"]["main"]["powerMeter"]["power"]["value"])
