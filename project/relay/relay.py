#!/usr/bin/env python3
"""
ESG 세탁기 로컈 릴레이

SmartThings API를 로컈 IP로 폴링하여 ESG IoT 엔드포인트로 중계.
Fly.io 데이터센터 IP가 SmartThings에서 차단되는 문제 우회.

설치:
    pip install httpx python-dotenv

실행:
    python relay.py
"""

import logging
import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

# 환경변수 또는 .env
SMARTTHINGS_PAT = os.environ["SMARTTHINGS_PAT"]
DEVICE_MACHINE_MAP: dict[str, int] = {}  # {smartthings_device_id: esg_machine_id}

# SMARTTHINGS_DEVICE_1=uuid, SMARTTHINGS_DEVICE_2=uuid 형식
for key, value in os.environ.items():
    if key.startswith("SMARTTHINGS_DEVICE_") and value.strip():
        machine_id = int(key[len("SMARTTHINGS_DEVICE_"):])
        DEVICE_MACHINE_MAP[value.strip()] = machine_id

if not DEVICE_MACHINE_MAP:
    raise SystemExit("SMARTTHINGS_DEVICE_XX 환경변수 미설정")

ESG_BASE_URL = os.getenv("ESG_BASE_URL", "https://esg-laundry-checker.fly.dev")
IOT_DEVICE_KEY = os.environ["IOT_DEVICE_KEY"]

START_THRESHOLD_W = float(os.getenv("START_THRESHOLD_W", "10"))
STOP_THRESHOLD_W = float(os.getenv("STOP_THRESHOLD_W", "5"))
POLL_INTERVAL_SEC = int(os.getenv("POLL_INTERVAL_SEC", "60"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

_last_running: dict[str, bool] = {}  # {device_id: is_running}


def get_power_w(device_id: str) -> float:
    r = httpx.get(
        f"https://api.smartthings.com/v1/devices/{device_id}/status",
        headers={"Authorization": f"Bearer {SMARTTHINGS_PAT}"},
        timeout=30.0,
    )
    r.raise_for_status()
    return float(r.json()["components"]["main"]["powerMeter"]["power"]["value"])


def send_status(machine_id: int, is_running: bool) -> None:
    r = httpx.post(
        f"{ESG_BASE_URL}/iot/machines/{machine_id}/status",
        json={"is_running": is_running},
        headers={"x-device-key": IOT_DEVICE_KEY},
        timeout=15.0,
    )
    r.raise_for_status()


def main() -> None:
    logger.info(f"ESG 릴레이 시작: {DEVICE_MACHINE_MAP}")
    logger.info(f"start={START_THRESHOLD_W}W stop={STOP_THRESHOLD_W}W interval={POLL_INTERVAL_SEC}s")
    logger.info(f"ESG 서버: {ESG_BASE_URL}")

    while True:
        for device_id, machine_id in DEVICE_MACHINE_MAP.items():
            try:
                power_w = get_power_w(device_id)

                # 히스테리시스: 이전 상태에 따라 다른 임계값 적용
                prev = _last_running.get(device_id)
                is_running = (
                    power_w >= STOP_THRESHOLD_W if prev is True
                    else power_w >= START_THRESHOLD_W
                )

                changed = prev != is_running
                _last_running[device_id] = is_running

                if changed:
                    logger.info(
                        f"machine {machine_id}: {'가동' if is_running else '정지'} "
                        f"({power_w:.1f}W)"
                    )

                send_status(machine_id, is_running)
                logger.debug(f"machine {machine_id}: {power_w:.1f}W → 전송 OK")

            except httpx.HTTPStatusError as e:
                logger.error(f"machine {machine_id} HTTP 오류: {e.response.status_code} {e}")
            except Exception as e:
                logger.error(f"machine {machine_id} 오류: {type(e).__name__}: {e}")

        time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()
