import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError
from sqlalchemy.orm import Session

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
        # Send initial dashboard state on connect
        dashboard = get_dashboard(db, gender)
        await ws.send_json({"type": "machines_updated", **dashboard.model_dump()})
    finally:
        db.close()

    try:
        while True:
            # Keepalive: receive pings, check for expired reservations + queue notify
            try:
                await asyncio.wait_for(ws.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                pass  # No message within 30s — still alive, continue loop

            # Lazy expiration check + queue notification
            db = SessionLocal()
            try:
                released = machine_repo.release_expired(db)
                if released:
                    await _notify_queue_and_broadcast(db, gender)
            finally:
                db.close()

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(ws, gender)


async def _notify_queue_and_broadcast(db: Session, gender: str) -> None:
    """When machines free up: notify first waiter (if any), then broadcast mode update."""
    waiter = queue_repo.get_next_waiter(db, gender)
    if waiter:
        machine = machine_repo.get_first_available(db, gender)
        if machine:
            machine_repo.soft_reserve(db, machine, waiter.user_id)
            queue_repo.leave(db, waiter.user_id)
            await manager.send_to_user(
                waiter.user_id,
                gender,
                {
                    "type": "queue_notify",
                    "machine": {
                        "id": machine.id,
                        "floor": machine.floor,
                        "machine_number": machine.machine_number,
                    },
                    "reserved_until": machine.reserved_until.isoformat() if machine.reserved_until else None,
                },
            )

    # Broadcast updated dashboard to all in gender channel
    dashboard = get_dashboard(db, gender)
    await manager.broadcast(gender, {"type": "machines_updated", **dashboard.model_dump()})