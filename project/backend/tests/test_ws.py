"""
WebSocket 연결 및 초기 메시지 테스트
"""
from tests.conftest import register_and_login


def test_ws_connect_and_initial_state(seeded_client):
    token = register_and_login(seeded_client, "wsuser", "male")
    with seeded_client.websocket_connect(f"/ws?token={token}") as ws:
        data = ws.receive_json()
        assert data["type"] == "machines_updated"
        assert data["mode"] in ("A", "B", "C")
        assert "floors" in data


def test_ws_invalid_token_rejected(seeded_client):
    from starlette.websockets import WebSocketDisconnect
    try:
        with seeded_client.websocket_connect("/ws?token=invalid.token.here") as ws:
            ws.receive_json()
        assert False, "Should have raised WebSocketDisconnect"
    except WebSocketDisconnect as e:
        assert e.code == 1008


def test_ws_connect_female(seeded_client):
    token = register_and_login(seeded_client, "wsuser_f", "female")
    with seeded_client.websocket_connect(f"/ws?token={token}") as ws:
        data = ws.receive_json()
        assert data["type"] == "machines_updated"