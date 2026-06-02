import asyncio
import logging
import os
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.core.database import SessionLocal
from app.repositories import system_settings_repo

logger = logging.getLogger(__name__)

_ST_API = "https://api.smartthings.com/v1"
_ST_AUTH = "https://api.smartthings.com/oauth/token"

POLL_INTERVAL = 12
_STALE_THRESHOLD_SEC = 300  # 5분 이상 업데이트 없으면 오프라인 처리


def _device_map() -> dict[str, int]:
    result: dict[str, int] = {}
    for key, value in os.environ.items():
        if key.startswith("SMARTTHINGS_DEVICE_") and value.strip():
            suffix = key[len("SMARTTHINGS_DEVICE_"):]
            try:
                result[value.strip()] = int(suffix)
            except ValueError:
                pass
    return result


_TOKEN_REVOKED = object()  # refresh token이 영구 무효 (invalid_grant)


async def _refresh_token(refresh_token: str) -> tuple[str, str] | None | object:
    if not settings.st_client_id or not settings.st_client_secret:
        print("ST_CLIENT_ID/SECRET 미설정 — refresh 불가", flush=True)
        return None
    try:
        import base64
        creds = base64.b64encode(f"{settings.st_client_id}:{settings.st_client_secret}".encode()).decode()
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                _ST_AUTH,
                headers={"Authorization": f"Basic {creds}", "Content-Type": "application/x-www-form-urlencoded"},
                content=f"grant_type=refresh_token&refresh_token={refresh_token}",
            )
            print(f"refresh 응답: {r.status_code} {r.text[:200]}", flush=True)
            if r.status_code == 400 and "invalid_grant" in r.text:
                print("refresh token 영구 무효 (invalid_grant) — SmartThings 재인증 필요", flush=True)
                return _TOKEN_REVOKED
            r.raise_for_status()
            data = r.json()
            return data["access_token"], data.get("refresh_token", refresh_token)
    except Exception as e:
        print(f"토큰 갱신 실패: {e}", flush=True)
        return None


async def _get_power(device_id: str, token: str) -> float | None:
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{_ST_API}/devices/{device_id}/status",
                headers={"Authorization": f"Bearer {token}"},
            )
            if r.status_code == 401:
                return None  # 토큰 만료 신호
            r.raise_for_status()
            power_attr = r.json()["components"]["main"]["powerMeter"]["power"]
            power = float(power_attr["value"])
            ts_str = power_attr.get("timestamp")
            if ts_str:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                age = (datetime.now(timezone.utc) - ts).total_seconds()
                if age > _STALE_THRESHOLD_SEC:
                    logger.info(f"전력 데이터 {age:.0f}초 경과 → 오프라인 처리 (device={device_id})")
                    return -1.0
            return power
    except Exception as e:
        logger.error(f"전력 조회 실패 device={device_id}: {e}")
        return None


async def poll_loop() -> None:
    logger.info("SmartThings 폴러 시작")
    dm = _device_map()
    if not dm:
        logger.warning("SMARTTHINGS_DEVICE_ 환경변수 없음 — 폴러 종료")
        return

    while True:
        try:
            db = SessionLocal()
            try:
                auth_token = system_settings_repo.get_str(db, "st_auth_token") or ""
                refresh_tok = system_settings_repo.get_str(db, "st_refresh_token") or ""
            finally:
                db.close()

            if not auth_token:
                logger.warning("st_auth_token 없음 — 폴링 대기")
                await asyncio.sleep(POLL_INTERVAL)
                continue

            for device_id, machine_id in dm.items():
                power = await _get_power(device_id, auth_token)

                if power is None and refresh_tok:
                    logger.info("401 감지 — 토큰 갱신 시도")
                    result = await _refresh_token(refresh_tok)
                    if result is _TOKEN_REVOKED:
                        logger.error("SmartThings refresh token 영구 무효 — DB 토큰 초기화, 재인증 필요")
                        db = SessionLocal()
                        try:
                            system_settings_repo.set_str(db, "st_auth_token", "")
                            system_settings_repo.set_str(db, "st_refresh_token", "")
                        finally:
                            db.close()
                        auth_token = ""
                        refresh_tok = ""
                        break  # 이 poll 사이클 devices 루프 탈출
                    if result:
                        auth_token, refresh_tok = result
                        db = SessionLocal()
                        try:
                            system_settings_repo.set_str(db, "st_auth_token", auth_token)
                            system_settings_repo.set_str(db, "st_refresh_token", refresh_tok)
                        finally:
                            db.close()
                        power = await _get_power(device_id, auth_token)

                if power is None:
                    continue

                from app.api.smartthings import _last_states, _process_event
                prev = _last_states.get(device_id)
                is_running = (
                    power >= settings.stop_threshold_w if prev is True
                    else power >= settings.power_threshold_w
                )
                _last_states[device_id] = is_running
                await _process_event(machine_id, is_running, power)
                logger.debug(f"poll machine={machine_id} power={power}W")

        except Exception as e:
            logger.error(f"폴러 오류: {e}")

        await asyncio.sleep(POLL_INTERVAL)
