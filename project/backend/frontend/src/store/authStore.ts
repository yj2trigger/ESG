import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { AuthUser, Gender } from '../types/user'

interface AuthState {
  gender: Gender | null
  user: AuthUser | null
  setGender: (gender: Gender) => void
  setUser: (user: AuthUser) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      gender: null,
      user: null,
      setGender: (gender) => set({ gender }),
      setUser: (user) => set({ user, gender: user.gender }),
      logout: () => set({ gender: null, user: null }),
    }),
    { name: 'esg-auth' }
  )
)