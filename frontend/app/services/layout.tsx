import { ReactNode } from 'react'
import {ServicesNavigation} from '@/components/layout/services-navigation'
import { Hero } from '@/components/layout/hero'
import { Footer } from '@/components/layout/footer'

interface ServicesLayoutProps {
  children: ReactNode
  heroTitle?: string
  heroSubtitle?: string
}

export default function ServicesLayout({
  children,
  heroTitle = 'Unified AI Services Platform',
  heroSubtitle = 'Streamline your operations with AI-powered services for IT, analytics, and end-user support.'
}: ServicesLayoutProps) {
  return (
    <div className="flex flex-col min-h-screen bg-gray-50 dark:bg-gray-900">
      <ServicesNavigation />
      {/* <Hero title={heroTitle} subtitle={heroSubtitle} /> */}
      <main className="flex-grow">{children}</main>
      <Footer />
    </div>
  )
}
