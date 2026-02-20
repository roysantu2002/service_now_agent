import { Navigation } from '@/components/layout/navigation'
import { Hero } from '@/components/layout/hero'
import { Services } from '@/components/layout/services'
import { Footer } from '@/components/layout/footer'
import { OracleFlow } from "@/components/oracle/oracle-flow"
export default function HomePage() {
  return (
    <div className="min-h-screen bg-white dark:bg-gray-900">
      <Navigation />
      <main>
        <Hero />
        <OracleFlow />
        <Services />
      </main>
      <Footer />
    </div>
  )
}