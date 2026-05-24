# 기숙사 세탁기 예약 서비스 — 설계 진행 문서

> 기술 스택: React + TypeScript / FastAPI / PostgreSQL / Docker / Fly.io + Supabase + Vercel

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
| POST | `/auth/register` | 회원가입 (@hanyang.ac.kr 검증, 코드 발송) | 불필요 |
| POST | `/auth/verify-email` | 6자리 코드 인증 → JWT 반환 | 불필요 |
| POST | `/auth/login` | JWT 반환 (인증된 계정만) | 불필요 |
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
| `users` | id, username, password_hash, gender, role, email, is_verified |
| `machines` | id, floor, machine_number, status, gender_restriction, reserved_by_user_id, reserved_until |
| `queue_entries` | id, user_id, gender(비정규화), status, created_at, notified_at, expires_at |
| `email_verifications` | id, email, code(6자리), expires_at (10분) |
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

## 7단계: 배포 전략 (Fly.io + Supabase + Vercel)

> Railway 무료 플랜 종료로 전환. 모두 무료 플랜 사용.

| 역할 | 플랫폼 | 비고 |
|------|--------|------|
| Backend (FastAPI) | Fly.io | `esg-laundry-checker.fly.dev`, SIN 리전, 256MB |
| Database (PostgreSQL) | Supabase | 무료 500MB |
| Frontend (React) | Vercel | GitHub 연동 자동 배포 |
| 이메일 발송 | Resend | 무료 100통/일 |

**Fly.io 환경변수 (Secrets)**:
- `DATABASE_URL` — Supabase PostgreSQL 연결 문자열
- `SECRET_KEY` — JWT 서명 키
- `CORS_ORIGINS` — Vercel 도메인
- `RESEND_API_KEY` — 이메일 발송 키

**Vercel 환경변수**:
- `VITE_API_URL=https://esg-laundry-checker.fly.dev`
- `VITE_WS_URL=wss://esg-laundry-checker.fly.dev`

> `VITE_` 접두사 없으면 빌드 시 undefined. `auto_stop_machines = false` 필수 (WebSocket 유지).

---

## 8단계: CI/CD 자동화

### GitHub Actions 워크플로우 구성

```
.github/workflows/   ← 레포 루트에 위치 (여기만 GitHub이 인식)
├── ci.yml     ← main/develope push/PR 시 pytest + vitest 자동 실행
└── cd.yml     ← main push 시 테스트 통과 후 Fly.io + Vercel 자동 배포
```

### GitHub Secrets 설정

| Secret | 설명 |
|--------|------|
| `FLY_API_TOKEN` | Fly.io 배포 토큰 |
| `VERCEL_TOKEN` | Vercel 배포 토큰 |
| `VERCEL_ORG_ID` | Vercel User ID |
| `VERCEL_PROJECT_ID` | Vercel Project ID |

### 테스트 환경
- 백엔드: SQLite in-memory DB (Docker/PostgreSQL 없이 pytest 실행)
- 이메일 발송: conftest.py에서 `send_verification_email` monkeypatch로 mock
- 프론트엔드: vitest (jsdom)

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
| 2단계 | 전체 시스템 아키텍처 | ✅ 완료 |
| 3단계 | 프론트엔드 구조 설계 | ✅ 완료 |
| 4단계 | 백엔드 구조 설계 | ✅ 완료 |
| 5단계 | DB 및 데이터 흐름 설계 | ✅ 완료 |
| 6단계 | Docker 환경 구성 | ✅ 완료 |
| 7단계 | Fly.io + Supabase + Vercel 배포 | ✅ 완료 (2026-05-24) |
| 8단계 | CI/CD (GitHub Actions) | ✅ 완료 (2026-05-24) |
| 9단계 | Rate limiting + soft_reserve 중복 방지 | ✅ 완료 (2026-05-24) |
| 10단계 | 한양대 이메일 인증 (hanyang.ac.kr + Resend) | ✅ 완료 (2026-05-25) |
