import logging

import httpx

logger = logging.getLogger(__name__)

_ST_API = "https://api.smartthings.com/v1"


async def subscribe_devices(
    installed_app_id: str,
    auth_token: str,
    device_ids: list[str],
    *,
    clear_first: bool = False,
) -> None:
    async with httpx.AsyncClient(timeout=15.0) as client:
        if clear_first:
            r = await client.delete(
                f"{_ST_API}/installedapps/{installed_app_id}/subscriptions",
                headers={"Authorization": f"Bearer {auth_token}"},
            )
            logger.info(f"구독 초기화: {r.status_code}")

        for device_id in device_ids:
            r = await client.post(
                f"{_ST_API}/installedapps/{installed_app_id}/subscriptions",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={
                    "sourceType": "DEVICE",
                    "device": {
                        "deviceId": device_id,
                        "componentId": "main",
                        "capability": "powerMeter",
                        "attribute": "power",
                        "stateChangeOnly": False,
                    },
                },
            )
            r.raise_for_status()
            logger.info(f"구독 등록: device={device_id}")
