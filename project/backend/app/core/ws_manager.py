import asyncio
from typing import Optional

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        # gender → list of (user_id, websocket)
        self._conns: dict[str, list[tuple[int, WebSocket]]] = {"male": [], "female": []}

    async def connect(self, ws: WebSocket, gender: str, user_id: int) -> None:
        await ws.accept()
        self._conns[gender].append((user_id, ws))

    def disconnect(self, ws: WebSocket, gender: str) -> None:
        self._conns[gender] = [(uid, w) for uid, w in self._conns[gender] if w is not ws]

    async def broadcast(self, gender: str, message: dict) -> None:
        dead: list[WebSocket] = []
        for _, ws in list(self._conns[gender]):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, gender)

    async def send_to_user(self, user_id: int, gender: str, message: dict) -> None:
        for uid, ws in list(self._conns[gender]):
            if uid == user_id:
                try:
                    await ws.send_json(message)
                except Exception:
                    self.disconnect(ws, gender)

    def user_connected(self, user_id: int, gender: str) -> bool:
        return any(uid == user_id for uid, _ in self._conns[gender])


# Singleton — imported by all routers
manager = ConnectionManager()