import asyncio
import logging
import time
from datetime import datetime, timezone

from app.config import settings
from app.core.database import SessionLocal
from app.repositories import machine_power_log_repo, machine_repo
from app.services import smartthings_client
from app.services.machine_service import get_current_mode

logger = logging.getLogger(__name__)

_last_states: dict[int, bool] = {}
_last_cleanup: float = 0.0


def _parse_device_map() -> dict[int, str]:
    result: dict[int, str] = {}
    raw = (settings.smartthings_device_map or "").strip()
    if raw:
        for pair in raw.split(","):
            pair = pair.strip()
            if ":" in pair:
                mid, did = pair.split(":", 1)
                result[int(mid.strip())] = did.strip()
    if not result and settings.smartthings_device_id and settings.smartthings_machine_id:
        result[settings.smartthings_machine_id] = settings.smartthings_device_id
    return result


def _calc_interval(mode: str) -> float:
    kst_hour = (datetime.now(timezone.utc).hour + 9) % 24
    if kst_hour < 7 or kst_hour >= 22:
        return 15 * 60.0
    return {"A": 60.0, "B": 120.0, "C": 480.0}.get(mode, 120.0)


async def _apply_state_change(machine_id: int, is_running: bool) -> None:
    from app.api.iot import _handle_available, _handle_in_use

    db = SessionLocal()
    try:
        machine = machine_repo.get_by_id(db, machine_id)
        if not machine:
            return
        new_status = "in_use" if is_running else "available"
        if machine.status == new_status:
            return
        machine_repo.set_status(db, machine, new_status)
        gender = machine.gender_restriction
    finally:
        db.close()

    genders = ["male", "female"] if gender is None else [gender]
    if is_running:
        for g in genders:
            await _handle_in_use(g)
    else:
        for g in genders:
            await _handle_available(g)


async def poll_loop() -> None:
    global _last_cleanup

    if not settings.smartthings_pat:
        logger.info("SMARTTHINGS_PAT 미설정 — SmartThings polling 비활성")
        return

    device_map = _parse_device_map()
    if not device_map:
        logger.info("SmartThings device map 미설정 — polling 비활성")
        return

    logger.info(f"SmartThings polling 시작: {device_map}")

    while True:
        db = SessionLocal()
        try:
            mode = get_current_mode(db, "male")
        finally:
            db.close()

        interval = _calc_interval(mode)

        for machine_id, device_id in device_map.items():
            try:
                power_w = await smartthings_client.get_power_w(device_id)

                db = SessionLocal()
                try:
                    machine_power_log_repo.create(db, machine_id, power_w)
                finally:
                    db.close()

                is_running = power_w >= settings.power_threshold_w
                prev = _last_states.get(machine_id)
                if prev != is_running:
                    logger.info(f"machine {machine_id}: {'가동' if is_running else '정지'} ({power_w:.1f}W)")
                    _last_states[machine_id] = is_running
                    await _apply_state_change(machine_id, is_running)

            except Exception as e:
                logger.warning(f"SmartThings polling error (machine {machine_id}): {e}")

        now = time.time()
        if now - _last_cleanup > 86400:
            db = SessionLocal()
            try:
                machine_power_log_repo.delete_old(db)
            finally:
                db.close()
            _last_cleanup = now

        await asyncio.sleep(interval)
