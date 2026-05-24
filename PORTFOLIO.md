# AI 주도 개발 사례 — 포트폴리오

> 작성일: 2026-05-23 (최종 업데이트: 2026-05-25)
> 프로젝트: 기숙사 세탁기 예약 서비스 (ESG) + EDK 키오스크 (ic-pbl)

---

## 개요

2026년 5월, 두 개의 프로젝트를 AI(Claude)와 함께 진행했습니다.
단순히 코드를 생성시키는 수준이 아니라, 설계 의사결정과 문서화, 실제 구현까지 AI를 도구로 삼아 직접 주도한 사례입니다.

---

## 프로젝트 1: ESG — 기숙사 세탁기 예약 서비스

### 무엇을 만들었나

소프트웨어융합대학 기숙사생들이 세탁기 사용 가능 여부를 스마트폰으로 확인하고,
상황에 따라 다르게 대응할 수 있는 웹앱입니다.

**핵심 로직: 3-Mode State Machine**

세탁기 수에 따라 세 가지 모드로 분기합니다.

- **4대 이상 (Mode A)**: 층별 이용 가능 수 표시. 사용자가 직접 판단해서 이동.
- **1~3대 (Mode B)**: "사용하시겠습니까?" 버튼 → 세탁기 1대 위치를 해당 사용자에게만 공개 + 10분 소프트 예약.
- **0대 (Mode C)**: 대기열 등록 → 세탁기가 비면 순서대로 WebSocket 알림 발송 → 10분 미사용 시 다음 대기자에게 이동.

**기술 스택**: React + TypeScript / FastAPI / PostgreSQL / Docker / Fly.io + Supabase + Vercel

**인증**: 한양대 이메일(@hanyang.ac.kr) 도메인 제한 + 6자리 OTP 코드 인증 (Resend 발송)

---

### AI를 어떻게 활용했나

#### 1. 설계 전 과정을 AI와 함께 진행

직접 요구사항을 정의하고, AI에게 각 단계별 설계를 작성하도록 지시했습니다.
단순히 출력을 수용한 게 아니라, 매 단계마다 검토하고 방향을 수정했습니다.

**10단계 설계 과정:**

| 단계 | 내용 | 주요 결정 |
|------|------|---------|
| 1단계 | 서비스 정의 | Mode A/B/C 분기 기준을 "전체 이용 가능 수"로 확정 |
| 2단계 | 시스템 아키텍처 | WebSocket 양방향 통신 채택, Redis 대신 PostgreSQL로 대기열 관리 |
| 3단계 | 프론트엔드 구조 | Zustand 채택 (Redux 대비 보일러플레이트 최소화), FloorCard 컴포넌트가 모드를 모르도록 설계 |
| 4단계 | 백엔드 구조 | Router → Service → Repository 3계층 분리, Mode 계산은 반드시 백엔드에서 |
| 5단계 | DB 설계 | Lazy expiration 방식 채택 (APScheduler 없이 GET 요청 시 만료 처리) |
| 6단계 | Docker 구성 | healthcheck + depends_on으로 DB 준비 후 백엔드 시작 보장 |
| 7단계 | Fly.io + Supabase + Vercel 배포 | Railway 무료 종료 → 무료 대안 3종으로 전환 |
| 8단계 | CI/CD | GitHub Actions, main push 시 flyctl + vercel 자동 배포 |
| 9단계 | 운영 | Rate limiting (slowapi), soft_reserve 중복 방지 (409) |
| 10단계 | 이메일 인증 | @hanyang.ac.kr 도메인 제한 + 6자리 OTP (Resend) |

#### 2. 설계 오류를 직접 발견하고 수정

AI가 "정보 제공 서비스"로 설계한 것을 "실제 판매 서비스"로 수정했습니다.
이 결정으로 payment.py, cart.py 제거 계획이 유지로 바뀌었고,
결제 화면 3개가 재활용 대상으로 전환되어 구현 작업량이 줄었습니다.

#### 3. 문서 왜곡 검토

AI가 이전 대화에서 생성한 설계 내용이 실제 원본과 다르게 저장된 것을 발견했습니다.
(`full_plan.md`에 3~7단계가 완료된 것처럼 기록되었으나 실제로는 1~2단계만 완료)
직접 원본과 대조하며 수정을 지시했습니다.

#### 4. AI 협업 체계 설계

프로젝트 도중, AI가 작업을 독단적으로 진행하는 문제를 인식하고
다음 규칙을 직접 정의해서 문서화했습니다:

- 모호한 점은 작업 전에 질문할 것
- 작업 계획을 먼저 설명하고 승인받을 것
- 한 단계 완료 후 결과를 정리하고 다음 단계 승인을 받을 것
- 기능 구현 시 테스트를 함께 작성할 것

이 규칙은 `COLLABORATION_RULES.md`로 저장되어 다른 AI가 이 프로젝트를 이어받을 때도 적용됩니다.

#### 5. 메타-리포지토리 구성

두 개의 프로젝트(ESG, ic-pbl)를 단일 관리 레포(`task-management-repository`)로 통합했습니다.

- 각 프로젝트의 설계 문서를 한 곳에서 관리
- `CURRENT_STATE.md`를 진행 상태의 단일 소스로 활용
- `AI_HANDOVER.md`로 AI가 대화를 이어받을 때 즉시 컨텍스트를 파악할 수 있도록 구성
- `tasks/backlog.md`, `in-progress.md`, `done.md`로 작업 흐름 관리

---

### 구체적인 기술 결정 사례

#### WebSocket 채널 분리

단순히 WebSocket으로 broadcast하면 남성 사용자에게 여성 전용 세탁기 정보가 노출됩니다.
이 문제를 직접 인식하고 AI에게 gender 기반 채널 분리를 설계하도록 지시했습니다.

```python
class ConnectionManager:
    male_connections: list[WebSocket] = []
    female_connections: list[WebSocket] = []

    async def broadcast_to_gender(self, gender: str, message: dict):
        # gender 기반 채널 분리
```

#### 인증 범위 결정 — 초기 → 실서비스

초기에는 프로토타입 단계에서 복잡도를 낮추기 위해 "성별 선택 + localStorage 저장"으로 인증을 대체했습니다.
이후 실제 서비스로 발전시키면서 JWT 인증을 도입하고, 추가로 1인 1계정 제한이 필요하다는 것을 판단했습니다.

**인증 방식 후보 검토:**

| 방식 | 장점 | 단점 | 결정 |
|------|------|------|------|
| Kakao OAuth | 구현 간단 | 학교 구성원 제한 불가 | 탈락 |
| 학교 SSO | 확실한 학교 인증 | API 접근 불가 | 탈락 |
| 학교 이메일 도메인 제한 | 무료, 구현 가능 | 졸업생도 사용 가능 (감수) | **채택** |

`@hanyang.ac.kr` 도메인 검증 + Resend로 6자리 OTP 발송. 인증 전 로그인 차단(403).
이 결정으로 Kakao Developer 등록 없이 학교 구성원 제한이 가능해졌습니다.

#### 무료 배포 스택 전환 결정

Railway가 2024년 무료 플랜을 종료했다는 것을 확인하고, 배포 전략을 전면 재검토했습니다.
AI에게 역할별 무료 대안을 분석하도록 지시하고, 세 가지 플랫폼으로 분산하는 결정을 직접 내렸습니다.

| 역할 | Railway (기존) | 변경 후 | 이유 |
|------|---------------|---------|------|
| Backend | Railway | Fly.io | WebSocket 상시 가동 필요, Docker 네이티브 |
| Database | Railway PostgreSQL | Supabase | 무료 500MB, 별도 관리 용이 |
| Frontend | Railway | Vercel | 정적 파일 배포 특화, CDN 자동 |

**Fly.io 선택 근거**: `auto_stop_machines = false` 설정으로 WebSocket 연결 끊김 방지.
Render 대안도 검토했으나 15분 비활성 시 슬립 → WebSocket 재연결 문제로 탈락.

#### Lazy expiration 채택

10분 타이머를 APScheduler로 정확하게 처리하는 방식 대신,
GET 요청 시 만료된 예약을 자동 해제하는 Lazy expiration 방식을 채택했습니다.
프로토타입에서 불필요한 인프라 복잡도를 줄이기 위한 결정입니다.

---

## 프로젝트 2: ic-pbl (EDK) — 일반의약품 키오스크

### 무엇을 만들었나

소프트웨어융합대학 학관 내 무인 키오스크로, 증상을 선택하면 해당하는 일반의약품/영양제를 추천하고 실제로 구매할 수 있는 시스템입니다.

**기술 스택**: Python / PyQt6 / SQLite(JSON)

---

### AI를 어떻게 활용했나

#### 1. 도메인 전환 판단

기존에 커피/영양구미 판매 키오스크로 구현된 코드베이스를 의약품 키오스크로 전환하는 작업에서,
기존 코드의 어떤 부분을 재활용하고 어떤 부분을 교체할지 직접 판단했습니다.

**핵심 판단:**
- `payment.py`, `cart.py` — 실제 판매 서비스이므로 유지 (AI 초안은 제거로 설계)
- `product.py` → `medicine.py` — 도메인 교체 (최소 변경)
- `gui/screens/` — 화면 흐름은 유지, 내용만 교체

#### 2. 코드 기반으로 문서 업데이트

AI가 계획 문서(log_panel, state_machine 등)를 기반으로 문서를 관리하고 있었으나,
실제 구현된 코드(PyQt6, 10개 화면, VoiceService)와 다르다는 것을 발견했습니다.
AI에게 코드를 직접 읽고 실제 구현 기준으로 문서를 전면 재작성하도록 지시했습니다.

---

## 이 경험에서 배운 것

**AI는 도구입니다. 방향은 사람이 잡아야 합니다.**

AI가 잘하는 것:
- 설계 문서 작성 (구조화된 정보 정리)
- 반복적인 파일 생성/수정
- 코드 패턴 제안
- 여러 레포에 걸친 문서 동기화

AI가 못하는 것:
- 비즈니스 요구사항 파악 (직접 물어봐야 함)
- 실제 진행 상태와 문서의 일치 여부 판단
- 어떤 코드를 재활용하고 버릴지 결정

**실제로 문제가 된 사례:**
- AI가 "정보 제공 서비스"로 설계 → 결제 시스템 제거 → 직접 발견하고 수정
- AI가 3~7단계를 완료된 것처럼 기록 → 원본 대조 후 수정
- AI가 승인 없이 여러 단계를 한꺼번에 진행 → 협업 규칙 수립으로 해결
- Fly.io가 monorepo 구조를 인식 못함 → 루트에 Dockerfile 직접 작성 (project/backend 경로 명시)
- GitHub Actions 워크플로우를 `project/.github/workflows/`에 위치 → 루트로 이동해야 인식됨
- Vercel CLI `working-directory` + 프로젝트 Root Directory 설정 중복 → 경로 이중 적용 오류 → `working-directory` 제거로 해결

---

## 저장소 구조

```
task-management-repository/   ← 메타-리포 (문서/태스크 관리)
├── AI_HANDOVER.md            ← AI 인계 문서
├── COLLABORATION_RULES.md    ← AI 협업 규칙
├── docs/
│   ├── ic-pbl/               ← ic-pbl 설계 문서 전체
│   └── ESG/                  ← ESG 진행 상태
└── tasks/                    ← backlog / in-progress / done

ESG/                          ← 세탁기 예약 서비스 코드
├── fly.toml                  ← Fly.io 배포 설정
├── Dockerfile                ← project/backend 경로 참조
├── .github/workflows/        ← ci.yml + cd.yml (루트에 위치해야 GitHub이 인식)
└── project/
    ├── design_progress.md    ← 1~10단계 설계 전체
    ├── backend/              ← FastAPI (Supabase PostgreSQL 연결)
    └── frontend/             ← React + TypeScript (Vercel 배포)

pmg-ic-pbl/                   ← EDK 키오스크 코드
└── project/
    ├── docs/                 ← 설계 문서 (구 버전)
    └── src/app/              ← Python + PyQt6
```
