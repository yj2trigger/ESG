"""
헬스체크 엔드포인트 테스트
— 테스트 구조가 정상 동작하는지 확인하는 기본 테스트입니다.
"""


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
