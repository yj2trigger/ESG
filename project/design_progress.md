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

### C. 핵심 기능

| 항목 | 내용 |
|------|------|
| **MVP 필수 기능** | 이용 가능 세탁기 수에 따른 3가지 모드 분기 처리 |
| **나중에 추가** | 관리자 페이지, 정식 로그인 서비스 등 |
| **파일 업로드** | 불필요 |
| **실시간 기능** | 필요 (알림 + 세탁기 사용 여부 판단) |

### D. 규모 및 제약

| 항목 | 내용 |
|------|------|
| **동시 사용자** | 프로토타입: 고려 안 함 / 배포: 수백 명 수준 |
| **개발 기간** | 프로토타입 1일~1주일 |
| **팀 구성** | 팀 프로젝트이나 사실상 개인 진행 |

---

## 세탁기 환경 상세

| 층 | 성별 제한 | 세탁기 수 |
|----|-----------|-----------|
| 1~2층 | 공용 (남녀 모두) | 총 9대 |
| 3층 이상 | 층별 성별 구분 | 각 층 1~2대 |

---

## 핵심 비즈니스 로직: 3-Mode State Machine

> 기준: **해당 성별의 전체 이용 가능 세탁기 수**

```
전체 이용가능 수 (성별 기준)
┌─────────────────────────────────────────────────────────────┐
│  4대 이상         │  1~3대            │  0대               │
│  [MODE A]         │  [MODE B]         │  [MODE C]          │
│  층별 대수 표시    │  1:1 즉시 배정     │  대기열 기반 배정   │
└─────────────────────────────────────────────────────────────┘
```

### MODE A (4대 이상)
- 층별 이용 가능 세탁기 **수** 표시
- 사용자가 직접 판단하여 이동

### MODE B (1~3대) — 소프트 예약
- 화면: "현재 세탁기가 1~3대이기에 수요 분산을 위해 위치를 직접 안내합니다."
- [사용하시겠습니까?] 버튼 표시
- 버튼 누름 → **해당 사용자에게만** 세탁기 1대의 위치(층+번호) 공개
- 해당 세탁기는 **10분간 소프트 예약** 상태 (다른 사용자에게 이용중으로 표시)
- 10분 내 실제 사용 → 정상 완료
- 10분 내 미사용 → 소프트 예약 해제, 다시 이용 가능 상태로 복귀

### MODE C (0대) — 대기열 배정
- 버튼을 누르면 **대기열** 등록
- 세탁기가 비면 → 대기열 순서대로 세탁기 1대의 위치 **알림** 발송
- 알림 받은 사용자가 **10분 내 미사용** 시 → 소프트 예약 해제, 다음 대기자에게 알림
- 다시 4대 이상이 되면 MODE A로 복귀

### 공통 핵심 메커니즘 (Mode B & C 공유)
```
soft_reserve(machine_id, user_id, duration=10min)
  ├── 해당 세탁기를 특정 사용자에게 1:1 귀속
  ├── 타이머 만료 시 자동 해제
  └── 해제 후 → Mode 재계산 → 필요 시 다음 사용자에게 배정

차이점:
  Mode B = 이용 가능한 세탁기가 있으므로 즉시 배정
  Mode C = 이용 가능한 세탁기가 없으므로 대기 후 배정
```

---

## 2단계: 전체 시스템 아키텍처

### 시스템 구성도

```
[사용자 브라우저 / PWA]
        │
        │ HTTP (REST) + WebSocket
        ▼
[React + TypeScript]  ← 프론트엔드
        │
        │ HTTPS
        ▼
[FastAPI]             ← 백엔드 API + WebSocket 서버
   ├── Auth (JWT)
   ├── Machine API
   ├── Queue Manager
   └── Notification Service
        │
        ├── PostgreSQL  ← 영구 데이터 (유저, 세탁기, 대기열)
        │
        └── (더미데이터 레이어) ← IoT 연결 전까지

[GitHub Actions] → [Railway] ← 배포
```

### 핵심 기술 선택 결정표

| 항목 | 선택 | 대안 | 이유 |
|------|------|------|------|
| 실시간 통신 | **WebSocket** | SSE, Polling | 양방향 필요 (대기열 알림) |
| 알림 방식 | **WebSocket 인앱 알림** | PWA Push Notification | 프로토타입 복잡도 최소화 |
| 대기열 저장 | **PostgreSQL** | Redis Queue | 별도 인프라 불필요 |
| 인증 | **JWT** | Session | 무상태, 모바일 친화적 |
| 더미 데이터 | **DB 시드 + 수동 토글** | 하드코딩 | IoT 연결 시 교체 용이 |

### 알림 방식 비교

| 방식 | 장점 | 단점 | 적용 시점 |
|------|------|------|-----------|
| WebSocket 인앱 알림 | 구현 단순, 별도 서버 불필요 | 앱 열고 있어야 함 | **프로토타입** |
| PWA Push Notification | 백그라운드에서도 수신 가능 | HTTPS 필수, Service Worker 복잡 | 실서비스 확장 시 |

### 레이어 분리 전략

```
Frontend                  Backend
─────────────────         ────────────────────────────
View Layer                Router Layer (API 진입점)
  └─ 3가지 모드 UI           └─ /machines, /auth, /queue

State Layer               Service Layer (비즈니스 로직)
  └─ 실시간 상태 관리          └─ Mode 판별, Queue 로직

API Layer                 Repository Layer (DB 접근)
  └─ WebSocket 연결           └─ SQLAlchemy ORM
```

> IoT 연결 방식이 바뀌어도 Repository Layer만 수정하면 됨.
> Service Layer는 데이터 출처를 모름.

### 데이터 구조 (개략)

| 엔티티 | 핵심 필드 | 비고 |
|--------|-----------|------|
| `User` | id, gender, role | 성별로 모드 분기 |
| `Machine` | id, floor, status, gender_restriction | 1~2층: null (공용) |
| `QueueEntry` | user_id, floor, notified_at, expires_at | 10분 타이머 |

### 실시간 흐름도

```
[세탁기 상태 변경]
      │
      ▼
[Backend: 상태 업데이트]
      │
      ├── Mode 재계산 (A/B/C)
      ├── 대기열 있으면 → 첫 번째 사용자에게 WebSocket 알림
      │                    └── 10분 타이머 시작
      └── 전체 연결된 클라이언트에 broadcast
```

### 흔한 실수

| 실수 | 결과 | 해결 |
|------|------|------|
| Mode를 프론트에서만 계산 | 조작 가능, 성별 우회 | **백엔드에서 계산** |
| WebSocket 하나로 전체 broadcast | 성별 정보 노출 | 연결 시 gender 기반 **채널 분리** |
| 대기열을 메모리에 저장 | 서버 재시작 시 초기화 | **PostgreSQL에 저장** |

---

## 3단계: 프론트엔드 구조 설계

### 폴더 구조

```
src/
├── api/
│   ├── machines.ts
│   └── websocket.ts
├── components/
│   ├── common/
│   └── machine/
├── pages/
│   ├── LoginPage.tsx
│   └── DashboardPage.tsx
├── hooks/
│   ├── useWebSocket.ts
│   └── useMachines.ts
├── store/
│   ├── authStore.ts
│   └── machineStore.ts
└── types/
    ├── machine.ts
    └── user.ts
```

### 상태 관리: Zustand 채택

### TypeScript 핵심 타입

```typescript
export type MachineMode = 'A' | 'B' | 'C'

export interface Machine {
  id: number
  floor: number
  status: 'available' | 'in_use' | 'soft_reserved' | 'broken'
  genderRestriction: 'male' | 'female' | null
}

export interface DashboardState {
  mode: MachineMode
  floors: FloorInfo[]
  myReservation: Machine | null
  queuePosition: number | null
}
```

### 컴포넌트 트리

```
DashboardPage
├── ModeBanner
├── FloorList
│   └── FloorCard
│       ├── [MODE A] → <MachineCount />
│       ├── [MODE B] → <ReserveButton />
│       └── [MODE C] → <QueueButton />
└── MyStatusPanel
```

### WebSocket 이벤트

```
서버 → 클라이언트:
  { type: 'MODE_CHANGE',   payload: { mode: 'B' } }
  { type: 'FLOOR_UPDATE',  payload: { floor: 3, count: 2 } }
  { type: 'MY_ASSIGNMENT', payload: { machine: { floor: 2, id: 7 } } }
  { type: 'QUEUE_UPDATE',  payload: { position: 2 } }

클라이언트 → 서버:
  { type: 'REQUEST_MACHINE' }
  { type: 'JOIN_QUEUE' }
```

### 흔한 실수

| 실수 | 해결 |
|------|------|
| 모드 분기를 컴포넌트 안에서 처리 | 부모에서 분기, 자식은 역할만 |
| WebSocket을 컴포넌트에서 직접 연결 | 커스텀 훅으로 분리 |
| API 응답을 타입 없이 사용 | types/에 정의 후 import |

---

## 4단계: 백엔드 구조 설계

### 폴더 구조

```
backend/
├── main.py              ← FastAPI 앱 생성, 라우터 등록
├── config.py            ← 환경변수 로딩 (DB URL, JWT 키 등)
│
├── api/                 ← Router Layer: 요청 받는 창구
│   ├── auth.py          ← POST /auth/login, /auth/register
│   ├── machines.py      ← GET /machines, POST /machines/request
│   ├── queue.py         ← POST /queue/join, DELETE /queue/leave
│   └── ws.py            ← WebSocket /ws
│
├── services/            ← Service Layer: 비즈니스 로직
│   ├── machine_service.py   ← Mode 계산, soft_reserve 로직
│   ├── queue_service.py     ← 대기열 관리, 타이머 처리
│   └── auth_service.py      ← 토큰 생성/검증
│
├── repositories/        ← Repository Layer: DB 접근만 담당
│   ├── machine_repo.py
│   ├── queue_repo.py
│   └── user_repo.py
│
├── models/              ← SQLAlchemy: DB 테이블 정의
│   ├── user.py
│   ├── machine.py
│   └── queue_entry.py
│
├── schemas/             ← Pydantic: API 요청/응답 타입
│   ├── machine.py
│   └── user.py
│
└── core/                ← 공통 인프라
    ├── database.py      ← DB 연결 설정
    ├── security.py      ← JWT 유틸
    └── dependencies.py  ← FastAPI Depends
```

### models vs schemas — 왜 둘 다 있나요?

| | `models/` | `schemas/` |
|---|---|---|
| 역할 | DB 테이블 구조 정의 | API 요청/응답 구조 정의 |
| 사용 기술 | SQLAlchemy | Pydantic |
| 이유 | `password_hash`는 DB엔 있어도 응답엔 없어야 함 |

### API 엔드포인트 설계

| Method | Path | 설명 | 인증 |
|--------|------|------|------|
| POST | `/auth/register` | 회원가입 (gender 포함) | 불필요 |
| POST | `/auth/login` | 로그인 → JWT 반환 | 불필요 |
| GET | `/machines` | 현재 모드 + 층별 상태 반환 | 필요 |
| POST | `/machines/request` | Mode B: 세탁기 1대 배정 요청 | 필요 |
| POST | `/queue/join` | Mode C: 대기열 등록 | 필요 |
| DELETE | `/queue/leave` | 대기열 취소 | 필요 |
| WS | `/ws` | 실시간 연결 | JWT 쿼리 파라미터 |

> WebSocket은 HTTP 헤더를 못 쓰는 경우가 많아 JWT를 URL 쿼리 파라미터로 전달합니다.
> 예: `wss://api.example.com/ws?token=eyJ...`

### JWT 설계

```python
{
  "sub": "42",       # user_id
  "gender": "male",  # 성별 — Mode 계산에 필수
  "role": "user",    # 권한
  "exp": 1700000000  # 만료 시간
}
```

> gender를 토큰에 넣는 이유: 모든 요청마다 DB 조회 없이 바로 사용 가능.
> 단, 민감 정보(비밀번호 등)는 절대 넣지 않습니다.

### 계층 흐름 예시 (Mode B 버튼)

```
1. api/machines.py     → 요청 수신, JWT 검증
2. services/           → mode 확인, 세탁기 선택, soft_reserve 호출
3. repositories/       → DB 조회 및 status 업데이트
4. services/           → 10분 타이머 등록 (BackgroundTask)
5. api/machines.py     → 해당 유저에게만 위치 응답
```

### Mode 계산 로직

```python
def get_current_mode(gender: str, db) -> MachineMode:
    available = machine_repo.count_available(gender, db)
    if available >= 4:
        return 'A'
    elif available >= 1:
        return 'B'
    else:
        return 'C'
```

> 이 함수는 백엔드에만 있습니다. 프론트는 서버가 반환한 `mode` 값으로 UI만 결정합니다.

### 10분 타이머 처리

| 방식 | 선택 | 이유 |
|------|------|------|
| **Lazy expiration** | **프로토타입** | 구현 단순 — GET 요청 시 만료 항목 자동 해제 |
| APScheduler | 실서비스 | 정확한 시간 처리, 라이브러리 추가 필요 |

### WebSocket 연결 관리

```python
class ConnectionManager:
    def __init__(self):
        self.male_connections: list[WebSocket] = []
        self.female_connections: list[WebSocket] = []

    async def broadcast_to_gender(self, gender: str, message: dict):
        # gender 기반 채널 분리 → 타 성별에 정보 노출 방지
```

### 흔한 실수

| 실수 | 결과 | 해결 |
|------|------|------|
| 비즈니스 로직을 `api/`에 작성 | 라우터 비대화 | `services/`로 분리 |
| DB 쿼리를 `services/`에 직접 작성 | 계층 붕괴 | `repositories/`로 분리 |
| models와 schemas를 동일하게 사용 | 민감 정보 노출 | 반드시 분리 |
| JWT에 비밀번호 저장 | 심각한 보안 취약점 | 절대 금지 |
| WebSocket 단일 채널 broadcast | 타 성별 정보 노출 | gender 기반 채널 분리 |

---

## 진행 현황

| 단계 | 내용 | 상태 |
|------|------|------|
| 1단계 | 서비스 정의 | ✅ 완료 |
| 2단계 | 전체 시스템 아키텍처 | ✅ 완료 (승인 대기) |
| 3단계 | 프론트엔드 구조 설계 | ✅ 완료 (승인 대기) |
| 4단계 | 백엔드 구조 설계 | ✅ 완료 (승인 대기) |
| 5단계 | DB 및 데이터 흐름 설계 | ⏳ 대기 |
| 6단계 | Docker 환경 구성 | ⏳ 대기 |
| 7단계 | Railway 배포 전략 | ⏳ 대기 |
| 8단계 | CI/CD 자동화 | ⏳ 대기 |
| 9단계 | 운영 고려사항 | ⏳ 대기 |
