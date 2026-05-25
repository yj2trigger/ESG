# 기숙사 세탁기 예약 서비스 — 전체 설계 문서

> 기술 스택: React + TypeScript / FastAPI / PostgreSQL / Docker
> 배포: Fly.io (백엔드) + Supabase (DB) + Vercel (프론트엔드)

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
[React + TypeScript]  ← 프론트엔드 (Vercel)
        │
        │ HTTPS
        ▼
[FastAPI]             ← 백엔드 API + WebSocket 서버 (Fly.io)
   ├── Auth (JWT + 이메일 인증)
   ├── Machine API
   ├── Queue Manager
   ├── Admin API
   └── IoT Signal API
        │
        ├── PostgreSQL (Supabase) ← 영구 데이터 (유저, 세탁기, 대기열)
        │
        └── IoT 장치 (추후 연결)
              └── POST /iot/machines/{id}/status

[GitHub Actions] → [Fly.io / Vercel] ← 배포
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

### 개발 우선순위

```
1. DB 모델 + 더미 데이터 시드
2. 세탁기 상태 API (REST)
3. Mode A/B/C 판별 로직 (Service Layer)
4. WebSocket 연결 + broadcast
5. React UI (3가지 모드 렌더링)
6. 대기열 API + 타이머 로직
7. JWT 인증
8. Docker + Railway 배포
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
├── api/              ← 서버 통신 함수만 모음
│   ├── machines.ts   ← REST API 호출
│   └── websocket.ts  ← WebSocket 연결 관리
│
├── components/       ← 재사용 가능한 UI 조각
│   ├── common/       ← 버튼, 카드 등 범용
│   └── machine/      ← 세탁기 전용 컴포넌트
│
├── pages/            ← 라우트 1개 = 파일 1개
│   ├── LoginPage.tsx
│   └── DashboardPage.tsx
│
├── hooks/            ← 커스텀 훅
│   ├── useWebSocket.ts
│   └── useMachines.ts
│
├── store/            ← 전역 상태
│   ├── authStore.ts
│   └── machineStore.ts
│
└── types/            ← TypeScript 타입 정의 전용
    ├── machine.ts
    └── user.ts
```

### 라우팅 전략

```
/           → LoginPage    (비로그인 시 리디렉션 대상)
/dashboard  → DashboardPage (메인 화면, 로그인 필요)
/admin      → AdminPage    (role=admin 필요, 나중에 추가)
```

| 항목 | 선택 | 이유 |
|------|------|------|
| 라우팅 라이브러리 | **React Router v6** | 사실상 표준, 문서 풍부 |
| 보호 라우트 | `<ProtectedRoute>` 컴포넌트 | 인증 로직을 라우터에서 분리 |

### 상태 관리 선택

| 방식 | 장점 | 단점 | 결론 |
|------|------|------|------|
| Context + useReducer | 라이브러리 없음 | 보일러플레이트 많음, 리렌더 최적화 어려움 | 탈락 |
| Redux Toolkit | 강력함 | 초보자에게 과도함, 설정 복잡 | 탈락 |
| **Zustand** | 코드 단순, TypeScript 친화적, 보일러플레이트 최소 | 외부 라이브러리 | **채택** |

### TypeScript 핵심 타입 설계

```typescript
// src/types/machine.ts

export type MachineMode = 'A' | 'B' | 'C'

export interface Machine {
  id: number
  floor: number
  status: 'available' | 'in_use' | 'soft_reserved' | 'broken'
  genderRestriction: 'male' | 'female' | null  // null = 공용
}

export interface FloorInfo {
  floor: number
  availableCount: number       // Mode A용
  hasAvailable: boolean        // Mode B/C용
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
├── ModeBanner          ← "현재 모드 A/B/C" 안내 문구
├── FloorList
│   └── FloorCard (층마다 1개)
│       ├── [MODE A] → <MachineCount count={n} />
│       ├── [MODE B] → <ReserveButton />
│       └── [MODE C] → <QueueButton position={n} />
└── MyStatusPanel       ← 내 예약 상태 / 대기 순서 표시
```

> 핵심 설계 원칙: FloorCard는 모드를 모릅니다.
> 부모(DashboardPage)가 모드를 판단해서 올바른 자식 컴포넌트를 선택합니다.

### WebSocket 이벤트 설계

```
서버 → 클라이언트:
  { type: 'MODE_CHANGE',   payload: { mode: 'B' } }
  { type: 'FLOOR_UPDATE',  payload: { floor: 3, count: 2 } }
  { type: 'MY_ASSIGNMENT', payload: { machine: { floor: 2, id: 7 } } }
  { type: 'QUEUE_UPDATE',  payload: { position: 2 } }

클라이언트 → 서버:
  { type: 'REQUEST_MACHINE' }   ← "사용하시겠습니까?" 버튼
  { type: 'JOIN_QUEUE' }        ← Mode C 대기열 등록
```

### 프론트 내 개발 순서

```
1. 타입 정의 (types/)
2. 더미 데이터로 3가지 모드 UI 렌더링
3. Zustand store 연결
4. REST API 연결
5. WebSocket 연결
6. 로그인 페이지 + 라우팅
```

### 흔한 실수

| 실수 | 결과 | 해결 |
|------|------|------|
| 모드 분기를 컴포넌트 안에서 if/else | 컴포넌트 비대화, 테스트 어려움 | 부모에서 분기, 자식은 역할만 |
| WebSocket을 컴포넌트에서 직접 연결 | 중복 연결, 메모리 누수 | 커스텀 훅으로 분리 |
| API 응답을 타입 없이 사용 | any 지옥, 런타임 에러 | types/에 정의 후 import |
| 하드코딩 `gender: 'male'` | 테스트 후 수정 누락 | 항상 store에서 읽기 |

---

## 용어 개념 설명

### WebSocket

HTTP와 비교하면 이해가 빠릅니다.

```
HTTP (일반 요청):
  클라이언트: "세탁기 상태 알려줘"  →  서버: "3층 2대 남았어"
  클라이언트: "세탁기 상태 알려줘"  →  서버: "3층 1대 남았어"
  (매번 요청해야 함, 서버가 먼저 말할 수 없음)

WebSocket:
  클라이언트: "연결할게"  →  서버: "OK, 연결됨"
  서버: "3층 2대 남았어"  (변경 즉시 자동 전송)
  서버: "3층 1대 남았어"  (변경 즉시 자동 전송)
  (서버가 먼저 말할 수 있음, 연결 유지)
```

Python 비유: HTTP는 편지, WebSocket은 전화입니다.
편지는 보낼 때만 연결되고, 전화는 끊기 전까지 양방향 대화가 가능합니다.

이 서비스에서 WebSocket이 필요한 이유:
- 세탁기가 비었을 때 서버가 먼저 알려줘야 함
- 대기열 알림은 클라이언트가 요청하지 않아도 수신해야 함

### 커스텀 훅 (Custom Hook)

React에서 로직을 함수로 분리해 재사용하는 패턴입니다. 이름이 반드시 `use`로 시작합니다.

```typescript
// 훅 없이 (컴포넌트가 WebSocket 직접 관리)
function DashboardPage() {
  const [socket, setSocket] = useState(null)
  useEffect(() => {
    const ws = new WebSocket(...)
    ws.onmessage = ...
    ws.onclose = ... // 재연결 로직
    return () => ws.close()
  }, [])
  // 컴포넌트가 비즈니스 로직 + 연결 관리를 모두 알아야 함
}

// 커스텀 훅으로 분리 후
function useWebSocket() {
  // 연결/해제/재연결 로직이 여기에 캡슐화됨
  return { machines, mode }
}

function DashboardPage() {
  const { machines, mode } = useWebSocket()
  // 컴포넌트는 데이터를 쓰는 것만 담당
}
```

Python 비유: `WebSocketManager` 클래스를 만들어 연결 관리를 맡기는 것처럼,
커스텀 훅은 React 상태 로직을 캡슐화합니다.

### 보일러플레이트 (Boilerplate)

기능과 무관하게 구조상 반드시 써야 하는 틀 코드를 말합니다.

```typescript
// Context + useReducer로 상태 1개 추가 시 필요한 코드
// 1. 타입 정의
// 2. 초기값 정의
// 3. reducer 함수 (switch문)
// 4. Context 생성 (createContext)
// 5. Provider 컴포넌트 작성
// 6. 커스텀 훅 작성 (useContext 래핑)
// → 코드 약 50줄, 상태 1개 추가 완료

// Zustand로 동일 작업
const useMachineStore = create((set) => ({
  machines: [],
  setMachines: (m) => set({ machines: m }),
}))
// → 코드 약 5줄, 상태 1개 추가 완료
```

Python 비유: Java에서 필드 1개에 getter/setter를 모두 써야 하는 것과
Python에서 `self.value`로 직접 접근하는 차이입니다.

### 리렌더 최적화 어려움

React Context의 구조적 문제입니다.

```
Context Provider (machines, mode, myReservation 보관)
├── FloorList      ← machines만 사용
├── ModeBanner     ← mode만 사용
└── MyStatusPanel  ← myReservation만 사용

machines 값이 바뀌면?
→ FloorList, ModeBanner, MyStatusPanel 전부 리렌더
  (ModeBanner, MyStatusPanel은 machines를 안 쓰는데도)
```

Zustand는 구독한 값이 바뀔 때만 리렌더합니다.

```typescript
// ModeBanner는 mode만 구독
const mode = useMachineStore((state) => state.mode)
// machines가 바뀌어도 ModeBanner는 리렌더되지 않음
```

Python 비유: Observer 패턴에서 모든 구독자에게 알림을 보내는 것과
해당 이벤트를 구독한 사람에게만 알림을 보내는 것의 차이입니다.

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
│   ├── queue.py         ← POST /queue/join
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
    └── dependencies.py  ← FastAPI Depends (현재 유저 가져오기)
```

### models vs schemas — 왜 둘 다 있나요?

| | `models/` | `schemas/` |
|---|---|---|
| 역할 | DB 테이블 구조 정의 | API 요청/응답 구조 정의 |
| 사용 기술 | SQLAlchemy | Pydantic |
| 예시 | `Machine` (DB 행) | `MachineResponse` (JSON 응답) |
| 이유 | DB 컬럼과 API 응답이 항상 같지 않음. `password_hash`는 DB엔 있어도 응답엔 없어야 함 |

### API 엔드포인트 설계

| Method | Path | 설명 | 인증 |
|--------|------|------|------|
| POST | `/auth/register` | 회원가입 (@hanyang.ac.kr 이메일 필수) | 불필요 |
| POST | `/auth/verify-email` | 이메일 OTP 인증 → JWT 반환 | 불필요 |
| POST | `/auth/login` | 로그인 → JWT 반환 | 불필요 |
| PATCH | `/auth/password` | 비밀번호 변경 (현재 비번 검증) | 필요 |
| PATCH | `/auth/username` | 아이디 변경 → 새 JWT 반환 | 필요 |
| GET | `/machines` | 현재 모드 + 층별 상태 반환 | 필요 |
| POST | `/machines/request` | Mode B 버튼: 세탁기 1대 배정 요청 | 필요 |
| POST | `/queue/join` | Mode C 버튼: 대기열 등록 | 필요 |
| DELETE | `/queue/leave` | 대기열 취소 | 필요 |
| GET | `/queue/status` | 현재 대기 상태 조회 (페이지 새로고침 복원용) | 필요 |
| GET | `/admin/machines` | 전체 세탁기 목록 (관리자용) | admin |
| PATCH | `/admin/machines/{id}` | 세탁기 상태 변경 + 큐 알림 트리거 | admin |
| POST | `/iot/machines/{id}/status` | IoT 장치 신호 수신 (`is_running` bool) | Device Key |
| WS | `/ws` | 실시간 연결 | JWT 쿼리 파라미터 |

> WebSocket은 HTTP 헤더를 못 쓰는 경우가 많아 JWT를 URL 쿼리 파라미터로 전달합니다.
> 예: `wss://api.example.com/ws?token=eyJ...`

### JWT 설계

```python
# JWT 페이로드 (토큰 안에 담기는 정보)
{
  "sub": "42",          # user_id
  "gender": "male",     # 성별 — Mode 계산에 필수
  "role": "user",       # 권한
  "exp": 1700000000     # 만료 시간
}
```

> **왜 gender를 토큰에 넣나요?**
> 모든 요청마다 DB에서 유저를 조회해 gender를 확인하면 쿼리가 낭비됩니다.
> 토큰에 넣으면 DB 없이 바로 사용할 수 있습니다.
> 단, 민감 정보(비밀번호 등)는 절대 넣지 않습니다.

### 계층 흐름 예시 (Mode B 버튼)

```
1. api/machines.py
       요청 수신, JWT 검증 → user 정보 추출
       │
       ▼
2. services/machine_service.py
       현재 mode 계산 (gender 기준 이용가능 수)
       Mode B 맞는지 확인
       배정 가능한 세탁기 1대 선택
       soft_reserve() 호출
       │
       ▼
3. repositories/machine_repo.py
       DB에서 available 세탁기 조회
       status → 'soft_reserved' 업데이트
       │
       ▼
4. services/machine_service.py
       10분 타이머 등록 (BackgroundTask)
       │
       ▼
5. api/machines.py
       배정된 세탁기 위치 응답 (해당 유저만)
```

### Mode 계산 로직

```python
# services/machine_service.py

def get_current_mode(gender: str, db) -> MachineMode:
    available = machine_repo.count_available(gender, db)
    if available >= 4:
        return 'A'
    elif available >= 1:
        return 'B'
    else:
        return 'C'
```

> 이 함수는 백엔드에만 있습니다.
> 프론트는 모드를 직접 계산하지 않고, 서버가 반환한 `mode: 'B'` 값으로 UI만 결정합니다.

### 10분 타이머 처리 방식

| 방식 | 장점 | 단점 | 선택 |
|------|------|------|------|
| **Lazy expiration** | 구현 단순 | 만료 감지가 다음 요청 때까지 지연됨 | **프로토타입** |
| APScheduler | 정확한 시간에 처리 | 라이브러리 추가, 설정 복잡 | 실서비스 |
| Celery + Redis | 대규모 작업 큐 | 인프라 복잡 | 과도함 |

Lazy expiration 동작:
```
세탁기 배정 시 → expires_at = now + 10분 저장
GET /machines 요청 시 → expires_at 지난 항목 자동 해제 후 반환
```

### WebSocket 연결 관리

```python
# core/websocket_manager.py

class ConnectionManager:
    def __init__(self):
        self.male_connections: list[WebSocket] = []
        self.female_connections: list[WebSocket] = []

    async def broadcast_to_gender(self, gender: str, message: dict):
        # male/female 각각 다른 채널로 전송
        # 성별 정보가 반대 성별에 노출되지 않음
```

### 흔한 실수

| 실수 | 결과 | 해결 |
|------|------|------|
| 비즈니스 로직을 `api/`에 작성 | 라우터 비대화, 재사용 불가 | `services/`로 분리 |
| DB 쿼리를 `services/`에 직접 작성 | 계층 붕괴, DB 교체 시 전체 수정 | `repositories/`로 분리 |
| models와 schemas를 동일하게 사용 | 민감 정보 노출 위험 | 반드시 분리 |
| JWT에 비밀번호 저장 | 심각한 보안 취약점 | 절대 금지 |
| WebSocket을 단일 채널로 broadcast | 타 성별에 세탁기 위치 노출 | gender 기반 채널 분리 |

---

## 5단계: DB 및 데이터 흐름 설계

### 테이블 설계 (ER 다이어그램)

```
┌─────────────┐         ┌──────────────────┐
│    users    │         │     machines     │
│─────────────│         │──────────────────│
│ id (PK)     │         │ id (PK)          │
│ username    │    ┌───▶│ floor            │
│ password_   │    │    │ machine_number   │
│   hash      │    │    │ status           │
│ gender      │    │    │ gender_          │
│ role        │    │    │   restriction    │
│ created_at  │    │    │ reserved_by_ ───▶│ users.id
└──────┬──────┘    │    │   user_id        │
       │           │    │ reserved_until   │
       │           │    └──────────────────┘
       │           │
       │    ┌──────┴──────────┐
       └───▶│  queue_entries  │
            │─────────────────│
            │ id (PK)         │
            │ user_id ───────▶│ users.id
            │ gender          │
            │ status          │
            │ assigned_       │
            │   machine_id ──▶│ machines.id
            │ created_at      │
            │ notified_at     │
            │ expires_at      │
            └─────────────────┘
```

### users

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | INTEGER PK | |
| `username` | VARCHAR | 학번 또는 닉네임 |
| `password_hash` | VARCHAR | 절대 평문 저장 금지 |
| `gender` | ENUM('male','female') | Mode 분기 기준 |
| `role` | ENUM('user','admin') | 기본값 'user' |
| `created_at` | TIMESTAMP | |

### machines

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | INTEGER PK | |
| `floor` | INTEGER | 층 번호 |
| `machine_number` | INTEGER | 층 내 번호 (1번, 2번...) |
| `status` | ENUM | `available` / `in_use` / `soft_reserved` / `broken` |
| `gender_restriction` | ENUM / NULL | `male` / `female` / `NULL` (공용, 1~2층) |
| `reserved_by_user_id` | INTEGER FK / NULL | 소프트 예약한 유저 |
| `reserved_until` | TIMESTAMP / NULL | 예약 만료 시각 |

### queue_entries

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | INTEGER PK | |
| `user_id` | INTEGER FK | |
| `gender` | ENUM | 쿼리 속도를 위해 비정규화 저장 |
| `status` | ENUM | `waiting` / `notified` / `fulfilled` / `expired` / `cancelled` |
| `assigned_machine_id` | INTEGER FK / NULL | 배정된 세탁기 |
| `created_at` | TIMESTAMP | **대기 순서 기준** |
| `notified_at` | TIMESTAMP / NULL | 알림 발송 시각 |
| `expires_at` | TIMESTAMP / NULL | `notified_at + 10분` |

### machine_status_logs

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | INTEGER PK | |
| `machine_id` | INTEGER FK | 어떤 세탁기 |
| `status` | ENUM | 변경된 상태 |
| `changed_by_user_id` | INTEGER FK / NULL | 변경 주체 (자동 만료는 NULL) |
| `changed_at` | TIMESTAMP | 변경 시각 — 통계 핵심 |

> 기존 테이블 수정 없이 append-only로 쌓기만 합니다.
> 통계 UI는 나중에 만들어도 되지만 데이터는 지금부터 쌓여야 합니다.

---

> **왜 gender를 queue_entries에 중복 저장하나요?** (비정규화)
> 대기열 조회 시 `JOIN users` 없이 `WHERE gender = 'male'` 만으로 필터링 가능합니다.
> 데이터 일관성보다 쿼리 단순함을 선택한 실용적 결정입니다.

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

### 데이터 흐름 1: GET /machines (화면 진입)

```
1. reserved_until < NOW() 인 soft_reserved 항목 → available 로 일괄 해제  ← lazy expiration
2. 성별 기준 available 수 COUNT
3. Mode 결정 (A/B/C)
4. 응답 구성:
   Mode A → 층별 available count
   Mode B → 층별 hasAvailable (bool)
   Mode C → 대기열 내 내 순서
```

### 데이터 흐름 2: POST /machines/request (Mode B 버튼)

```
1. 현재 mode 확인 → B 아니면 거절
2. available 세탁기 중 1대 선택
3. machines 업데이트:
   status         → 'soft_reserved'
   reserved_by    → user_id
   reserved_until → NOW() + 10분
4. 해당 유저에게만 응답: { floor: 3, machine_number: 1 }
5. WebSocket broadcast → 전체 클라이언트 상태 갱신
```

### 데이터 흐름 3: POST /queue/join (Mode C 버튼)

```
1. 현재 mode 확인 → C 아니면 거절
2. 이미 대기 중인지 확인 → 중복 방지
3. queue_entries INSERT:
   user_id, gender, status='waiting', created_at=NOW()
4. 응답: { queue_position: 5 }
```

### 데이터 흐름 4: 세탁기 반납 시 (in_use → available)

```
1. machines.status → 'available' 업데이트
2. available 수 재계산
3. 대기열에 waiting 항목 있으면:
   a. created_at 기준 첫 번째 유저 조회
   b. queue_entries 업데이트:
      status              → 'notified'
      assigned_machine_id → 빈 세탁기 id
      notified_at         → NOW()
      expires_at          → NOW() + 10분
   c. 해당 세탁기 → soft_reserved (해당 유저에게 귀속)
   d. WebSocket으로 해당 유저에게만 알림 발송
4. Mode 재계산 → 전체 broadcast
```

### 인덱스 전략

| 테이블 | 인덱스 | 이유 |
|--------|--------|------|
| `machines` | `(gender_restriction, status)` | Mode 판별 쿼리 핵심 |
| `machines` | `reserved_until` | Lazy expiration 처리 |
| `queue_entries` | `(gender, status, created_at)` | 대기열 순서 조회 |
| `queue_entries` | `(user_id, status)` | 중복 대기 방지 |

### 흔한 실수

| 실수 | 결과 | 해결 |
|------|------|------|
| soft_reserved를 available로 카운트 | Mode 오판, 이중 배정 | `reserved_until < NOW()` 조건 필수 |
| 대기열 순서를 id로 정렬 | 트랜잭션 타이밍에 따라 순서 뒤바뀜 | **`created_at` 기준 정렬** |
| gender를 JOIN으로만 가져옴 | 대기열 쿼리마다 users 조인 | queue_entries에 gender 비정규화 |
| 만료 처리를 별도 스케줄러로만 | 스케줄러 오류 시 좀비 예약 | lazy expiration을 기본으로 유지 |

---

## 6단계: Docker 환경 구성

### 전체 컨테이너 구성

```
docker-compose.yml
├── frontend    (React)       → 포트 3000
├── backend     (FastAPI)     → 포트 8000
└── db          (PostgreSQL)  → 포트 5432
```

### 폴더 구조

```
project-root/
├── frontend/
│   ├── Dockerfile
│   └── ... (React 앱)
├── backend/
│   ├── Dockerfile
│   └── ... (FastAPI 앱)
├── docker-compose.yml        ← 로컬 개발용
├── docker-compose.prod.yml   ← 배포용 (DB 제외)
└── .env                      ← 환경변수 (git 제외)
```

### backend/Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 의존성만 먼저 복사 → 코드 변경 시 캐시 재사용
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### frontend/Dockerfile

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
```

> **왜 2단계(multi-stage build)로 빌드하나요?**
> `node_modules` (수백 MB)를 최종 이미지에 포함하지 않습니다.
> 결과 이미지 크기: ~1GB → ~50MB. Railway 배포 속도에 직결됩니다.

### docker-compose.yml (로컬 개발용)

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: laundry
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  backend:
    build: ./backend
    environment:
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@db:5432/laundry
      JWT_SECRET: ${JWT_SECRET}
    ports:
      - "8000:8000"
    depends_on:
      - db
    volumes:
      - ./backend:/app   # 코드 변경 즉시 반영 (개발 편의)

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend

volumes:
  postgres_data:
```

### .env 파일 (절대 git에 올리지 않음)

```
DB_USER=laundry_user
DB_PASSWORD=강한패스워드
JWT_SECRET=랜덤한긴문자열
```

> `.gitignore`에 반드시 `.env` 추가.
> 팀원에게는 `.env.example` (값 없는 템플릿)만 공유합니다.

### 로컬 개발 vs 배포 환경 차이

| 항목 | 로컬 | Railway 배포 |
|------|------|-------------|
| DB | docker-compose 내 postgres | Railway PostgreSQL 플러그인 |
| 환경변수 | `.env` 파일 | Railway 대시보드에서 설정 |
| 프론트 | 개발 서버 (`npm run dev`) | Nginx 빌드 결과물 |
| 코드 반영 | volumes로 즉시 반영 | 이미지 재빌드 필요 |

### 흔한 실수

| 실수 | 결과 | 해결 |
|------|------|------|
| `.env` git 커밋 | 비밀키 노출 | `.gitignore`에 즉시 추가 |
| `COPY . .`를 의존성보다 먼저 | 코드 변경마다 전체 재설치 | 의존성 복사 → 설치 → 코드 복사 순서 유지 |
| `localhost` 하드코딩 | 컨테이너 간 통신 불가 | 서비스 이름으로 참조 (`db`, `backend`) |
| DB 준비 전 백엔드 실행 | 연결 오류 | `depends_on` + 재시도 로직 |

---

## 추가 기능 검토: 시간대별 사용 통계

### 결론: 가능하고, 지금 테이블 1개만 추가하면 됩니다.

### 접근 방식 비교

| 방식 | 설명 | 장점 | 단점 | 결론 |
|------|------|------|------|------|
| **이벤트 로그** | 상태 변경 시마다 기록 | 유연, 기존 테이블 무수정 | 나중에 집계 쿼리 필요 | **채택** |
| 사용 세션 | 시작/종료를 한 행으로 저장 | 통계 직관적 | 종료 시점 추적 복잡 | 보류 |
| 사전 집계 | 시간대별 요약을 미리 저장 | 쿼리 빠름 | 유연성 없음, 과도함 | 탈락 |

### 추가할 테이블: machine_status_logs

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | INTEGER PK | |
| `machine_id` | INTEGER FK | 어떤 세탁기 |
| `status` | ENUM | 변경된 상태 |
| `changed_by_user_id` | INTEGER FK / NULL | 변경 주체 (자동 만료는 NULL) |
| `changed_at` | TIMESTAMP | 변경 시각 — 통계 핵심 |

### 구현 위치

```python
# services/machine_service.py
# 상태 변경이 일어나는 모든 곳에 한 줄 추가

def update_machine_status(machine_id, new_status, user_id, db):
    machine_repo.update_status(machine_id, new_status, db)
    log_repo.insert(machine_id, new_status, user_id, db)  # ← 이게 전부
```

### 나중에 가능한 통계

```sql
-- 시간대별 평균 사용 세탁기 수 (혼잡 시간대 파악)
SELECT
  EXTRACT(HOUR FROM changed_at) AS hour,
  COUNT(*) AS usage_count
FROM machine_status_logs
WHERE status = 'in_use'
GROUP BY hour
ORDER BY hour;
```

- 시간대별 혼잡도 히트맵
- 층별 이용률
- 평균 대기 시간
- 성별 이용 패턴

### 지금 해야 할 것

테이블 정의만 추가합니다. 통계 API와 UI는 나중에 만들면 됩니다.
데이터가 쌓여야 통계가 의미 있으므로, **지금 로깅만 켜두는 것**이 맞습니다.

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
| 7단계 | 배포 (Fly.io + Supabase + Vercel) | ✅ 완료 |
| 8단계 | CI/CD 자동화 (GitHub Actions) | ✅ 완료 |
| 9단계 | 인증 강화 (이메일 인증, 계정 변경) | ✅ 완료 |
| 10단계 | 관리자 페이지 | ✅ 완료 |
| 11단계 | IoT 연동 준비 | ✅ 완료 |
| 12단계 | PWA / 모바일 최적화 | ✅ 완료 |

---

## 7단계: 배포 전략 (Fly.io + Supabase + Vercel)

### 플랫폼 구성

| 역할 | 플랫폼 | 이유 |
|------|--------|------|
| 백엔드 (FastAPI + WS) | **Fly.io** | WebSocket 장기 연결 지원, Docker 배포 |
| 데이터베이스 | **Supabase** | PostgreSQL 완전 관리형, 무료 티어 |
| 프론트엔드 | **Vercel** | React/Vite 자동 빌드, CDN 내장 |

> Railway에서 전환: Fly.io는 WebSocket 장기 연결에 안정적이며, Supabase는 DB 관리 부담 없음.

### 배포 흐름

```
개발자 → git push → GitHub (main 브랜치)
                       │
           ┌───────────┴──────────┐
           ▼                      ▼
   GitHub Actions CI          Vercel (자동 감지)
   (test-backend,                  │
    test-frontend)                 ▼
           │               프론트엔드 빌드/배포
           ▼
   GitHub Actions CD
   (needs: [test-backend, test-frontend])
           │
           ▼
      fly deploy
   (백엔드 Docker 빌드 → Fly.io 배포)
```

### 환경변수

| 변수명 | 위치 | 설명 |
|--------|------|------|
| `DATABASE_URL` | Fly.io Secrets | Supabase PostgreSQL URL |
| `SECRET_KEY` | Fly.io Secrets | JWT 서명 키 |
| `GMAIL_USER` | Fly.io Secrets | 이메일 인증 발신 계정 |
| `GMAIL_APP_PASSWORD` | Fly.io Secrets | Gmail 앱 비밀번호 |
| `IOT_DEVICE_KEY` | Fly.io Secrets | IoT 장치 인증 키 (미설정 시 /iot 비활성화) |
| `CORS_ORIGINS` | Fly.io Secrets | Vercel 프론트 URL |
| `VITE_API_URL` | Vercel Environment | 백엔드 API URL |

### 인증 흐름 (이메일 인증)

```
회원가입: username + password + gender + email(@hanyang.ac.kr)
  → 이메일로 6자리 OTP 발송 (Gmail SMTP)
  → /verify-email 페이지에서 코드 입력
  → 인증 완료 시 JWT 발급
로그인: 미인증 계정 → 403 차단
```

### DB 마이그레이션

현재 `create_all()` 방식 사용 (프로토타입). 실서비스 전환 시 Alembic 도입 예정.

### IoT 연동 준비

```
POST /iot/machines/{machine_id}/status
Header: X-Device-Key: <IOT_DEVICE_KEY>
Body: {"is_running": true | false}

is_running: true  → in_use + machines_updated 브로드캐스트
is_running: false → available + _notify_queue_and_broadcast
                    (대기열 첫 번째 사용자에게 queue_notify)
```

Fly.io 시크릿 설정 후 즉시 연동 가능:
```
fly secrets set IOT_DEVICE_KEY=<랜덤값> --app esg-laundry-checker
```

---

## 구현 완료 기능 현황 (2025-05-25 기준)

### 백엔드

| 기능 | 파일 | 비고 |
|------|------|------|
| 회원가입 + 이메일 OTP 인증 | `api/auth.py`, `services/auth_service.py` | @hanyang.ac.kr 전용 |
| 이메일 발송 | `core/email.py` | Gmail SMTP (smtplib) |
| 로그인 (JWT) | `api/auth.py` | 미인증 계정 403 차단 |
| 비밀번호 변경 | `PATCH /auth/password` | 현재 비번 검증 필수 |
| 아이디 변경 | `PATCH /auth/username` | 현재 비번 검증 + 새 JWT 발급 |
| Mode A/B/C 판별 | `services/machine_service.py` | 성별 기준 available 수 |
| Mode B 소프트 예약 | `POST /machines/request` | 10분 타이머 |
| Mode C 대기열 | `POST /queue/join`, `DELETE /queue/leave` | PostgreSQL 저장 |
| 대기열 상태 조회 | `GET /queue/status` | 새로고침 복원용 |
| 실시간 WebSocket | `api/ws.py` | 성별 채널 분리 |
| 큐 위치 실시간 업데이트 | `ws.py:broadcast_queue_positions` | queue_position_updated 이벤트 |
| 소프트예약 만료 자동 해제 | `machine_repo.release_expired` | WS 루프 30초마다 |
| 관리자 기기 목록/상태변경 | `api/admin.py` | available 전환 시 큐 알림 연동 |
| IoT 신호 수신 엔드포인트 | `api/iot.py` | X-Device-Key 인증 |
| GitHub Actions CI/CD | `.github/workflows/` | test → deploy (Fly.io) |

### 프론트엔드

| 기능 | 파일 | 비고 |
|------|------|------|
| 성별 선택 페이지 | `GenderSelectPage.tsx` | 첫 진입점 |
| 로그인/회원가입 | `LoginPage.tsx` | 비밀번호 보기 토글 |
| 이메일 인증 | `VerifyEmailPage.tsx` | OTP 6자리 입력 |
| 대시보드 (Mode A/B/C) | `DashboardPage.tsx` | WebSocket 실시간 연동 |
| Mode B 결과 영속 | `DashboardPage.tsx` | 모드 전환 후에도 배정 결과 유지 |
| Mode C 대기 영속 | `DashboardPage.tsx` | 모드 전환 후에도 대기 현황 유지 |
| 큐 위치 실시간 표시 | `DashboardPage.tsx` | queue_position_updated 수신 |
| 설정 페이지 | `SettingsPage.tsx` | 비번/아이디 변경, 로그아웃 |
| 관리자 페이지 | `AdminPage.tsx` | 층별 기기 상태 토글 |
| PWA / 모바일 전체화면 | `App.tsx`, `index.html` | 첫 터치 시 fullscreen 요청 |

### 알려진 제약

| 항목 | 현황 |
|------|------|
| `in_use` 자동 해제 | 없음 — 어드민 수동 변경 또는 IoT 연동 필요 |
| Alembic 마이그레이션 | 미적용 (`create_all()` 사용 중) |
| PWA 백그라운드 알림 | 미구현 (앱 열려 있어야 WS 수신 가능) |
| IoT 실제 연동 | 엔드포인트 준비 완료, 장치 연결 대기 중 |