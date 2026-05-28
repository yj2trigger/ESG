"""
세탁기 polling 상태 동기화 테스트

[재현 버그]
_last_states[id]=True (폴러가 '가동 중'으로 기억)이지만
DB status='available' (관리자 수동 변경 등)인 상태에서
다음 poll에서 56W를 읽어도 DB가 교정되지 않는 문제.

prev_running == is_running 이라 _apply_state_change를 호출하지 않아
56W인데도 '이용 가능'으로 영구 표시됨.

[수정]
_last_states와 _apply_state_change를 항상 갱신.
no-op 여부는 _apply_state_change 내부(previous_status == new_status)에서 처리.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from app.models.machine import Machine
from app.services import smartthings_poller


async def test_desync_db_corrected_when_last_states_mismatch(db):
    """
    _last_states=True, DB=available, 전력=56W
    → DB가 in_use로 교정되어야 한다.
    """
    machine = Machine(floor=1, machine_number=1, status="available", gender_restriction="male")
    db.add(machine)
    db.commit()
    machine_id = machine.id

    # 불일치 세팅: 폴러는 '가동 중'으로 기억, DB는 'available'
    smartthings_poller._last_states[machine_id] = True

    # SessionLocal()이 테스트 DB 세션을 반환하도록 패치
    # close()는 no-op으로 오버라이드 (테스트 세션 조기 종료 방지)
    session_mock = MagicMock(wraps=db)
    session_mock.close = MagicMock()

    with (
        patch("app.services.smartthings_poller.SessionLocal", return_value=session_mock),
        patch("app.services.smartthings_poller.machine_power_log_repo.create"),
        patch(
            "app.services.smartthings_poller.smartthings_client.get_power_w",
            new_callable=AsyncMock,
            return_value=56.0,
        ),
        patch("app.api.iot._handle_in_use", new_callable=AsyncMock),
        patch("app.api.iot._handle_available", new_callable=AsyncMock),
        patch("app.api.iot._handle_machine_started", new_callable=AsyncMock),
    ):
        await smartthings_poller._poll_single_machine(
            machine_id, "test-device-id",
            start_threshold=10.0,
            stop_threshold=5.0,
        )

    db.refresh(machine)
    assert machine.status == "in_use", (
        f"56W(>=10W)인데도 status={machine.status} — "
        f"_last_states 불일치 시 DB 교정 실패"
    )


async def test_no_change_when_already_in_use(db):
    """
    DB=in_use, _last_states=True, 전력=56W
    → DB 변경 없이 in_use 유지.
    """
    machine = Machine(floor=1, machine_number=1, status="in_use", gender_restriction="male")
    db.add(machine)
    db.commit()
    machine_id = machine.id

    smartthings_poller._last_states[machine_id] = True

    session_mock = MagicMock(wraps=db)
    session_mock.close = MagicMock()

    with (
        patch("app.services.smartthings_poller.SessionLocal", return_value=session_mock),
        patch("app.services.smartthings_poller.machine_power_log_repo.create"),
        patch(
            "app.services.smartthings_poller.smartthings_client.get_power_w",
            new_callable=AsyncMock,
            return_value=56.0,
        ),
        patch("app.api.iot._handle_in_use", new_callable=AsyncMock) as mock_in_use,
        patch("app.api.iot._handle_available", new_callable=AsyncMock),
    ):
        await smartthings_poller._poll_single_machine(
            machine_id, "test-device-id",
            start_threshold=10.0,
            stop_threshold=5.0,
        )

    db.refresh(machine)
    assert machine.status == "in_use"
    mock_in_use.assert_not_called()  # 상태 변화 없으므로 broadcast 없음


async def test_machine_transitions_to_available_when_power_low(db):
    """
    DB=in_use, _last_states=True, 전력=2W (<stop_threshold=5W)
    → DB가 available로 전환되어야 한다.
    """
    machine = Machine(floor=1, machine_number=1, status="in_use", gender_restriction="male")
    db.add(machine)
    db.commit()
    machine_id = machine.id

    smartthings_poller._last_states[machine_id] = True

    session_mock = MagicMock(wraps=db)
    session_mock.close = MagicMock()

    with (
        patch("app.services.smartthings_poller.SessionLocal", return_value=session_mock),
        patch("app.services.smartthings_poller.machine_power_log_repo.create"),
        patch(
            "app.services.smartthings_poller.smartthings_client.get_power_w",
            new_callable=AsyncMock,
            return_value=2.0,
        ),
        patch("app.api.iot._handle_in_use", new_callable=AsyncMock),
        patch("app.api.iot._handle_available", new_callable=AsyncMock) as mock_available,
    ):
        await smartthings_poller._poll_single_machine(
            machine_id, "test-device-id",
            start_threshold=10.0,
            stop_threshold=5.0,
        )

    db.refresh(machine)
    assert machine.status == "available", f"2W인데도 status={machine.status}"
    mock_available.assert_called_once()  # 대기열 알림 호출 확인


async def test_soft_reserved_ignored_when_power_low(db):
    """
    DB=soft_reserved, _last_states=None, 전력=3W (<start_threshold=10W)
    → 예약 유지 (available로 전환되면 안 됨).
    """
    from datetime import timedelta, timezone
    from datetime import datetime

    machine = Machine(
        floor=1, machine_number=1, status="soft_reserved",
        gender_restriction="male",
        reserved_by_user_id=None,
        reserved_until=datetime.now(timezone.utc) + timedelta(minutes=9),
    )
    db.add(machine)
    db.commit()
    machine_id = machine.id

    smartthings_poller._last_states.pop(machine_id, None)  # 미확인 상태

    session_mock = MagicMock(wraps=db)
    session_mock.close = MagicMock()

    with (
        patch("app.services.smartthings_poller.SessionLocal", return_value=session_mock),
        patch("app.services.smartthings_poller.machine_power_log_repo.create"),
        patch(
            "app.services.smartthings_poller.smartthings_client.get_power_w",
            new_callable=AsyncMock,
            return_value=3.0,
        ),
        patch("app.api.iot._handle_available", new_callable=AsyncMock) as mock_available,
    ):
        await smartthings_poller._poll_single_machine(
            machine_id, "test-device-id",
            start_threshold=10.0,
            stop_threshold=5.0,
        )

    db.refresh(machine)
    assert machine.status == "soft_reserved", (
        f"soft_reserved 예약이 대기 중 전력 낙음으로 파곴됨: status={machine.status}"
    )
    mock_available.assert_not_called()
