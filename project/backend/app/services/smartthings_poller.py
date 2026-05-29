import asyncio
import logging
import os
import time
from datetime import datetime, timezone

from app.config import settings
from app.core.database import SessionLocal
from app.repositories import machine_power_log_repo, machine_repo
from app.services import smartthings_client

logger = logging.getLogger(__name__)

_last_states: dict[int, bool] = {}
_last_polled: dict[int, float] = {}
_last_cleanup: float = 0.0


def _parse_device_map() -> dict[int, str]:
    result: dict[int, str] = {}
    prefix = "SMARTTHINGS_DEVICE_"
    for key, value in os.environ.items():
        if key.startswith(prefix) and value.strip():
            suffix = key[len(prefix):]
            try:
                result[int(suffix)] = value.strip()
            except ValueError:
                pass
    return result


def _get_priority_machine_ids(device_map: dict[int, str]) -> set[int]:
    """
    우선 polling 대상 최대 3대.
    - Mode A (available > 3): 층별 이용 가능 1대만 남은 층의 세탁기
    - Mode B (available 1~3): available 세탁기 자체 (사용 시작 빠른 감지)
    - Mode C (available 0): soft_reserved 세탁기 (가동 시작 감지)
    """
    try:
        from sqlalchemy import func
        from app.models.machine import Machine

        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            available_count = (
                db.query(func.count(Machine.id))
                .filter(Machine.status == "available")
                .scalar()
            ) or 0

            priority_ids: set[int] = set()

            if available_count > 3:
                # Mode A: 층별 1대만 남은 세탁기
                scarce_floors = (
                    db.query(Machine.floor)
                    .filter(Machine.status == "available")
                    .group_by(Machine.floor)
                    .having(func.count(Machine.id) == 1)
                    .all()
                )
                for (floor,) in scarce_floors:
                    m = (
                        db.query(Machine)
                        .filter(Machine.floor == floor, Machine.status == "available")
                        .first()
                    )
                    if m and m.id in device_map:
                        priority_ids.add(m.id)
                    if len(priority_ids) >= 3:
                        break
            elif available_count > 0:
                # Mode B (1~3대): available 세탁기 자체 우선 감지
                machines = (
                    db.query(Machine)
                    .filter(Machine.status == "available")
                    .limit(3)
                    .all()
                )
                priority_ids = {m.id for m in machines if m.id in device_map}
            else:
                # Mode C (0대): soft_reserved 세탁기 가동 시작 감지
                machines = (
                    db.query(Machine)
                    .filter(
                        Machine.status == "soft_reserved",
                        Machine.reserved_until > now,
                    )
                    .limit(3)
                    .all()
                )
                priority_ids = {m.id for m in machines if m.id in device_map}

            return priority_ids
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"priority machine 조회 실패: {e}")
        return set()


async def _poll_single_machine(
    machine_id: int,
    device_id: str,
    start_threshold: float,
    stop_threshold: float,
) -> None:
    try:
        power_w = await smartthings_client.get_power_w(device_id)

        try:
            db = SessionLocal()
            try:
                machine_power_log_repo.create(db, machine_id, power_w)
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"전력 로그 저장 실패 (machine {machine_id}): {e}")

        prev_running = _last_states.get(machine_id)
        is_running = (
            power_w >= stop_threshold if prev_running is True
            else power_w >= start_threshold
        )

        if prev_running != is_running:
            effective = stop_threshold if prev_running is True else start_threshold
            logger.info(
                f"machine {machine_id}: {'가동' if is_running else '정지'} "
                f"({power_w:.1f}W, 기준 {effective}W)"
            )

        _last_states[machine_id] = is_running
        try:
            await _apply_state_change(machine_id, is_running)
        except Exception as e:
            logger.warning(f"상태 변경 실패 (machine {machine_id}): {type(e).__name__}: {e}")

    except Exception as e:
        logger.warning(f"SmartThings polling error (machine {machine_id}): {type(e).__name__}: {e}")


async def _apply_state_change(machine_id: int, is_running: bool) -> None:
    from app.api.iot import _handle_available, _handle_in_use, _handle_machine_started

    db = SessionLocal()
    try:
        machine = machine_repo.get_by_id(db, machine_id)
        if not machine:
            return
        previous_status = machine.status
        if previous_status == "broken":
            return
        if previous_status == "soft_reserved":
            if not is_running:
                return
            new_status = "in_use"
        else:
            new_status = "in_use" if is_running else "available"
        if previous_status == new_status:
            return
        logger.info(f"machine {machine_id}: DB {previous_status} → {new_status}")
        reserved_user_id = (
            machine.reserved_by_user_id
            if previous_status == "soft_reserved" and new_status == "in_use"
            else None
        )
        machine_floor = machine.floor
        machine_number = machine.machine_number
        machine_repo.set_status(db, machine, new_status)
        gender = machine.gender_restriction
    finally:
        db.close()

    genders = ["male", "female"] if gender is None else [gender]
    if new_status == "in_use":
        if reserved_user_id:
            await _handle_machine_started(reserved_user_id, genders[0], machine_floor, machine_number)
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
        logger.info("SMARTTHINGS_DEVICE_XX 미설정 — polling 비활성")
        return

    start_threshold = settings.power_threshold_w
    stop_threshold = settings.stop_threshold_w
    slow_sec = settings.base_poll_sec
    fast_sec = slow_sec / max(settings.priority_poll_ratio, 1.0)

    logger.info(
        f"SmartThings polling 시작: {device_map} | "
        f"start={start_threshold}W stop={stop_threshold}W | "
        f"fast={fast_sec:.0f}s slow={slow_sec:.0f}s (ratio={settings.priority_poll_ratio}x)"
    )

    priority_ids: set[int] = set()
    last_priority_refresh: float = 0.0

    while True:
        now = time.time()

        if now - last_priority_refresh >= fast_sec:
            priority_ids = _get_priority_machine_ids(device_map)
            last_priority_refresh = now
            logger.debug(f"priority machines: {priority_ids}")

            next_tick = int(fast_sec if priority_ids else slow_sec)
            last_polled_at = int(max(_last_polled.values())) if _last_polled else int(now)
            try:
                from app.core.ws_manager import manager
                for gender in ["male", "female"]:
                    await manager.broadcast(gender, {
                        "type": "poll_tick",
                        "next_interval_sec": next_tick,
                        "fast_interval_sec": int(fast_sec),
                        "slow_interval_sec": int(slow_sec),
                        "priority_count": len(priority_ids),
                        "last_polled_at": last_polled_at,
                    })
            except Exception as e:
                logger.warning(f"poll_tick 브로드쾐스트 실패: {e}")

        for machine_id, device_id in device_map.items():
            interval = fast_sec if machine_id in priority_ids else slow_sec
            if now - _last_polled.get(machine_id, 0) >= interval:
                await _poll_single_machine(machine_id, device_id, start_threshold, stop_threshold)
                _last_polled[machine_id] = time.time()

        if now - _last_cleanup > 86400:
            try:
                db = SessionLocal()
                try:
                    machine_power_log_repo.delete_old(db)
                finally:
                    db.close()
            except Exception as e:
                logger.warning(f"오래된 전력 로그 정리 실패: {e}")
            _last_cleanup = now

        await asyncio.sleep(1)
