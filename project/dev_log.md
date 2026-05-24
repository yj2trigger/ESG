# ESG 프로젝트 개발 사고 기록

> Claude가 구현을 진행하면서 내린 판단, 막혔던 지점, 플레이스홀더로 남긴 것들을 기록한 문서.
> 설계(design_progress.md)가 WHY라면, 이 문서는 HOW + WHY NOT의 기록이다.

---

## 0. 시작 전 — 레포 연결 시 판단

### 문제
로컬 `project/` 폴더에 `design_progress.md`, `full_plan.md`, `text.txt`가 이미 존재했고,
GitHub 레포에도 동일 파일이 있었으나 SHA가 달랐다.

### 판단
- `full_plan.md`: SHA 동일 → 충돌 없음
- `design_progress.md`, `text.txt`: SHA 불일치 → 사용자 선택 필요
- 사용자가 "원격 받기"를 선택 → `git checkout -f -b main --track origin/main`으로 강제 체크아웃

### 결과
원격 버전으로 덮어쓴 뒤, 로컬에만 있던 `ppt/`, `프롬프트/` 폴더는 untracked 상태로 유지됨.

---

## 1. 테스트 환경 구축 — 예상치 못한 호환성 문제들

### 1-1. SQLAlchemy 2.0.30 + Python 3.14 비호환

**증상**: `TypeError: Can't replace canonical symbol for '__firstlineno__' with new int value 615`

**원인**: Python 3.14에서 `__firstlineno__` 속성이 추가됐는데,
SQLAlchemy 2.0.30의 `FastIntFlag` 구현이 이 이름을 symbol로 등록하려다 충돌.

**판단**: requirements.txt에는 2.0.30으로 고정돼 있지만, CI는 Python 3.11을 사용하므로
로컬(Python 3.14)에서만 문제. 최신 버전(2.0.49)으로 업그레이드.

> **이후 반영**: requirements.txt를 `sqlalchemy==2.0.49`로 고정.
> CI에서는 Python 3.11 사용하므로 둘 다 OK.

---

### 1-2. psycopg2-binary Windows 빌드 실패

**증상**: pip install 중 `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xb1`

**원인**: Windows 한글 환경에서 psycopg2-binary 빌드 중 환경 정보 읽기 실패.

**판단**: 테스트는 SQLite를 쓰기 때문에 psycopg2 자체가 불필요.
→ 테스트 실행에서는 psycopg2 없이 진행. requirements.txt에는 유지(배포 환경은 Linux).

> **플레이스홀더**: psycopg2-binary는 도커/Railway 환경에서만 실제로 필요.
> 로컬 테스트에서는 영구적으로 SQLite 사용.

---

### 1-3. conftest.py import 순서 문제

**증상**: `app.core.database`를 import하는 순간 PostgreSQL 연결 시도 → `ModuleNotFoundError: No module named 'psycopg2'`

**원인**: `database.py`의 `engine = create_engine(settings.database_url)` 가 **모듈 수준(module-level)**에서 실행됨.
conftest에서 DB override를 하기 전에 이미 실행되어 버림.

**판단**: conftest 최상단(모든 import 전)에 `os.environ["DATABASE_URL"] = "sqlite:///./test.db"` 삽입.
pydantic-settings가 `Settings()` 초기화 시 이 env var를 읽어서 SQLite URL을 사용하게 됨.

```python
# conftest.py 최상단 — 반드시 app import 전에 위치해야 함
import os
os.environ["DATABASE_URL"] = "sqlite:///./test.db"

import pytest
from app.main import app  # 이제 SQLite engine으로 초기화됨
```

---

### 1-4. bcrypt 5.x + passlib 1.7.4 비호환

**증상**: `ValueError: password cannot be longer than 72 bytes, truncate manually if necessary`

**원인**: passlib 1.7.4는 bcrypt 백엔드 로딩 시 긴 비밀번호로 자체 테스트를 수행함.
bcrypt 5.x에서 72바이트 초과 시 silent truncation 대신 ValueError를 raise하도록 변경됨.
passlib이 이 변경을 모르고 예외를 catch하지 않음.

**판단**: bcrypt를 4.x로 다운그레이드. passlib은 아직 bcrypt 5.x를 지원하지 않음.
requirements.txt에 `bcrypt==4.3.0` 고정.

---

### 1-5. tsconfig.node.json 누락

**증상**: vitest 실행 시 `ENOENT: no such file or directory, open '...\tsconfig.node.json'`

**원인**: `tsconfig.json`이 `references: [{ path: "./tsconfig.node.json" }]`를 가지고 있으나,
해당 파일이 git에 커밋되지 않음.

**판단**: Vite 표준 설정 파일 직접 생성.

---

## 2. 구현 3단계 (Auth) — 설계 → 코드 전환 시 판단

### 2-1. 레이어 분리 결정

설계 문서는 `api/ → services/ → repositories/` 구조를 명시함.
처음엔 "간단하니까 service 없이 API에서 직접 repo 호출해도 되지 않나?" 생각했으나:

- `register()`는 중복 체크 + 해싱 + 토큰 생성 3단계 → 비즈니스 로직이 충분히 존재
- 나중에 `login_with_google()` 등 추가 시 service layer 없으면 API layer 비대해짐

→ **레이어 분리 유지**.

---

### 2-2. TokenResponse에 user info 포함

설계: JWT만 반환. 프론트에서 JWT decode해서 user info 추출.

**판단**: 프론트에서 JWT decode를 하려면 `jwt-decode` 패키지가 필요하고,
secret key 없이도 decode는 가능하지만 라이브러리 추가 없이 구현이 지저분해짐.

→ **API response에 username/gender/role 직접 포함**. JWT payload와 redundant하지만 클라이언트 코드가 단순해짐.

```python
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str    # 추가
    gender: str      # 추가
    role: str        # 추가
```

---

### 2-3. authStore gender vs user 이중 구조

초기 설계: authStore에 `gender` 하나만.

구현하면서 보니: gender 선택은 로그인 **전** 단계이고, 실제 인증 후에는 `AuthUser` 객체가 필요.
그런데 회원가입 폼에서 gender를 미리 선택해서 넘겨야 하므로 `gender`는 그대로 유지.

→ **`gender` (pre-auth 선택값) + `user` (post-auth 전체 정보) 두 필드 유지**.
`setUser()` 시 `gender`도 `user.gender`로 자동 sync.

---

### 2-4. 라우팅 흐름 확정

```
미로그인 + gender 없음  →  /gender
미로그인 + gender 있음  →  /login (register or login)
로그인됨               →  / (DashboardPage)
```

App.tsx에서 이 분기를 처리. 각 페이지는 자기 진입 조건을 스스로 체크해서 redirect.

---

## 3. 구현 4단계 (Machines) — Mode 계산 핵심 로직

### 3-1. count_available의 lazy expiration 반영

`count_available()`이 단순히 `status == 'available'`만 세면 안 됨.
`soft_reserved`이지만 `reserved_until < now()`인 세탁기도 사실상 이용 가능.

→ SQL 조건:
```sql
WHERE (status = 'available')
   OR (status = 'soft_reserved' AND reserved_until < NOW())
```

이렇게 하지 않으면 Mode 계산이 실제보다 비관적으로 나옴.

---

### 3-2. GET /machines 인증 필수인데 403 반환

FastAPI의 `HTTPBearer`는 Authorization 헤더가 없으면 자동으로 403을 반환함.
설계 문서에는 "인증 필요"만 명시. 401이 맞지 않나 생각했으나:

- FastAPI 기본 동작이 403이고,
- 테스트 코드를 `assert response.status_code == 403`으로 이미 작성함.
- RFC 상으로도 둘 다 허용되므로 그대로 유지.

---

### 3-3. 시드 데이터 실제 기숙사 환경 반영

`design_progress.md`에 명시된 환경:
- 1~2층: 공용 9대
- 3층 이상: 층별 성별 구분 1~2대

→ seed 함수:
- 1층: 공용 5대, 2층: 공용 4대 (총 9대)
- 3층: 남성 2대, 4~5층: 남성 각 1대
- 6층: 여성 2대, 7~8층: 여성 각 1대

**현재 플레이스홀더**: 실제 기숙사 층 수/배치는 미확정. 나중에 관리자 페이지에서 조정 가능하도록 설계.

---

## 4. 구현 5단계 (Soft Reserve + Queue)

### 4-1. Lazy expiration vs APScheduler

설계 문서에 "lazy expiration" 명시.

**판단**: 프로토타입에서 APScheduler/Celery 같은 작업 스케줄러 추가는 over-engineering.
→ 매 API 요청 시 `release_expired()` 호출. 요청이 없으면 만료가 안 되는 단점이 있으나,
WebSocket keepalive(30초마다)가 이를 보완함.

> **확장 시 메모**: 실서비스 전환 시 APScheduler로 정확한 타이머 구현 필요.
> 현재는 "최대 30초 지연" 수준의 정확도.

---

### 4-2. QueueEntry user_id unique constraint

처음엔 unique 없이 구현했다가, 중복 등록 방지 로직을 `queue_repo.join()`에서 DB 조회로 체크.
→ DB 레벨에서도 unique를 걸어서 이중 방어. (만약 race condition이 생겨도 DB가 막음)

```python
user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
```

---

### 4-3. Mode 검증 위치

Mode B/C 진입 조건 검증을 어디서 할지:
- API layer에서 → 얇은 API, 검증 로직 분산
- Service layer에서 → 비즈니스 로직 집중

→ **Service layer**에서 검증. API는 요청 받아서 service 호출하고 반환만 함.

```python
def join_queue(db, user):
    mode = get_current_mode(db, user.gender)  # service layer에서 mode 체크
    if mode != "C":
        raise HTTPException(400, f"현재 Mode {mode}입니다")
```

---

### 4-4. Mode B: "사용하시겠습니까?" 버튼 이후 상태

Mode B에서 버튼을 누르면:
1. 세탁기 1대 배정 (soft_reserve)
2. 해당 사용자에게만 층+번호 공개
3. 다른 사용자에게는 해당 세탁기가 "이용중"으로 표시됨

→ `MachineRequestResponse`에 `assigned_machine`과 `reserved_until` 반환.
프론트에서 이를 받아 해당 사용자에게만 보여줌.

**플레이스홀더**: 같은 사용자가 반복 요청할 때 차단 로직 없음.
현재는 Mode B 자체가 세탁기가 1~3대일 때만 활성화되므로, 계속 누르면 세탁기가 빨리 소진됨.
→ 나중에 "이미 예약 중인 사용자는 다시 요청 불가" 검증 추가 필요.

---

## 5. 구현 6단계 (WebSocket)

### 5-1. ConnectionManager 싱글톤

FastAPI는 여러 worker가 뜰 수 있어서 싱글톤 in-memory 방식은 멀티 프로세스에서 문제.
프로토타입에서는 단일 worker만 사용하므로 OK.

> **확장 시 메모**: 실서비스에서는 Redis pub/sub 또는 Redis Streams로 교체 필요.
> 현재 `ws_manager.py`의 `manager` 객체를 Redis 기반으로 교체하면 됨 (인터페이스 유지).

---

### 5-2. WebSocket에서 DB 의존성 주입 방식

FastAPI `Depends(get_db)`는 WebSocket 엔드포인트에서도 동작하지만,
세션이 연결 전체 수명 동안 열려 있으면 리소스 낭비.

→ 접속 검증(토큰 확인)과 초기 상태 전송 시에만 짧게 `SessionLocal()`로 직접 열고 닫음.
30초 keepalive 루프에서는 만료 체크 필요 시만 다시 열고 닫음.

```python
db = SessionLocal()
try:
    released = machine_repo.release_expired(db)
finally:
    db.close()
```

---

### 5-3. Queue notify 타이밍 문제

이상적인 흐름: 세탁기가 반납(in_use → available)되는 순간 대기자에게 즉시 알림.

**현실**: 더미 데이터 환경에서는 "반납"이 자동으로 일어나지 않음.
soft_reserve 만료(10분 후)만이 "세탁기가 다시 이용 가능해지는" 트리거.

→ WebSocket keepalive(30초)마다 `release_expired()` 실행 후 대기자 확인.
즉시 알림이 아닌 **최대 30초 지연** 알림.

> **확장 시 메모**: IoT 연결 시 `machine_repo`의 `update_status()` 메서드를 추가하고,
> 그 호출부에서 `_notify_queue_and_broadcast()`를 트리거하면 즉시 알림 가능.
> Repository Layer만 교체 = 비즈니스 로직 변경 없음.

---

### 5-4. vite-env.d.ts 누락

`import.meta.env.VITE_API_URL` 사용 시 TypeScript 타입 오류 발생.
Vite 프로젝트는 `src/vite-env.d.ts`에 타입 선언이 있어야 함.
이 파일이 git에 커밋되지 않아서 처음엔 `as` 캐스팅으로 우회했다가,
제대로 `vite-env.d.ts` 생성으로 수정.

---

## 6. 전체적인 "이게 있어야 저게 됨" 의존 관계

```
conftest.py DATABASE_URL 설정 (import 전)
    ↓
SQLite engine으로 app 초기화
    ↓
테이블 생성 (Base.metadata.create_all)
    ↓
시드 데이터 (machine_repo.seed)
    ↓
seeded_client fixture
    ↓
register_and_login helper (인증 토큰)
    ↓
세탁기/대기열/WS 테스트
```

```
User 모델 (users 테이블)
    ↓ ForeignKey
Machine 모델 (machines 테이블) ← reserved_by_user_id
QueueEntry 모델 (queue_entries 테이블) ← user_id
```

```
get_current_user (JWT decode → DB lookup)
    ↓ 사용
GET /machines, POST /machines/request
POST /queue/join, DELETE /queue/leave
WS /ws?token=...
```

---

## 7. 현재 플레이스홀더 / 미구현 목록

| 항목 | 현재 상태 | 이유 | 다음 단계 |
|------|----------|------|----------|
| 세탁기 시드 데이터 | 하드코딩 더미 | IoT 미연결 | 관리자 페이지에서 조정 |
| soft_reserve 재요청 방지 | 없음 | 프로토타입 scope 밖 | user당 active reserve 1개 제한 추가 |
| WS 알림 지연 | 최대 30초 | lazy expiration | IoT 연결 시 push 방식으로 전환 |
| 동일 사용자 중복 WS 연결 | 허용 | 단순화 | 재연결 시 이전 연결 해제 처리 |
| 세탁기 상태 직접 변경 (관리자) | 없음 | 관리자 페이지 미구현 | `/admin/machines/{id}` PATCH |
| 비밀번호 변경 / 탈퇴 | 없음 | MVP 외 | 나중에 추가 |
| Rate limiting | 없음 | 프로토타입 | `slowapi` 추가 (설계 9단계에 명시) |
| Docker lifespan seed | 없음 | 테스트에서만 seed | main.py lifespan에 seed 추가 필요 (7단계) |
| 계정 중복 가입 악용 | username 중복만 차단 | 프로토타입 scope 밖 | **카카오 OAuth 연동**: 카카오 계정 1개당 계정 1개로 제한. `python-social-auth` 또는 `authlib` 사용, `/auth/kakao` 엔드포인트 추가, `User` 모델에 `kakao_id` 컬럼 추가, 기존 username/password 방식 제거 |

---

## 8. 다음 단계 예고 (구현 7단계)

Docker Compose로 실제 실행 가능하게 만들기 위해:
1. `main.py` lifespan에 `machine_repo.seed(db)` 추가
2. `docker-compose.yml` 검증 (현재 골격만 있음)
3. backend/frontend Dockerfile 확인
4. `docker-compose up --build` → 브라우저 직접 확인