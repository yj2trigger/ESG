/**
 * 테스트 구조가 정상 동작하는지 확인하는 기본 테스트입니다.
 * 각 기능 구현 시 해당 store/유틸 테스트가 이 디렉토리에 추가됩니다.
 *
 * 실행 방법 (project/frontend/ 디렉토리에서):
 *   npm run test        → 1회 실행
 *   npm run test:watch  → 변경 감지 실행
 */

import { describe, it, expect } from 'vitest'

describe('테스트 환경', () => {
  it('vitest가 정상 동작합니다', () => {
    expect(1 + 1).toBe(2)
  })
})
