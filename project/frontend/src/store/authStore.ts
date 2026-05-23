import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { Gender } from '../types/user'

interface AuthState {
  gender: Gender | null
  setGender: (gender: Gender) => void
  clearGender: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      gender: null,
      setGender: (gender) => set({ gender }),
      clearGender: () => set({ gender: null }),
    }),
    {
      name: 'esg-auth',
    }
  )
)
