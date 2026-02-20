import { ReactNode } from 'react'
import { Hero } from '@/components/layout/hero'
import { Footer } from '@/components/layout/footer'
import { ServicesNavigation } from '@/components/layout/services-navigation'

interface EUSLayoutProps {
  children: ReactNode
}

export default function EUSLayout({ children }: EUSLayoutProps) {
  return (
    <div className="flex flex-col min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Navigation */}
      {/* <ServicesNavigation /> */}

      {/* Hero Section */}
      {/* <Hero 
        title="End-User Services" 
        subtitle="Empowering employees with AI-driven support and automation." 
      /> */}

      {/* Page Content */}
      <main className="flex-grow">{children}</main>

      {/* Footer */}
      <Footer />
    </div>
  )
}
