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

### 레이어 분리 전략

```
Frontend                  Backend
─────────────────         ────────────────────────────
View Layer                Router Layer (API 진입점)
State Layer               Service Layer (비즈니스 로직)
API Layer                 Repository Layer (DB 접근)
```

### 흔한 실수

| 실수 | 해결 |
|------|------|
| Mode를 프론트에서만 계산 | **백엔드에서 계산** |
| WebSocket 하나로 전체 broadcast | gender 기반 **채널 분리** |
| 대기열을 메모리에 저장 | **PostgreSQL에 저장** |

---

## 3단계: 프론트엔드 구조 설계

### 폴더 구조

```
src/
├── api/          ← machines.ts, websocket.ts
├── components/   ← common/, machine/
├── pages/        ← LoginPage.tsx, DashboardPage.tsx
├── hooks/        ← useWebSocket.ts, useMachines.ts
├── store/        ← authStore.ts, machineStore.ts (Zustand)
└── types/        ← machine.ts, user.ts
```

### TypeScript 핵심 타입

```typescript
export type MachineMode = 'A' | 'B' | 'C'

export interface Machine {
  id: number; floor: number
  status: 'available' | 'in_use' | 'soft_reserved' | 'broken'
  genderRestriction: 'male' | 'female' | null
}

export interface DashboardState {
  mode: MachineMode; floors: FloorInfo[]
  myReservation: Machine | null; queuePosition: number | null
}
```

### 컴포넌트 트리

```
DashboardPage
├── ModeBanner
├── FloorList → FloorCard
│   ├── [A] <MachineCount />  ├── [B] <ReserveButton />  └── [C] <QueueButton />
└── MyStatusPanel
```

> FloorCard는 모드를 모릅니다. 부모가 모드 판단 후 올바른 자식 컴포넌트 선택.

### WebSocket 이벤트

```
서버→클라이언트: MODE_CHANGE / FLOOR_UPDATE / MY_ASSIGNMENT / QUEUE_UPDATE
클라이언트→서버: REQUEST_MACHINE / JOIN_QUEUE
```

---

## 4단계: 백엔드 구조 설계

### 폴더 구조

```
backend/
├── main.py / config.py
├── api/        ← auth.py, machines.py, queue.py, ws.py
├── services/   ← machine_service.py, queue_service.py, auth_service.py
├── repositories/ ← machine_repo.py, queue_repo.py, user_repo.py
├── models/     ← SQLAlchemy: user.py, machine.py, queue_entry.py
├── schemas/    ← Pydantic: machine.py, user.py
└── core/       ← database.py, security.py, dependencies.py
```

### API 엔드포인트

| Method | Path | 설명 | 인증 |
|--------|------|------|------|
| POST | `/auth/register` | 회원가입 (gender 포함) | 불필요 |
| POST | `/auth/login` | 로그인 → JWT 반환 | 불필요 |
| GET | `/machines` | 현재 모드 + 층별 상태 | 필요 |
| POST | `/machines/request` | Mode B: 세탁기 배정 | 필요 |
| POST | `/queue/join` | Mode C: 대기열 등록 | 필요 |
| DELETE | `/queue/leave` | 대기열 취소 | 필요 |
| WS | `/ws?token=...` | 실시간 연결 | JWT 쿼리 파라미터 |

### Mode 계산 로직

```python
def get_current_mode(gender: str, db) -> MachineMode:
    available = machine_repo.count_available(gender, db)
    if available >= 4: return 'A'
    elif available >= 1: return 'B'
    else: return 'C'
```

### 타이머: Lazy expiration (프로토타입)

GET 요청 시 `reserved_until < NOW()` 항목 자동 해제 후 반환.

### WebSocket

```python
class ConnectionManager:
    male_connections: list[WebSocket] = []
    female_connections: list[WebSocket] = []
    # gender 기반 채널 분리
```

---

## 5단계: DB 및 데이터 흐름 설계

### 테이블 설계

**users**

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | INTEGER PK | |
| `username` | VARCHAR | 학번 또는 닉네임 |
| `password_hash` | VARCHAR | 절대 평문 저장 금지 |
| `gender` | ENUM('male','female') | Mode 분기 기준 |
| `role` | ENUM('user','admin') | 기본값 'user' |
| `created_at` | TIMESTAMP | |

**machines**

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | INTEGER PK | |
| `floor` | INTEGER | 층 번호 |
| `machine_number` | INTEGER | 층 내 번호 |
| `status` | ENUM | `available` / `in_use` / `soft_reserved` / `broken` |
| `gender_restriction` | ENUM / NULL | `male` / `female` / NULL (1~2층 공용) |
| `reserved_by_user_id` | INTEGER FK / NULL | 소프트 예약한 유저 |
| `reserved_until` | TIMESTAMP / NULL | 예약 만료 시각 |

**queue_entries**

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | INTEGER PK | |
| `user_id` | INTEGER FK | |
| `gender` | ENUM | 비정규화 저장 (JOIN 없이 필터링) |
| `status` | ENUM | `waiting` / `notified` / `fulfilled` / `expired` / `cancelled` |
| `assigned_machine_id` | INTEGER FK / NULL | 배정된 세탁기 |
| `created_at` | TIMESTAMP | **대기 순서 기준** |
| `notified_at` | TIMESTAMP / NULL | 알림 발송 시각 |
| `expires_at` | TIMESTAMP / NULL | `notified_at + 10분` |

**machine_status_logs** (통계용 — append-only)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | INTEGER PK | |
| `machine_id` | INTEGER FK | |
| `status` | ENUM | 변경된 상태 |
| `changed_by_user_id` | INTEGER FK / NULL | 자동 만료 시 NULL |
| `changed_at` | TIMESTAMP | 변경 시각 — 통계 핵심 |

> 통계 UI는 나중에 만들어도 되지만, 데이터는 지금부터 쌓아야 합니다.

### 핵심 쿼리: Mode 판별

```sql
-- 남성 기준 이용 가능 세탁기 수 (lazy expiration 포함)
SELECT COUNT(*) FROM machines
WHERE
  (gender_restriction = 'male' OR gender_restriction IS NULL)
  AND (
    status = 'available'
    OR (status = 'soft_reserved' AND reserved_until < NOW())
  )
```

### 데이터 흐름: GET /machines (화면 진입)

```
1. reserved_until < NOW() 인 soft_reserved → available 일괄 해제 (lazy expiration)
2. 성별 기준 available 수 COUNT
3. Mode 결정 (A/B/C)
4. Mode A → 층별 count / Mode B → 층별 hasAvailable / Mode C → 내 대기 순서
```

### 데이터 흐름: POST /machines/request (Mode B)

```
1. 현재 mode 확인 → B 아니면 거절
2. available 세탁기 1대 선택
3. status → 'soft_reserved', reserved_by → user_id, reserved_until → NOW()+10분
4. 해당 유저에게만 응답: { floor: 3, machine_number: 1 }
5. WebSocket broadcast → 전체 클라이언트 상태 갱신
```

### 데이터 흐름: 세탁기 반납 시

```
1. machines.status → 'available'
2. 대기열 waiting 항목 있으면:
   a. created_at 기준 첫 번째 유저 조회
   b. queue_entries: status → 'notified', expires_at → NOW()+10분
   c. 해당 세탁기 → soft_reserved
   d. WebSocket으로 해당 유저에게만 알림
3. Mode 재계산 → 전체 broadcast
```

### 인덱스 전략

| 테이블 | 인덱스 | 이유 |
|--------|--------|------|
| `machines` | `(gender_restriction, status)` | Mode 판별 쿼리 핵심 |
| `machines` | `reserved_until` | Lazy expiration 처리 |
| `queue_entries` | `(gender, status, created_at)` | 대기열 순서 조회 |
| `queue_entries` | `(user_id, status)` | 중복 대기 방지 |

### 흔한 실수

| 실수 | 해결 |
|------|------|
| soft_reserved를 available로 카운트 | `reserved_until < NOW()` 조건 필수 |
| 대기열 순서를 id로 정렬 | **`created_at` 기준 정렬** |
| gender를 JOIN으로만 가져옴 | queue_entries에 gender 비정규화 |
| 만료 처리를 스케줄러로만 | lazy expiration을 기본으로 유지 |

---

## 진행 현황

| 단계 | 내용 | 상태 |
|------|------|------|
| 1단계 | 서비스 정의 | ✅ 완료 |
| 2단계 | 전체 시스템 아키텍처 | ✅ 완료 (승인 대기) |
| 3단계 | 프론트엔드 구조 설계 | ✅ 완료 (승인 대기) |
| 4단계 | 백엔드 구조 설계 | ✅ 완료 (승인 대기) |
| 5단계 | DB 및 데이터 흐름 설계 | ✅ 완료 (승인 대기) |
| 6단계 | Docker 환경 구성 | ⏳ 대기 |
| 7단계 | Railway 배포 전략 | ⏳ 대기 |
| 8단계 | CI/CD 자동화 | ⏳ 대기 |
| 9단계 | 운영 고려사항 | ⏳ 대기 |
