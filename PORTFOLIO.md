# ESG 기숙사 세탁기 예약 시스템

> 한양대학교 ERICA 기숙사 세탁기 실시간 현황 조회 및 대기열 예약 서비스  
> 단독 풀스택 개발 | 2025년 5월 ~ (진행 중)

**라이브:** https://esg-laundry-checker.vercel.app  
**스택:** FastAPI · React 18 · PostgreSQL · WebSocket · Fly.io · Supabase · Vercel

---

## 현재 상태

| 항목 | 상태 |
|------|------|
| 핵심 기능 전체 (Mode A/B/C, WS, 예약 복원) | ✅ 운영 중 |
| 이메일 인증 (hanyang.ac.kr OTP) | ✅ |
| CI/CD (pytest + vitest → Fly.io + Vercel) | ✅ |
| Alembic 마이그레이션 (TIMESTAMPTZ) | ✅ Supabase 적용 완료 |
| IoT 엔드포인트 | ✅ 준비 완료, Tuya 크레덴셜 확보 |
| Tuya 장치 물리 연결 | ⏳ 대기 중 |
| `maintenance_service.py` (DB 자동 정리) | ⏳ 구현 예정 |
| `GET /admin/system/stats` (DB 사용량 게이지) | ⏳ 구현 예정 |
| PWA Push Notification (백그라운드) | 🔵 계획 중 |

---

## 포트폴리오 상세 문서

> 설계 결정, 아키텍처, 개발 사고 기록, ADR, Postmortem 등 모든 상세 문서는  
> [task-management-repository/portfolio/ESG/](https://github.com/yj2trigger/task-management-repository/tree/main/portfolio/ESG) 에서 관리합니다.

| 문서 | 내용 |
|------|------|
| [README.md](https://github.com/yj2trigger/task-management-repository/blob/main/portfolio/ESG/README.md) | 프로젝트 개요, 핵심 기능, 기술 스택, ADR 요약, 배운 것 |
| [architecture.md](https://github.com/yj2trigger/task-management-repository/blob/main/portfolio/ESG/architecture.md) | 전체 구성, 데이터 모델, WS 이벤트 흐름, API 명세 |
| [dev_log.md](https://github.com/yj2trigger/task-management-repository/blob/main/portfolio/ESG/dev_log.md) | 구현 중 판단 기록, 막힌 지점, HOW + WHY NOT |
| [security.md](https://github.com/yj2trigger/task-management-repository/blob/main/portfolio/ESG/security.md) | JWT, OTP, IoT Device Key, CORS 설계 |
| [problem_statement.md](https://github.com/yj2trigger/task-management-repository/blob/main/portfolio/ESG/problem_statement.md) | 문제 배경, 사용 시나리오, 제약 |
| [decisions/](https://github.com/yj2trigger/task-management-repository/tree/main/portfolio/ESG/decisions) | ADR-001 ~ ADR-007 전체 |
| [postmortems/](https://github.com/yj2trigger/task-management-repository/tree/main/portfolio/ESG/postmortems) | 사고 원인 분석 및 해결 기록 |
