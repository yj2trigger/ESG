import { describe, it, expect, beforeEach } from 'vitest'
import { useAuthStore } from '../store/authStore'

describe('useAuthStore', () => {
  beforeEach(() => {
    // 각 테스트 전 store 상태와 localStorage 초기화
    useAuthStore.setState({ gender: null })
    localStorage.clear()
  })

  it('초기 gender는 null입니다', () => {
    expect(useAuthStore.getState().gender).toBeNull()
  })

  it('setGender로 male을 설정할 수 있습니다', () => {
    useAuthStore.getState().setGender('male')
    expect(useAuthStore.getState().gender).toBe('male')
  })

  it('setGender로 female을 설정할 수 있습니다', () => {
    useAuthStore.getState().setGender('female')
    expect(useAuthStore.getState().gender).toBe('female')
  })

  it('clearGender로 gender를 null로 초기화합니다', () => {
    useAuthStore.getState().setGender('male')
    useAuthStore.getState().clearGender()
    expect(useAuthStore.getState().gender).toBeNull()
  })

  it('setGender 후 gender를 다른 값으로 변경할 수 있습니다', () => {
    useAuthStore.getState().setGender('male')
    useAuthStore.getState().setGender('female')
    expect(useAuthStore.getState().gender).toBe('female')
  })
})
