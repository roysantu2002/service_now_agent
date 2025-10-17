'use client'

import { useSession } from 'next-auth/react'
import { User } from '@/types'

export function useAuth() {
  const { data: session, status } = useSession()
  
  return {
    user: session?.user as User | undefined,
    isLoading: status === 'loading',
    isAuthenticated: status === 'authenticated',
    role: session?.user?.role,
    isAdmin: session?.user?.role === 'ADMIN',
    isUser: session?.user?.role === 'USER',
  }
}