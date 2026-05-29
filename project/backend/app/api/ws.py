import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError
from sqlalchemy.orm import Session

from app.config import settings
from app.core.database import SessionLocal
from app.core.security import decode_token
from app.core.ws_manager import manager
from app.repositories import machine_repo, queue_repo, user_repo
from app.services.machine_service import get_dashboard

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, token: str):
    db: Session = SessionLocal()
    try:
        payload = decode_token(token)
        username: str = payload.get("sub", "")
        user = user_repo.get_by_username(db, username)
        if not user:
            await ws.close(code=1008)
            return
    except JWTError:
        await ws.close(code=1008)
        return
    finally:
        db.close()

    gender = user.gender
    user_id = user.id

    await manager.connect(ws, gender, user_id)

    db = SessionLocal()
    try:
        dashboard = get_dashboard(db, gender)
        await ws.send_json({"type": "machines_updated", **dashboard.model_dump()})
    finally:
        db.close()

    # 연결 즉시 poll_tick 전송 → 프론트엔드 '동기화 대기 중' 상태 제거
    _slow = settings.base_poll_sec
    _fast = _slow / max(settings.priority_poll_ratio, 1.0)
    await ws.send_json({
        "type": "poll_tick",
        "next_interval_sec": int(_fast),
        "fast_interval_sec": int(_fast),
        "slow_interval_sec": int(_slow),
        "priority_count": 0,
    })

    try:
        while True:
            try:
                await asyncio.wait_for(ws.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                pass

            db = SessionLocal()
            try:
                released = machine_repo.release_expired(db)
                expired_user_ids = queue_repo.reset_expired_notifications(db, gender)

                for uid in expired_user_ids:
                    await manager.send_to_user(
                        uid,
                        gender,
                        {"type": "queue_offer_expired", "message": "5분이 경과하여 대기열 맨 뒤로 이동되었습니다"},
                    )

                if released or expired_user_ids:
                    await _notify_queue_and_broadcast(db, gender)
            finally:
                db.close()

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(ws, gender)


async def _notify_queue_and_broadcast(db: Session, gender: str) -> None:
    """When machines free up: offer to first waiter (5-min hold), then broadcast mode update."""
    waiter = queue_repo.get_next_waiter(db, gender)
    if waiter:
        machine = machine_repo.get_first_available(db, gender)
        if machine:
            machine_repo.soft_reserve(db, machine, waiter.user_id, duration_minutes=5)
            entry = queue_repo.set_notified(db, waiter, accept_minutes=5)
            await manager.send_to_user(
                waiter.user_id,
                gender,
                {
                    "type": "queue_offer",
                    "machine": {
                        "id": machine.id,
                        "floor": machine.floor,
                        "machine_number": machine.machine_number,
                    },
                    "accept_until": entry.expires_at.isoformat() if entry.expires_at else None,
                },
            )

    dashboard = get_dashboard(db, gender)
    await manager.broadcast(gender, {"type": "machines_updated", **dashboard.model_dump()})

    await broadcast_queue_positions(db, gender)


async def broadcast_queue_positions(db: Session, gender: str) -> None:
    all_waiting = queue_repo.get_all_waiting(db, gender)
    total = len(all_waiting)
    for i, entry in enumerate(all_waiting):
        await manager.send_to_user(
            entry.user_id,
            gender,
            {"type": "queue_position_updated", "position": i + 1, "total": total},
        )
