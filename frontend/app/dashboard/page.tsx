'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/hooks/use-auth'
import { Navigation } from '@/components/layout/navigation'
import { AdminDashboard } from '@/components/dashboard/admin-dashboard'
import { UserDashboard } from '@/components/dashboard/user-dashboard'
import { Footer } from '@/components/layout/footer'

export default function DashboardPage() {
  const { isAuthenticated, isLoading, isAdmin } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/auth/signin')
    }
  }, [isAuthenticated, isLoading, router])

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return null
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <Navigation />
      <main className="py-8">
        {isAdmin ? <AdminDashboard /> : <UserDashboard />}
      </main>
      <Footer />
    </div>
  )
}