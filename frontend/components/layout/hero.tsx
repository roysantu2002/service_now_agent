'use client'

import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/hooks/use-auth'
import {
  RocketLaunchIcon,
  ChartBarIcon,
  ShieldCheckIcon,
  CpuChipIcon
} from '@heroicons/react/24/outline'

interface Feature {
  icon: any
  title: string
  description: string
}

interface HeroProps {
  title?: string
  subtitle?: string
  features?: Feature[]
}

const defaultFeatures: Feature[] = [
  {
    icon: CpuChipIcon,
    title: 'AI-Powered Automation',
    description: 'Automate analysis, routing, and remediation across multiple tech towers.'
  },
  {
    icon: ShieldCheckIcon,
    title: 'Enterprise Security',
    description: 'Compliance-ready AI with role-based access and secure data layers.'
  },
  {
    icon: ChartBarIcon,
    title: 'Unified Intelligence',
    description: 'Cross-domain insights from incidents, logs, chatbots, middleware, and more.'
  },
  {
    icon: RocketLaunchIcon,
    title: 'Scalable Integration',
    description: 'A platform engineered for Citi-scale workloads and multi-tower adoption.'
  }
]

export function Hero({ title, subtitle, features = defaultFeatures }: HeroProps) {
  const { isAuthenticated } = useAuth()

  return (
    <section className="relative bg-[#0A0F1A] text-white py-24 px-6 overflow-hidden">
      {/* Subtle floating dot pattern */}
      <div className="pointer-events-none absolute inset-0 opacity-10 bg-[radial-gradient(circle_at_center,rgba(255,255,255,0.12)_1px,transparent_1px)] bg-[length:30px_30px]" />

      <div className="relative max-w-7xl mx-auto">
        {/* Title area */}
        <h1 className="text-4xl sm:text-5xl font-bold tracking-tight text-white">
          {title || 'Unified AI Services Platform'}
        </h1>

        <p className="mt-6 max-w-3xl text-gray-300 leading-relaxed">
          {subtitle ||
            'AI-Enabled Automation Across Technology Towers.'}
        </p>

        {/* CTA Buttons */}
        <div className="mt-10 flex flex-col sm:flex-row gap-4">
          {isAuthenticated ? (
            <>
              <Button asChild size="lg">
                <Link href="/dashboard">Go to Dashboard</Link>
              </Button>
              <Button variant="outline" size="lg" asChild>
                <Link href="/services">Explore Services</Link>
              </Button>
            </>
          ) : (
            <>
              <Button asChild size="lg">
                <Link href="/auth/signin">Get Started</Link>
              </Button>
              <Button variant="outline" size="lg" asChild>
                <Link href="#features">Learn More</Link>
              </Button>
            </>
          )}
        </div>

        {/* Feature Section (VS Code three-column update style) */}
        <div className="mt-20 grid grid-cols-1 md:grid-cols-3 gap-10">
          {/* Column 1 */}
          <div>
            <div className="border border-blue-400/40 px-4 py-2 inline-block rounded-md mb-6 text-blue-300">
              Automation
            </div>

            <ul className="space-y-6">
              <li className="flex items-start">
                <span className="mt-1 mr-3 h-2 w-2 bg-blue-400 rounded-full"></span>
                Intelligent incident triage & root-cause automation
              </li>
              <li className="flex items-start">
                <span className="mt-1 mr-3 h-2 w-2 bg-blue-400 rounded-full"></span>
                Automated workflow & code generation with LLMs
              </li>
              <li className="flex items-start">
                <span className="mt-1 mr-3 h-2 w-2 bg-blue-400 rounded-full"></span>
                Smart resolution & document interpretation
              </li>
            </ul>
          </div>

          {/* Column 2 */}
          <div>
            <div className="border border-purple-400/40 px-4 py-2 inline-block rounded-md mb-6 text-purple-300">
              Security & Trust
            </div>

            <ul className="space-y-6">
              <li className="flex items-start">
                <span className="mt-1 mr-3 h-2 w-2 bg-purple-400 rounded-full"></span>
                Policy-driven access controls across services
              </li>
              <li className="flex items-start">
                <span className="mt-1 mr-3 h-2 w-2 bg-purple-400 rounded-full"></span>
                Governance layers for compliant AI adoption
              </li>
              <li className="flex items-start">
                <span className="mt-1 mr-3 h-2 w-2 bg-purple-400 rounded-full"></span>
                Enterprise-grade data routing & secure LLM integration
              </li>
            </ul>
          </div>

          {/* Column 3 */}
          <div>
            <div className="border border-green-400/40 px-4 py-2 inline-block rounded-md mb-6 text-green-300">
              Engineering Innovation
            </div>

            <ul className="space-y-6">
              <li className="flex items-start">
                <span className="mt-1 mr-3 h-2 w-2 bg-green-400 rounded-full"></span>
                Scalable cross-tower orchestration
              </li>
              <li className="flex items-start">
                <span className="mt-1 mr-3 h-2 w-2 bg-green-400 rounded-full"></span>
                AI-first infrastructure using modern LLMs
              </li>
              <li className="flex items-start">
                <span className="mt-1 mr-3 h-2 w-2 bg-green-400 rounded-full"></span>
                Built with React, Next.js, FastAPI, ServiceNow, Kore.ai & more
              </li>
            </ul>
          </div>
        </div>

        {/* Attribution */}
        <p className="mt-16 text-gray-400 text-sm">
          Presented by: <span className="text-white">AI & Engineering Innovation Team</span>
        </p>
      </div>
    </section>
  )
}
