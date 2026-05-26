# PORTFOLIO — ESG 기숙사 세탁기 예약 시스템

> 한양대학교 ERICA 기숙사 세탁기 실시간 현황 조회 및 대기열 예약 서비스  
> 단독 풀스택 개발 | 2025년 5월 ~ (진행 중)

**라이브:** https://esg-laundry-checker.vercel.app  
**스택:** FastAPI · React 18 · PostgreSQL · WebSocket · Fly.io · Supabase · Vercel

---

## 문제

기숙사 세탁기 현황을 확인하려면 직접 세탁실에 가야 한다. 모두 사용 중이면 허탕. 반복 방문, 세탁실 앞 대기가 일상.

**핵심 질문:** 세탁실에 가기 전에, 지금 세탁기가 비어 있는지 알 수 있는가?

---

## 해결책

3단계 모드 시스템 — 세탁기 가용 대수에 따라 자동 모드 전환.

| 모드 | 상황 | 동작 |
|------|------|------|
| **Mode A** | available 多 | 사용자가 층/번호 직접 선택 |
| **Mode B** | available 1~3대 | 시스템이 1대 자동 배정, 10분 소프트 예약 |
| **Mode C** | available 0대 | 대기열 등록 → 빈 자리 발생 시 5분 수락 창 → 수락 시 10분 소프트 예약 |

---

## 주요 기능

### 실시간 WebSocket 상태 동기화

polling 없이 세탁기 상태 변경을 즉시 전파. 성별 구역별 채널 분리.

### 5분 수락 창 (Mode C)

즉시 배정 대신 수락 요청 전송 → 5분 내 수락 시 확정. 미수락 시 대기열 맨 뒤로 → 다음 대기자에게 offer.  
알림을 놓친 사용자에게 세탁기가 10분간 점유되는 문제 방지.

### 소프트 예약 복원

`GET /machines/my-reservation`으로 페이지 새로고침 후 예약 상태 복원, 카운트다운 유지.

### 한양대 이메일 인증

`@hanyang.ac.kr` 도메인 + 6자리 OTP → 재학생만 접근 가능.

### 모바일 PWA

standalone 모드 + Fullscreen API. 세탁실로 이동하면서 스마트폰으로 확인 가능.

### 어드민 패널

세탁기 상태 수동 관리, 대기열 알림 수동 트리거.

### IoT 연동 (엔드포인트 준비 완료)

`POST /iot/machines/{id}/status` — 실제 세탁기 센서 신호 수신.  
Tuya Cloud Smart Home 프로젝트 생성 완료, 크레덴셜 확보 (Client ID / Secret / Project ID).  
HMAC-SHA256 서명 + Adaptive Polling으로 API quota 67% 유지 (17,460/26,000 호출/월).  
현재: 장치 물리 연결 대기 중.

### DB Quota 관리 (계획 수립 완료)

IoT 연동 후 `machine_status_logs` ~14,400 행/일 예상.  
30일 자동 정리 + 80%/90% 임계값 Gmail SMTP 알림 설계 완료 (`maintenance_service.py` 구현 예정).

---

## 기술 스택

```
Frontend   React 18 + TypeScript + Zustand
           → Vercel (GitHub push → 자동 배포)

Backend    FastAPI (Python 3.12) + SQLAlchemy 2.x
           → Fly.io (Docker, auto_stop_machines=false)

Database   PostgreSQL (Supabase managed)
           Alembic 마이그레이션, Session Pooler (IPv4 지원)

실시간     WebSocket (FastAPI native)
           성별별 브로드캐스트 + 1:1 offer 전송

인증       JWT 7일 + bcrypt + Gmail SMTP OTP
```

---

## 아키텍처 결정 (주요 ADR)

| ADR | 결정 | 핵심 이유 |
|-----|------|-----------|
| ADR-001 | WebSocket | polling 대비 대기열 알림 지연 없음 |
| ADR-002 | Fly.io + Supabase + Vercel | WS 장기 연결 — Railway cold start 탈락 |
| ADR-003 | Lazy Expiration | Celery/Redis 없이 WS keepalive 재활용 |
| ADR-004 | Gmail SMTP | Resend 무료 외부 도메인 발송 불가 |
| ADR-005 | IoT REST 선설계 | 장치 없이 curl로 검증 가능한 구조 |
| ADR-006 | 5분 수락 창 | 즉시 배정 시 미확인 사용자 10분 낭비 방지 |
| ADR-007 | Adaptive Polling | 734,400 → 17,460 호출/월 (97.6% 절감), quota 67% 유지 |

ADR 전체 목록 → [task-management-repository/portfolio/ESG/decisions/](https://github.com/yj2trigger/task-management-repository/tree/main/portfolio/ESG/decisions)

---

## 해결한 문제들

| 문제 | 원인 | 해결 |
|------|------|------|
| 소프트 예약 배너 즉시 소멸 | timezone-naive datetime → JS 로컬 파싱 → 9시간 오차 | TIMESTAMPTZ 마이그레이션 |
| Mode B 결과 즉시 사라짐 | 모드 전환 → 컴포넌트 언마운트 → 로컬 상태 소멸 | 부모 컴포넌트로 lift up |
| 대기열 notified 상태 복원 실패 | `/queue/status`가 waiting만 조회 | `get_entry()` status 무관 조회로 변경 |
| 어드민 알림 트리거 미작동 | `available` 전환 시 `_notify_queue_and_broadcast()` 미연결 | 상태 변경 핸들러에 연결 |
| Supabase IPv6 DNS 실패 | Direct URL이 IPv6 전용 | Session Pooler URL로 전환 |
| Alembic `%` 보간 오류 | configparser가 `%40`를 보간 문법으로 해석 | `create_engine()` 직접 사용 |
| React StrictMode WS 1006 | StrictMode effect 2회 실행 → 첫 연결 즉시 종료 | 프로덕션 빌드에서 미발생 — 무시 |

사고 상세 분석 → [task-management-repository/portfolio/ESG/postmortems/](https://github.com/yj2trigger/task-management-repository/tree/main/portfolio/ESG/postmortems)

---

## 배운 것

**React 상태 설계:**  
컴포넌트 언마운트 = 로컬 상태 소멸. "이 상태가 어떤 조건에서 살아있어야 하는가"를 트리 구조보다 먼저 정의 → lift up 결정.

**Datetime timezone 계약:**  
백엔드-프론트 datetime 교환 시 항상 UTC + `Z` suffix 명시. SQLite(naive) vs PostgreSQL(aware) 테스트 환경 차이 → naive/aware guard 필수.

**IoT 선설계 패턴:**  
장치 없이 엔드포인트 먼저 설계 → curl로 검증 → 장치 연결 시 URL+Key만 설정. `IOT_DEVICE_KEY` 미설정 시 503 graceful degradation.

**API Quota 설계:**  
단순 폴링 734,400 호출/월 → 무료 26,000/월의 28×. Mode별 adaptive interval + 심야 감소로 17,460/월 (quota 67%).

**엔티티 상태 추가 시 3-step:**  
① status API 노출 ② 마운트 복원 ③ UI 분기. notified 상태 복원 누락 시 배너 소멸 + 잘못된 버튼 표시.

**DB Quota 선제 관리:**  
IoT 연동 전 로그 급증량 계산 (~14,400 행/일) → retention policy + 경보 임계값 먼저 설계. 실제 서비스 중단보다 사전 설계 비용이 훨씬 낮음.

---

## 현재 상태 및 다음 단계

| 항목 | 상태 |
|------|------|
| 핵심 기능 전체 (Mode A/B/C, WS, 예약 복원) | ✅ 운영 중 |
| 이메일 인증 (hanyang.ac.kr OTP) | ✅ |
| CI/CD (pytest + vitest → Fly.io + Vercel) | ✅ |
| Alembic 마이그레이션 (TIMESTAMPTZ) | ✅ Supabase 적용 완료 |
| IoT 엔드포인트 | ✅ 준비 완료 (curl 검증) |
| Tuya Cloud 크레덴셜 | ✅ 확보 완료 |
| Tuya 장치 물리 연결 | ⏳ 대기 중 |
| `maintenance_service.py` (DB 자동 정리) | ⏳ 구현 예정 |
| `GET /admin/system/stats` (DB 사용량 게이지) | ⏳ 구현 예정 |
| PWA Push Notification (백그라운드) | 🔵 계획 중 |

---

## 협업 인프라

단독 개발이지만 팀 확장을 고려해 초기부터 구성.

- `feature/* → main` GitHub Flow, main Branch Protection (PR + CI 필수)
- pytest + vitest CI, Fly.io + Vercel CD
- `ONBOARDING.md` — 환경 구성부터 WS 이벤트까지 전체 문서화

---

## 상세 포트폴리오 문서

모든 상세 문서는 [task-management-repository/portfolio/ESG/](https://github.com/yj2trigger/task-management-repository/tree/main/portfolio/ESG)에서 관리.

- [아키텍처 & 데이터 모델](https://github.com/yj2trigger/task-management-repository/blob/main/portfolio/ESG/architecture.md)
- [보안 설계](https://github.com/yj2trigger/task-management-repository/blob/main/portfolio/ESG/security.md)
- [개발 판단 기록 (dev_log)](https://github.com/yj2trigger/task-management-repository/blob/main/portfolio/ESG/dev_log.md)
- [문제 정의](https://github.com/yj2trigger/task-management-repository/blob/main/portfolio/ESG/problem_statement.md)
- [사고 기록 (Postmortems)](https://github.com/yj2trigger/task-management-repository/tree/main/portfolio/ESG/postmortems)
- [ADR 목록](https://github.com/yj2trigger/task-management-repository/tree/main/portfolio/ESG/decisions)
