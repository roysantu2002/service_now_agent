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

const features = [
  {
    icon: CpuChipIcon,
    title: 'AI-Powered Analysis',
    description: 'Advanced machine learning algorithms for intelligent incident processing and insights.'
  },
  {
    icon: ShieldCheckIcon,
    title: 'Enterprise Security',
    description: 'Role-based access control and compliance filtering for sensitive data protection.'
  },
  {
    icon: ChartBarIcon,
    title: 'Real-time Analytics',
    description: 'Comprehensive dashboards and reporting for data-driven decision making.'
  },
  {
    icon: RocketLaunchIcon,
    title: 'Scalable Platform',
    description: 'Built for enterprise scale with microservices architecture and cloud-native design.'
  }
]

export function Hero() {
  const { isAuthenticated } = useAuth()

  return (
    <section className="relative isolate overflow-hidden bg-gradient-to-br from-blue-50 via-white to-purple-50 dark:from-gray-900 dark:via-gray-800 dark:to-purple-900">
      {/* Decorative Backgrounds */}
      <div className="absolute inset-x-0 -top-40 -z-10 transform-gpu overflow-hidden blur-3xl sm:-top-72">
        <div className="relative left-1/2 w-[36rem] -translate-x-1/2 rotate-[30deg] aspect-[1155/678] bg-gradient-to-tr from-blue-400 to-purple-600 opacity-20 sm:w-[70rem]" />
      </div>

      {/* Main content container */}
      <div className="mx-auto max-w-7xl px-6 py-16 sm:py-24 lg:flex lg:items-center lg:justify-between lg:px-8 lg:py-32">
        {/* Left Text Section */}
        <div className="max-w-2xl mx-auto text-center lg:text-left lg:max-w-xl lg:mx-0">
          {/* Tag */}
          <div className="flex justify-center lg:justify-start items-center gap-x-4 mb-6 sm:mb-8">
            <span className="rounded-full bg-blue-600/10 px-3 py-1 text-sm font-semibold leading-6 text-blue-600 ring-1 ring-inset ring-blue-600/10">
              Latest Updates
            </span>
            <span className="inline-flex items-center space-x-1 text-sm font-medium leading-6 text-gray-600 dark:text-gray-400">
              <span>v2.1 is here</span>
              <ChartBarIcon className="h-5 w-5 text-gray-400" />
            </span>
          </div>

          {/* Heading */}
          <h1 className="text-4xl font-bold tracking-tight text-gray-900 dark:text-white sm:text-5xl lg:text-6xl">
            Unified AI Services Platform
          </h1>

          {/* Subtext */}
          <p className="mt-6 text-base sm:text-lg leading-8 text-gray-600 dark:text-gray-300">
            Streamline your operations with our comprehensive AI-powered platform.
            Manage incidents, analyze logs, implement RAG solutions, and gain actionable
            insights — all with enterprise-grade security and compliance.
          </p>

          {/* CTA Buttons */}
          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center lg:justify-start gap-4">
            {isAuthenticated ? (
              <>
                <Button asChild size="lg" className="w-full sm:w-auto">
                  <Link href="/dashboard">Go to Dashboard</Link>
                </Button>
                <Button variant="outline" size="lg" asChild className="w-full sm:w-auto">
                  <Link href="/services">Explore Services</Link>
                </Button>
              </>
            ) : (
              <>
                <Button asChild size="lg" className="w-full sm:w-auto">
                  <Link href="/auth/signin">Get Started</Link>
                </Button>
                <Button variant="outline" size="lg" asChild className="w-full sm:w-auto">
                  <Link href="#features">Learn More</Link>
                </Button>
              </>
            )}
          </div>
        </div>

        {/* Right Features Grid */}
        <div className="mt-16 sm:mt-20 lg:mt-0 lg:ml-12 xl:ml-24 flex justify-center lg:justify-end">
          <div className="w-full max-w-lg sm:max-w-xl lg:max-w-2xl">
            <div className="rounded-2xl bg-white dark:bg-gray-800 shadow-2xl ring-1 ring-gray-900/10 overflow-hidden">
              <div className="bg-gray-800 px-4 py-3 flex space-x-2">
                <span className="h-3 w-3 rounded-full bg-red-500"></span>
                <span className="h-3 w-3 rounded-full bg-yellow-500"></span>
                <span className="h-3 w-3 rounded-full bg-green-500"></span>
              </div>
              <div className="p-6 sm:p-8">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6">
                  {features.map((feature, index) => (
                    <div
                      key={index}
                      className="rounded-lg bg-gray-50 dark:bg-gray-900 p-4 transition hover:bg-gray-100 dark:hover:bg-gray-800"
                    >
                      <feature.icon className="h-8 w-8 text-blue-600 mb-3" />
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-1">
                        {feature.title}
                      </h3>
                      <p className="text-gray-600 dark:text-gray-400 text-sm leading-6">
                        {feature.description}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Decorative bottom gradient */}
      <div className="absolute inset-x-0 top-[calc(100%-10rem)] -z-10 transform-gpu overflow-hidden blur-3xl sm:top-[calc(100%-20rem)]">
        <div className="relative left-1/2 w-[36rem] -translate-x-1/2 aspect-[1155/678] bg-gradient-to-tr from-purple-400 to-blue-600 opacity-25 sm:w-[70rem]" />
      </div>
    </section>
  )
}
