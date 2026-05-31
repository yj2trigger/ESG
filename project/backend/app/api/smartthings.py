import logging
import os

import httpx
from fastapi import APIRouter, BackgroundTasks, Request

from app.config import settings
from app.core.database import SessionLocal
from app.repositories import machine_power_log_repo, machine_repo, machine_status_log_repo, system_settings_repo
from app.services import st_install

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/smartthings", tags=["smartthings"])

_last_states: dict[str, bool] = {}


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


@router.post("/webhook")
async def smartthings_webhook(request: Request, background_tasks: BackgroundTasks):
    body = await request.json()
    lifecycle = body.get("lifecycle")

    if lifecycle == "CONFIRMATION":
        confirmation_url = body.get("confirmationData", {}).get("confirmationUrl")
        if confirmation_url:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.get(confirmation_url)
            logger.info(f"CONFIRMATION 완료: {confirmation_url}")
        return {}

    if lifecycle == "PING":
        return {"pingData": {"challenge": body["pingData"]["challenge"]}}

    if lifecycle in ("INSTALL", "UPDATE"):
        data = body.get("installData") or body.get("updateData")
        auth_token = data["authToken"]
        refresh_token = data["refreshToken"]
        installed_app_id = data["installedApp"]["installedAppId"]

        db = SessionLocal()
        try:
            system_settings_repo.set_str(db, "st_auth_token", auth_token)
            system_settings_repo.set_str(db, "st_refresh_token", refresh_token)
            system_settings_repo.set_str(db, "st_installed_app_id", installed_app_id)
        finally:
            db.close()

        device_ids = list(_device_map().keys())
        background_tasks.add_task(
            st_install.subscribe_devices,
            installed_app_id,
            auth_token,
            device_ids,
            clear_first=(lifecycle == "UPDATE"),
        )

        response_key = "installData" if lifecycle == "INSTALL" else "updateData"
        return {response_key: {}}

    if lifecycle == "UNINSTALL":
        db = SessionLocal()
        try:
            for key in ("st_auth_token", "st_refresh_token", "st_installed_app_id"):
                system_settings_repo.set_str(db, key, "")
        finally:
            db.close()
        return {"uninstallData": {}}

    if lifecycle == "EVENT":
        events = body.get("eventData", {}).get("events", [])
        dm = _device_map()
        for event in events:
            dev_evt = event.get("deviceEvent")
            if not dev_evt:
                continue
            if dev_evt.get("capability") != "powerMeter" or dev_evt.get("attribute") != "power":
                continue
            device_id = dev_evt.get("deviceId", "")
            machine_id = dm.get(device_id)
            if not machine_id:
                continue
            try:
                power_w = float(dev_evt["value"])
            except (KeyError, TypeError, ValueError):
                continue

            prev = _last_states.get(device_id)
            is_running = (
                power_w >= settings.stop_threshold_w if prev is True
                else power_w >= settings.power_threshold_w
            )
            _last_states[device_id] = is_running
            background_tasks.add_task(_process_event, machine_id, is_running, power_w)

        return {"eventData": {}}

    return {}


async def _process_event(machine_id: int, is_running: bool, power_w: float) -> None:
    from app.api.iot import _handle_available, _handle_in_use, _handle_machine_started

    db = SessionLocal()
    try:
        machine_power_log_repo.create(db, machine_id, power_w)
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

        changed = previous_status != new_status
        reserved_user_id = (
            machine.reserved_by_user_id
            if previous_status == "soft_reserved" and new_status == "in_use"
            else None
        )
        machine_floor = machine.floor
        machine_number = machine.machine_number
        gender = machine.gender_restriction

        if changed:
            machine_repo.set_status(db, machine, new_status)

        machine_status_log_repo.create(
            db, machine, new_status, "webhook",
            previous_status=previous_status, is_running=is_running, changed=changed,
        )
    finally:
        db.close()

    if not changed:
        return

    genders = ["male", "female"] if gender is None else [gender]
    if new_status == "in_use":
        if reserved_user_id:
            await _handle_machine_started(reserved_user_id, genders[0], machine_floor, machine_number)
        for g in genders:
            await _handle_in_use(g)
    else:
        for g in genders:
            await _handle_available(g)
