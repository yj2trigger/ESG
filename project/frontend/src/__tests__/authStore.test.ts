import { describe, it, expect, beforeEach } from 'vitest'
import { useAuthStore } from '../store/authStore'
import { AuthUser } from '../types/user'

const mockUser: AuthUser = {
  token: 'test-token-abc',
  username: 'testuser',
  gender: 'male',
  role: 'user',
}

describe('useAuthStore', () => {
  beforeEach(() => {
    useAuthStore.setState({ gender: null, user: null })
    localStorage.clear()
  })

  it('초기 상태는 null입니다', () => {
    const { gender, user } = useAuthStore.getState()
    expect(gender).toBeNull()
    expect(user).toBeNull()
  })

  it('setGender로 성별을 설정할 수 있습니다', () => {
    useAuthStore.getState().setGender('male')
    expect(useAuthStore.getState().gender).toBe('male')
  })

  it('setUser로 유저와 성별을 동시에 설정합니다', () => {
    useAuthStore.getState().setUser(mockUser)
    const state = useAuthStore.getState()
    expect(state.user).toEqual(mockUser)
    expect(state.gender).toBe('male')
  })

  it('logout으로 모든 상태를 초기화합니다', () => {
    useAuthStore.getState().setUser(mockUser)
    useAuthStore.getState().logout()
    const state = useAuthStore.getState()
    expect(state.user).toBeNull()
    expect(state.gender).toBeNull()
  })

  it('setGender 후 setUser 하면 gender는 user.gender로 덮입니다', () => {
    useAuthStore.getState().setGender('male')
    const femaleUser: AuthUser = { ...mockUser, gender: 'female' }
    useAuthStore.getState().setUser(femaleUser)
    expect(useAuthStore.getState().gender).toBe('female')
  })
})