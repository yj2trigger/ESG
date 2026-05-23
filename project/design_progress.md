# 기숙사 세탁기 예약 서비스 — 설계 진행 문서

> 기술 스택: React + TypeScript / FastAPI / PostgreSQL / Docker / Railway

---

## 1단계: 서비스 정의

| 항목 | 내용 |
|------|------|
| **서비스 설명** | 기숙사생들이 세탁기를 이용할 때 이용 가능한 세탁기를 원격으로 확인하고, 합리적으로 판단할 수 있도록 하는 앱 |
| **사용자** | 기숙사생 (로그인 필요 — 남녀 구분 + 1인 다계정 방지) / 관리자 |
| **실시간 기능** | 필요 (알림 + 세탁기 사용 여부 판단) |
| **동시 사용자** | 프로토타입: 고려 안 함 / 배포: 수백 명 수준 |

**세탁기 환경**: 1~2층 공용 9대, 3층 이상 층별 성별 구분 1~2대

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

```
Railway Project: ESG
├── Service: backend    ← FastAPI (backend/Dockerfile)
├── Service: frontend   ← React (frontend/Dockerfile.prod)
└── Service: db         ← Railway PostgreSQL 플러그인 (자동 DATABASE_URL 주입)
```

**환경변수**: backend에 `SECRET_KEY`, `ALGORITHM`, `FRONTEND_URL` / frontend에 `VITE_API_URL`, `VITE_WS_URL`

**WebSocket**: Railway HTTPS 기본 제공 → `ws://` → `wss://` 자동.

**배포 순서**: DB 플러그인 → backend → URL 확인 → frontend 환경변수 설정 → frontend 배포

**마이그레이션**:
```dockerfile
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]
```

> `VITE_` 접두사 없으면 빌드 시 undefined. 프로덕션에서 `ws://` 사용 시 혼합 콘텐츠 차단.

---

## 8단계: CI/CD 자동화

### GitHub Actions 워크플로우 구성

```
.github/workflows/
├── ci.yml     ← PR 시 자동 테스트 + 린트
└── cd.yml     ← main 브랜치 push 시 Railway 자동 배포
```

### ci.yml — PR 자동 검증

```yaml
name: CI

on:
  pull_request:
    branches: [main]

jobs:
  backend-test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_pass
          POSTGRES_DB: test_db
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
          pip install pytest pytest-asyncio httpx

      - name: Run tests
        env:
          DATABASE_URL: postgresql://test_user:test_pass@localhost:5432/test_db
          SECRET_KEY: test-secret-key
          ALGORITHM: HS256
        run: |
          cd backend
          pytest tests/ -v

  frontend-lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        run: cd frontend && npm ci

      - name: Type check
        run: cd frontend && npx tsc --noEmit

      - name: Lint
        run: cd frontend && npm run lint
```

### cd.yml — main 브랜치 자동 배포

```yaml
name: CD

on:
  push:
    branches: [main]

jobs:
  deploy-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Deploy to Railway (backend)
        uses: bervProject/railway-deploy@main
        with:
          railway_token: ${{ secrets.RAILWAY_TOKEN }}
          service: backend

  deploy-frontend:
    runs-on: ubuntu-latest
    needs: deploy-backend   # 백엔드 배포 완료 후 프론트엔드 배포
    steps:
      - uses: actions/checkout@v4

      - name: Deploy to Railway (frontend)
        uses: bervProject/railway-deploy@main
        with:
          railway_token: ${{ secrets.RAILWAY_TOKEN }}
          service: frontend
```

### GitHub Secrets 설정

| Secret | 값 | 설정 위치 |
|--------|---|----------|
| `RAILWAY_TOKEN` | Railway 계정 토큰 | GitHub repo Settings → Secrets |

> Railway 토큰: Railway 대시보드 → Account Settings → Tokens에서 발급

### 브랜치 전략

```
main   ← 프로덕션 (직접 push 금지, PR만 허용)
dev    ← 개발 통합 브랜치
feat/* ← 기능 개발 브랜치

흐름: feat/xxx → PR → CI 통과 → dev 머지 → PR → main → CD 자동 배포
```

### Branch Protection Rules (GitHub 설정)

main 브랜치에 다음을 설정합니다:
- `Require pull request reviews` — 직접 push 방지
- `Require status checks` — CI 통과 필수
- `Require branches to be up to date` — 최신 상태 유지

### 흔한 실수

| 실수 | 결과 | 해결 |
|------|------|------|
| RAILWAY_TOKEN을 코드에 하드코딩 | 토큰 노출 | 반드시 GitHub Secrets 사용 |
| CI 없이 main에 직접 push | 깨진 코드 배포 | Branch Protection Rules 설정 |
| 프론트보다 백엔드 배포 순서 늦춤 | API 불일치 | `needs: deploy-backend` |
| 테스트 DB를 프로덕션 DB로 사용 | 데이터 오염 | CI 전용 postgres service 사용 |

---

## 9단계: 운영 고려사항

### 모니터링

| 항목 | 도구 | 설명 |
|------|------|------|
| 에러 트래킹 | Railway 내장 로그 | 무료 플랜에서 사용 가능 |
| 업타임 모니터링 | UptimeRobot (무료) | 5분 간격 ping, 장애 시 이메일 알림 |
| 응답 시간 | Railway 메트릭스 | 대시보드에서 CPU/메모리 확인 |

### 로깅 전략

```python
# backend/core/logging.py
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

# 핵심 이벤트 로그 (디버깅에 중요)
logger.info(f"Mode changed: {old_mode} → {new_mode} (gender={gender})")
logger.info(f"Soft reserve: machine={machine_id}, user={user_id}, until={reserved_until}")
logger.info(f"Queue notify: user={user_id}, position={position}")
logger.warning(f"Soft reserve expired: machine={machine_id}")
```

### 보안 체크리스트

| 항목 | 조치 |
|------|------|
| JWT 만료 시간 | 60분 (필요 시 Refresh Token 추가) |
| 비밀번호 해싱 | bcrypt 사용 (`passlib[bcrypt]`) |
| CORS 설정 | `FRONTEND_URL`만 허용 (와일드카드 금지) |
| SQL Injection | SQLAlchemy ORM 사용으로 자동 방지 |
| Rate Limiting | `slowapi` 라이브러리 (로그인 시도 제한) |
| 환경변수 | 코드에 하드코딩 금지, `.env.example`만 커밋 |

### CORS 설정 예시

```python
# backend/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:5173")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 장애 대응 시나리오

| 상황 | 감지 | 대응 |
|------|------|------|
| Railway 서비스 다운 | UptimeRobot 알림 | Railway 대시보드 → 재시작 |
| WebSocket 연결 끊김 | 프론트엔드 자동 재연결 | `useWebSocket` 훅에 재연결 로직 구현 |
| DB 연결 실패 | FastAPI 500 에러 | Railway PostgreSQL 상태 확인 |
| soft_reserved 미해제 누적 | 세탁기 수 감소 | lazy expiration 정상 동작 확인 |

### WebSocket 재연결 로직 (프론트엔드)

```typescript
// src/hooks/useWebSocket.ts
const useWebSocket = (url: string) => {
  const reconnect = useCallback(() => {
    const ws = new WebSocket(url)

    ws.onclose = () => {
      // 3초 후 재연결 시도
      setTimeout(() => reconnect(), 3000)
    }

    return ws
  }, [url])

  return reconnect()
}
```

### 확장 고려사항 (실서비스 전환 시)

| 현재 (프로토타입) | 확장 시 |
|------------------|---------|
| Lazy expiration | APScheduler 또는 Celery로 정확한 타이머 |
| WebSocket 인앱 알림 | PWA Push Notification (백그라운드 수신) |
| 더미데이터 토글 | IoT API 연동 (Repository Layer만 교체) |
| 단일 Railway 인스턴스 | 트래픽 증가 시 Railway 스케일링 |

### 프로토타입 완성 체크리스트

```
□ docker-compose up --build → 정상 실행
□ 회원가입 / 로그인 → JWT 정상 발급
□ /machines → 현재 모드 A/B/C 정상 반환
□ Mode B: [사용하시겠습니까?] → 위치 안내 → 10분 후 자동 해제
□ Mode C: 대기열 등록 → 세탁기 반납 시 WebSocket 알림 수신
□ WebSocket 연결 끊김 → 3초 후 자동 재연결
□ Railway 배포 → HTTPS + wss:// 정상 동작
□ GitHub Actions CI → PR 시 테스트 자동 실행
□ GitHub Actions CD → main push 시 자동 배포
```

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
| 8단계 | CI/CD 자동화 | ✅ 완료 (승인 대기) |
| 9단계 | 운영 고려사항 | ✅ 완료 (승인 대기) |
