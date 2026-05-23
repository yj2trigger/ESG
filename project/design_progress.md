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

### MODE A / B / C 요약
- **A**: 층별 이용 가능 수 표시, 사용자가 직접 판단
- **B**: [사용하시겠습니까?] → 세탁기 1대 위치 공개 + 10분 소프트 예약
- **C**: 대기열 등록 → 빈 자리 발생 시 알림 → 10분 미사용 시 다음 대기자에게 이동

---

## 2단계: 전체 시스템 아키텍처

```
[React + TypeScript] ←HTTP/WS→ [FastAPI] ←→ [PostgreSQL]
[GitHub Actions] → [Railway]
```

### 핵심 결정

| 항목 | 선택 | 이유 |
|------|------|------|
| 실시간 통신 | WebSocket | 양방향 (대기열 알림) |
| 대기열 저장 | PostgreSQL | Redis 불필요 |
| 인증 | JWT | 무상태, gender 포함 |
| 더미 데이터 | DB 시드 + 수동 토글 | IoT 연결 시 Repository Layer만 교체 |

### 레이어

```
Frontend: View → State → API
Backend:  Router → Service → Repository → DB
```

> Mode 계산은 반드시 백엔드. WebSocket은 gender 기반 채널 분리.

---

## 3단계: 프론트엔드 구조 설계

```
src/
├── api/      ← machines.ts, websocket.ts
├── components/ ← common/, machine/
├── pages/    ← LoginPage.tsx, DashboardPage.tsx
├── hooks/    ← useWebSocket.ts, useMachines.ts
├── store/    ← authStore.ts, machineStore.ts (Zustand)
└── types/    ← machine.ts, user.ts
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

**API 엔드포인트**

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

**테이블**

| 테이블 | 핵심 컬럼 |
|--------|----------|
| `users` | id, username, password_hash, gender, role |
| `machines` | id, floor, machine_number, status, gender_restriction, reserved_by_user_id, reserved_until |
| `queue_entries` | id, user_id, gender(비정규화), status, created_at, notified_at, expires_at |
| `machine_status_logs` | machine_id, status, changed_at (append-only, 통계용) |

**핵심 쿼리 (Mode 판별)**

```sql
SELECT COUNT(*) FROM machines
WHERE (gender_restriction = 'male' OR gender_restriction IS NULL)
  AND (status = 'available'
       OR (status = 'soft_reserved' AND reserved_until < NOW()))
```

**흐름 요약**
- GET /machines: lazy expiration 처리 → COUNT → Mode 결정 → 응답
- POST /machines/request: mode=B 확인 → soft_reserve → 해당 유저에게만 위치 응답 → broadcast
- 반납: available → 대기열 첫 번째 유저 조회 → soft_reserve → WebSocket 알림

**인덱스**
- `machines`: `(gender_restriction, status)`, `reserved_until`
- `queue_entries`: `(gender, status, created_at)`, `(user_id, status)`

---

## 6단계: Docker 환경 구성

### 전체 파일 구조

```
project-root/
├── docker-compose.yml       ← 로컬 개발 전체 실행
├── docker-compose.prod.yml  ← 프로덕션 (Railway 제외 서비스용)
│
├── backend/
│   ├── Dockerfile
│   ├── .dockerignore
│   └── requirements.txt
│
└── frontend/
    ├── Dockerfile
    ├── Dockerfile.prod      ← nginx 기반 정적 빌드용
    └── .dockerignore
```

### docker-compose.yml (로컬 개발)

```yaml
version: "3.9"

services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: esg_user
      POSTGRES_PASSWORD: esg_pass
      POSTGRES_DB: esg_db
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U esg_user -d esg_db"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend:
    build: ./backend
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://esg_user:esg_pass@db:5432/esg_db
      SECRET_KEY: dev-secret-key-change-in-prod
      ALGORITHM: HS256
      ACCESS_TOKEN_EXPIRE_MINUTES: 60
    volumes:
      - ./backend:/app       # 핫 리로드용
    depends_on:
      db:
        condition: service_healthy

  frontend:
    build: ./frontend
    command: npm run dev -- --host
    ports:
      - "5173:5173"
    environment:
      VITE_API_URL: http://localhost:8000
      VITE_WS_URL: ws://localhost:8000
    volumes:
      - ./frontend:/app
      - /app/node_modules    # 컨테이너 내부 node_modules 보존
    depends_on:
      - backend

volumes:
  postgres_data:
```

### backend/Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 시스템 의존성
RUN apt-get update && apt-get install -y \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 의존성 먼저 설치 (레이어 캐싱 활용)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### frontend/Dockerfile (개발용)

```dockerfile
FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]
```

### frontend/Dockerfile.prod (프로덕션 — nginx)

```dockerfile
# 1단계: 빌드
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# 2단계: nginx로 정적 파일 서빙
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

### nginx.conf (SPA 라우팅 대응)

```nginx
server {
    listen 80;

    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;  # React Router 새로고침 대응
    }

    location /api/ {
        proxy_pass http://backend:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /ws {
        proxy_pass http://backend:8000/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";  # WebSocket 업그레이드 필수
    }
}
```

### 환경변수 관리

```
# .env.local (git에 올리지 않음)
DATABASE_URL=postgresql://esg_user:esg_pass@db:5432/esg_db
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# .env.example (git에 올림 — 템플릿)
DATABASE_URL=postgresql://USER:PASS@HOST:PORT/DB
SECRET_KEY=change-me
```

### 로컬 개발 실행 방법

```bash
# 전체 실행
docker-compose up --build

# DB만 실행 (백엔드 로컬 실행 시)
docker-compose up db

# 로그 확인
docker-compose logs -f backend

# DB 초기화
docker-compose down -v  # 볼륨까지 삭제
```

### 흔한 실수

| 실수 | 결과 | 해결 |
|------|------|------|
| depends_on만 사용 | DB 준비 전 백엔드 시작 | `healthcheck` + `condition: service_healthy` |
| node_modules를 volume mount | 컨테이너 내 모듈 덮어씌움 | `/app/node_modules` 익명 볼륨으로 보존 |
| nginx에서 WebSocket 프록시 미설정 | WS 연결 실패 | `Upgrade`, `Connection` 헤더 필수 |
| SECRET_KEY를 코드에 하드코딩 | 보안 취약점 | 환경변수로만 관리 |
| try_files 없는 nginx | SPA 새로고침 404 | `try_files $uri $uri/ /index.html` |

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
| 7단계 | Railway 배포 전략 | ⏳ 대기 |
| 8단계 | CI/CD 자동화 | ⏳ 대기 |
| 9단계 | 운영 고려사항 | ⏳ 대기 |
