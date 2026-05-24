import { create } from 'zustand'
import { MachinesResponse } from '../types/machine'

interface MachineState {
  data: MachinesResponse | null
  loading: boolean
  error: string | null
  setData: (data: MachinesResponse) => void
  setLoading: (v: boolean) => void
  setError: (msg: string | null) => void
}

export const useMachineStore = create<MachineState>()((set) => ({
  data: null,
  loading: false,
  error: null,
  setData: (data) => set({ data, loading: false, error: null }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error, loading: false }),
}))