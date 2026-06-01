export type Gender = 'male' | 'female'
export type Role = 'user' | 'admin'

export interface AuthUser {
  token: string
  username: string
  gender: Gender
  role: Role
}