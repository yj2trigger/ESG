import asyncio
import logging
import os
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
    """SMARTTHINGS_DEVICE_01, SMARTTHINGS_DEVICE_02 형식 환경변수 자동 파싱.
    숫자 부분 = ESG machine_id."""
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


def _calc_interval(mode: str) -> float:
    """ADR-007: 이용 가능 세탁기 적을수록 polling 빈도 높임."""
    kst_hour = (datetime.now(timezone.utc).hour + 9) % 24
    if kst_hour < 7 or kst_hour >= 22:
        return 900.0
    return {"A": 480.0, "B": 120.0, "C": 60.0}.get(mode, 120.0)


def _get_mode() -> str:
    """DB에서 mode 읽기. 실패 시 기본값 A 반환."""
    try:
        db = SessionLocal()
        try:
            return get_current_mode(db, "male")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"mode 조회 실패, 기본값 A 사용: {e}")
        return "A"


async def _apply_state_change(machine_id: int, is_running: bool) -> None:
    from app.api.iot import _handle_available, _handle_in_use, _handle_machine_started

    db = SessionLocal()
    try:
        machine = machine_repo.get_by_id(db, machine_id)
        if not machine:
            return

        previous_status = machine.status

        if previous_status == "soft_reserved":
            if not is_running:
                return
            new_status = "in_use"
        else:
            new_status = "in_use" if is_running else "available"

        if previous_status == new_status:
            return

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

    # config.py 값 직접 사용 (DB 뾁 없음)
    start_threshold = settings.power_threshold_w  # 20W
    stop_threshold = settings.stop_threshold_w    # 5W
    logger.info(f"SmartThings polling 시작: {device_map} | start={start_threshold}W stop={stop_threshold}W")

    while True:
        mode = _get_mode()
        interval = _calc_interval(mode)

        for machine_id, device_id in device_map.items():
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

                # 히스테리시스: 이전 상태에 따라 다른 임계값 적용
                # - 이전 가동 중: power < stop_threshold(5W)일 때만 정지
                # - 이전 정지/미확인: power >= start_threshold(20W)일 때 가동
                prev_running = _last_states.get(machine_id)
                if prev_running is True:
                    is_running = power_w >= stop_threshold
                else:
                    is_running = power_w >= start_threshold

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
                        logger.warning(f"상태 변경 실패 (machine {machine_id}): {e}")

            except Exception as e:
                logger.warning(f"SmartThings polling error (machine {machine_id}): {e}")

        now = time.time()
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

        next_interval = _calc_interval(mode)
        try:
            from app.core.ws_manager import manager
            for gender in ["male", "female"]:
                await manager.broadcast(gender, {
                    "type": "poll_tick",
                    "next_interval_sec": int(next_interval),
                })
        except Exception as e:
            logger.warning(f"poll_tick 브로드쾐스트 실패: {e}")

        await asyncio.sleep(next_interval)
