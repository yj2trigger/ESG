# 기숙사 세탁기 예약 서비스 — 설계 진행 문서

> 기술 스택: React + TypeScript / FastAPI / PostgreSQL / Docker / Railway

---

## 1단계: 서비스 정의

### A. 서비스 본질

| 항목 | 내용 |
|------|------|
| **서비스 설명** | 기숙사생들이 세탁기를 이용할 때 이용 가능한 세탁기를 원격으로 확인하고, 합리적으로 판단할 수 있도록 하는 앱 |
| **한 줄 정의** | 기숙사생들이 세탁기 사용 가능 여부를 원격으로 보고 합리적으로 판단할 수 있도록 하는 앱 |
| **목적** | 과제 프로토타입 + 실제 사용 + 포트폴리오 |

### B. 사용자

| 항목 | 내용 |
|------|------|
| **주요 사용자** | 기숙사생 |
| **역할 구분** | 일반 유저 / 관리자 |
| **로그인 필요 여부** | 필요 (남녀 구분 + 1인 다계정 방지) |

### C. 핵심 기능 / D. 규모 및 제약

| 항목 | 내용 |
|------|------|
| **MVP 필수 기능** | 이용 가능 세탁기 수에 따른 3가지 모드 분기 처리 |
| **실시간 기능** | 필요 (알림 + 세탁기 사용 여부 판단) |
| **동시 사용자** | 프로토타입: 고려 안 함 / 배포: 수백 명 수준 |
| **개발 기간** | 프로토타입 1일~1주일 |

---

## 세탁기 환경 상세

| 층 | 성별 제한 | 세탁기 수 |
|----|-----------|-----------|
| 1~2층 | 공용 (남녀 모두) | 총 9대 |
| 3층 이상 | 층별 성별 구분 | 각 층 1~2대 |

---

## 핵심 비즈니스 로직: 3-Mode State Machine

> 기준: **해당 성별의 전체 이용 가능 세탁기 수**

- **A (4대↑)**: 층별 이용 가능 수 표시, 사용자가 직접 판단
- **B (1~3대)**: [사용하시겠습니까?] → 세탁기 1대 위치 공개 + 10분 소프트 예약
- **C (0대)**: 대기열 등록 → 빈 자리 발생 시 알림 → 10분 미사용 시 다음 대기자에게

```
soft_reserve(machine_id, user_id, duration=10min)
  ├── 특정 유저에게 1:1 귀속, 타이머 만료 시 자동 해제
  └── Mode B = 즉시 배정 / Mode C = 대기 후 배정
```

---

## 2단계: 전체 시스템 아키텍처

```
[React + TypeScript] ←HTTP/WS→ [FastAPI] ←→ [PostgreSQL]
[GitHub Actions] → [Railway]
```

| 항목 | 선택 | 이유 |
|------|------|------|
| 실시간 통신 | WebSocket | 양방향 (대기열 알림) |
| 대기열 저장 | PostgreSQL | Redis 불필요 |
| 인증 | JWT (gender 포함) | 무상태, 매 요청 DB 조회 불필요 |
| 더미 데이터 | DB 시드 + 수동 토글 | IoT 연결 시 Repository Layer만 교체 |

> Mode 계산은 반드시 백엔드. WebSocket은 gender 기반 채널 분리.

---

## 3단계: 프론트엔드 구조 설계

```
src/
├── api/        ← machines.ts, websocket.ts
├── components/ ← common/, machine/
├── pages/      ← LoginPage.tsx, DashboardPage.tsx
├── hooks/      ← useWebSocket.ts, useMachines.ts
├── store/      ← authStore.ts, machineStore.ts (Zustand)
└── types/      ← machine.ts, user.ts
```

```typescript
export type MachineMode = 'A' | 'B' | 'C'
export interface Machine {
  id: number; floor: number
  status: 'available' | 'in_use' | 'soft_reserved' | 'broken'
  genderRestriction: 'male' | 'female' | null
}
```

> FloorCard는 모드를 모름. 부모(DashboardPage)가 모드 판단 후 자식 컴포넌트 선택.

---

## 4단계: 백엔드 구조 설계

```
backend/
├── api/          ← auth.py, machines.py, queue.py, ws.py
├── services/     ← machine_service.py, queue_service.py, auth_service.py
├── repositories/ ← machine_repo.py, queue_repo.py, user_repo.py
├── models/       ← SQLAlchemy ORM
├── schemas/      ← Pydantic 요청/응답
└── core/         ← database.py, security.py, dependencies.py
```

| Method | Path | 설명 | 인증 |
|--------|------|------|------|
| POST | `/auth/register` | 회원가입 | 불필요 |
| POST | `/auth/login` | JWT 반환 | 불필요 |
| GET | `/machines` | 모드 + 층별 상태 | 필요 |
| POST | `/machines/request` | Mode B 배정 | 필요 |
| POST | `/queue/join` | Mode C 대기 등록 | 필요 |
| DELETE | `/queue/leave` | 대기 취소 | 필요 |
| WS | `/ws?token=...` | 실시간 연결 | JWT 쿼리 파라미터 |

```python
def get_current_mode(gender: str, db) -> MachineMode:
    available = machine_repo.count_available(gender, db)
    if available >= 4: return 'A'
    elif available >= 1: return 'B'
    else: return 'C'
```

---

## 5단계: DB 및 데이터 흐름 설계

| 테이블 | 핵심 컬럼 |
|--------|----------|
| `users` | id, username, password_hash, gender, role |
| `machines` | id, floor, machine_number, status, gender_restriction, reserved_by_user_id, reserved_until |
| `queue_entries` | id, user_id, gender(비정규화), status, created_at, notified_at, expires_at |
| `machine_status_logs` | machine_id, status, changed_at (append-only, 통계용) |

```sql
-- Mode 판별 (lazy expiration 포함)
SELECT COUNT(*) FROM machines
WHERE (gender_restriction = 'male' OR gender_restriction IS NULL)
  AND (status = 'available'
       OR (status = 'soft_reserved' AND reserved_until < NOW()))
```

인덱스: `machines(gender_restriction, status)`, `machines(reserved_until)`,
`queue_entries(gender, status, created_at)`, `queue_entries(user_id, status)`

---

## 6단계: Docker 환경 구성

```
project-root/
├── docker-compose.yml       ← 로컬 개발
├── backend/Dockerfile
└── frontend/Dockerfile + Dockerfile.prod (nginx 멀티스테이지)
```

**핵심 포인트**
- `depends_on` + `healthcheck` → DB 준비 후 백엔드 시작
- `/app/node_modules` 익명 볼륨 → 호스트 mount로 덮이지 않도록
- nginx: `try_files $uri /index.html` (SPA 라우팅), WebSocket proxy `Upgrade` 헤더 필수
- 환경변수: `.env.local` (git 제외), `.env.example` (템플릿만 커밋)

```bash
docker-compose up --build   # 전체 실행
docker-compose up db         # DB만 (백엔드 로컬 실행 시)
docker-compose down -v       # DB 초기화 포함
```

---

## 7단계: Railway 배포 전략

### Railway 서비스 구성

Railway 프로젝트 하나에 아래 3개 서비스를 등록합니다.

```
Railway Project: ESG
├── Service: backend    ← FastAPI (Dockerfile로 배포)
├── Service: frontend   ← React (Dockerfile.prod로 배포)
└── Service: db         ← Railway PostgreSQL 플러그인
```

> Railway PostgreSQL은 별도 Dockerfile 없이 플러그인으로 추가합니다.
> Railway가 내부 네트워크에서 `DATABASE_URL`을 자동으로 주입합니다.

### 배포 방식: Dockerfile 기반

Railway는 GitHub 레포를 연결하면 자동으로 빌드합니다.
각 서비스에 어떤 Dockerfile을 쓸지 지정합니다.

| 서비스 | Dockerfile 경로 | 빌드 컨텍스트 |
|--------|----------------|--------------|
| backend | `backend/Dockerfile` | `backend/` |
| frontend | `frontend/Dockerfile.prod` | `frontend/` |

### 환경변수 설정 (Railway 대시보드)

**backend 서비스**

| 변수 | 값 |
|------|---|
| `DATABASE_URL` | Railway PostgreSQL 자동 주입 |
| `SECRET_KEY` | 랜덤 강력한 문자열 (직접 입력) |
| `ALGORITHM` | HS256 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 60 |
| `FRONTEND_URL` | Railway frontend 서비스 URL |

**frontend 서비스**

| 변수 | 값 |
|------|---|
| `VITE_API_URL` | Railway backend 서비스 URL |
| `VITE_WS_URL` | Railway backend 서비스 URL (wss://) |

> VITE_ 접두사는 빌드 시 번들에 포함됩니다.
> 배포 후 URL이 확정되면 환경변수를 업데이트하고 재배포합니다.

### WebSocket + HTTPS

Railway는 기본으로 HTTPS를 제공합니다.
WebSocket도 `wss://`(WebSocket Secure)로 자동 처리됩니다.

```
로컬:       ws://localhost:8000/ws?token=...
Railway:   wss://your-backend.railway.app/ws?token=...
```

프론트엔드에서 환경에 따라 자동으로 분기합니다:
```typescript
const WS_URL = import.meta.env.VITE_WS_URL  // wss://... (프로덕션)
```

### 배포 순서

```
1. Railway 프로젝트 생성
2. PostgreSQL 플러그인 추가
3. backend 서비스 추가 → GitHub 레포 연결 → Dockerfile 경로 지정
4. backend 환경변수 설정 (DATABASE_URL 자동 주입 확인)
5. backend 배포 완료 → URL 확인 (예: https://esg-backend.railway.app)
6. frontend 서비스 추가 → Dockerfile.prod 경로 지정
7. frontend 환경변수 설정 (VITE_API_URL, VITE_WS_URL = backend URL)
8. frontend 배포 완료 → URL 확인
9. backend의 FRONTEND_URL 업데이트 → 재배포
```

### 자동 재배포 설정

Railway는 GitHub push 시 자동 재배포를 지원합니다.

| 브랜치 | 배포 환경 |
|--------|----------|
| `main` | 프로덕션 자동 배포 |
| `dev` (선택) | 스테이징 환경 (필요 시) |

### DB 마이그레이션 전략

```
Alembic 사용:
1. backend/alembic/ 디렉토리 초기화
2. 배포 시 entrypoint에서 자동 마이그레이션 실행

# backend/Dockerfile CMD 수정
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]
```

> 프로토타입 단계에서는 `alembic upgrade head` 대신 SQLAlchemy `create_all()`로 간단히 처리해도 됩니다.

### 흔한 실수

| 실수 | 결과 | 해결 |
|------|------|------|
| VITE_ 없이 환경변수 사용 | 빌드 시 undefined | 반드시 `VITE_` 접두사 |
| ws:// 를 프로덕션에서 사용 | 혼합 콘텐츠 차단 | `wss://` 사용 |
| DATABASE_URL 직접 입력 | Railway 플러그인과 충돌 | 자동 주입 값 사용 |
| SECRET_KEY 기본값 그대로 배포 | 보안 취약점 | 강력한 랜덤 문자열로 교체 |
| 마이그레이션 없이 배포 | 테이블 없음 오류 | `alembic upgrade head` 또는 `create_all()` |

---

## 진행 현황

| 단계 | 내용 | 상태 |
|------|------|------|
| 1단계 | 서비스 정의 | ✅ 완료 |
| 2단계 | 전체 시스템 아키텍처 | ✅ 완료 (승인 대기) |
| 3단계 | 프론트엔드 구조 설계 | ✅ 완료 (승인 대기) |
| 4단계 | 백엔드 구조 설계 | ✅ 완료 (승인 대기) |
| 5단계 | DB 및 데이터 흐름 설계 | ✅ 완료 (승인 대기) |
| 6단계 | Docker 환경 구성 | ✅ 완료 (승인 대기) |
| 7단계 | Railway 배포 전략 | ✅ 완료 (승인 대기) |
| 8단계 | CI/CD 자동화 | ⏳ 대기 |
| 9단계 | 운영 고려사항 | ⏳ 대기 |
