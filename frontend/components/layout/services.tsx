'use client'

import Link from 'next/link'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/hooks/use-auth'
import {
  DocumentMagnifyingGlassIcon,
  ExclamationTriangleIcon,
  DocumentTextIcon,
  ChartBarIcon,
  CpuChipIcon,
  ShieldCheckIcon,
  ServerStackIcon,
 
  ChatBubbleLeftRightIcon,
  WrenchScrewdriverIcon,
  UserGroupIcon,
  Cog6ToothIcon
} from '@heroicons/react/24/outline'
import { Service } from '@/types'

const services: Service[] = [
  {
    id: 'middleware',
    name: 'Middleware Integration',
    description: 'Unified integration layer for connecting legacy systems, APIs, and AI pipelines.',
    icon: 'ServerStackIcon',
    color: 'from-indigo-500 to-blue-600',
    endpoint: '/api/middleware',
    enabled: true,
    category: 'integration'
  },
  // {
  //   id: 'databases',
  //   name: 'Intelligent Databases',
  //   description: 'AI-optimized data handling with auto-tuning, indexing, and performance insights.',
  //   icon: 'DatabaseIcon',
  //   color: 'from-green-500 to-emerald-600',
  //   endpoint: '/api/databases',
  //   enabled: true,
  //   category: 'data'
  // },
  {
    id: 'eus',
    name: 'End User Services (EUS)',
    description: 'AI assistance for device management, access issues, and user support automation.',
    icon: 'UserGroupIcon',
    color: 'from-pink-500 to-rose-600',
    endpoint: '/api/eus',
    enabled: true,
    category: 'support'
  },
  {
    id: 'servicedesk',
    name: 'Service Desk Automation',
    description: 'Smart ticketing, classification, and resolution workflows using generative AI.',
    icon: 'WrenchScrewdriverIcon',
    color: 'from-blue-500 to-cyan-600',
    endpoint: '/api/servicedesk',
    enabled: true,
    category: 'operations'
  },
  {
    id: 'chatbot',
    name: 'Conversational AI Chatbot',
    description: 'Omnichannel chatbot for IT, HR, and customer queries with contextual memory.',
    icon: 'ChatBubbleLeftRightIcon',
    color: 'from-violet-500 to-purple-600',
    endpoint: '/api/chatbot',
    enabled: true,
    category: 'communication'
  },
  {
    id: 'rag',
    name: 'RAG Knowledge Engine',
    description: 'Retrieval-Augmented Generation for dynamic document insights and data reasoning.',
    icon: 'DocumentMagnifyingGlassIcon',
    color: 'from-teal-500 to-emerald-600',
    endpoint: '/api/rag',
    enabled: true,
    category: 'analysis'
  },
  {
    id: 'incident',
    name: 'Incident Management',
    description: 'AI-powered detection, triage, and resolution integrated with ServiceNow and Jira.',
    icon: 'ExclamationTriangleIcon',
    color: 'from-red-500 to-pink-600',
    endpoint: '/api/incidents',
    enabled: true,
    category: 'management'
  },
  {
    id: 'monitoring',
    name: 'Monitoring & Observability',
    description: 'Unified monitoring dashboards with anomaly detection and real-time metrics.',
    icon: 'ChartBarIcon',
    color: 'from-purple-500 to-violet-600',
    endpoint: '/api/monitoring',
    enabled: true,
    category: 'analytics'
  },
  {
    id: 'ml-insights',
    name: 'ML Insights',
    description: 'Machine learning models for predictive maintenance, risk scoring, and forecasting.',
    icon: 'CpuChipIcon',
    color: 'from-orange-500 to-amber-600',
    endpoint: '/api/ml',
    enabled: false,
    category: 'analysis'
  },
  {
    id: 'compliance',
    name: 'Compliance & Governance',
    description: 'Automated compliance validation and audit readiness with regulatory frameworks.',
    icon: 'ShieldCheckIcon',
    color: 'from-gray-600 to-slate-700',
    endpoint: '/api/compliance',
    enabled: false,
    category: 'governance'
  },
  {
    id: 'knowledgebase',
    name: 'Knowledge Base Automation',
    description: 'Auto-curated enterprise knowledge repository powered by LLM summarization.',
    icon: 'DocumentTextIcon',
    color: 'from-cyan-500 to-sky-600',
    endpoint: '/api/knowledge',
    enabled: true,
    category: 'documentation'
  },
  {
    id: 'integration-hub',
    name: 'Integration Hub',
    description: 'Central hub for workflow orchestration, API federation, and AI service mesh.',
    icon: 'Cog6ToothIcon',
    color: 'from-lime-500 to-green-600',
    endpoint: '/api/integration',
    enabled: true,
    category: 'integration'
  }
]

const iconMap = {
  DocumentMagnifyingGlassIcon,
  ExclamationTriangleIcon,
  DocumentTextIcon,
  ChartBarIcon,
  CpuChipIcon,
  ShieldCheckIcon,
  ServerStackIcon,
  ChatBubbleLeftRightIcon,
  WrenchScrewdriverIcon,
  UserGroupIcon,
  Cog6ToothIcon
}

export function Services() {
  const { isAuthenticated, isAdmin } = useAuth()
  const filteredServices = services.filter(service => service.enabled || isAdmin)

  return (
    <section id="services" className="py-12 sm:py-16 lg:py-24 bg-gray-50 dark:bg-gray-900">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-2xl sm:text-3xl lg:text-4xl font-bold tracking-tight text-gray-900 dark:text-white">
            Unified AI Offerings and Services
          </h2>
          <p className="mt-3 sm:mt-4 text-base sm:text-lg leading-7 sm:leading-8 text-gray-600 dark:text-gray-300">
            Enterprise-ready suite integrating AI, automation, and analytics for seamless IT and business operations.
          </p>
        </div>

        {/* Service Grid */}
        <div className="mx-auto mt-8 sm:mt-12 lg:mt-16 xl:mt-20 grid max-w-2xl grid-cols-1 gap-4 sm:gap-6 lg:mx-0 lg:max-w-none lg:grid-cols-2 xl:grid-cols-3">
          {filteredServices.map((service) => {
            const IconComponent = iconMap[service.icon as keyof typeof iconMap]
            return (
              <Card key={service.id} className="group hover:shadow-lg transition-all duration-300 relative overflow-hidden">
                <div className={`absolute top-0 left-0 w-full h-1 bg-gradient-to-r ${service.color}`} />
                <CardHeader className="pb-3 sm:pb-4">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:space-x-3">
                    <div className={`p-2 rounded-lg bg-gradient-to-r ${service.color} bg-opacity-10 w-fit`}>
                      <IconComponent className="h-6 w-6 text-gray-700 dark:text-gray-300" />
                    </div>
                    <div className="flex flex-col sm:flex-row sm:items-center sm:space-x-2">
                      <CardTitle className="text-lg sm:text-xl">{service.name}</CardTitle>
                      {!service.enabled && (
                        <span className="text-xs bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200 px-2 py-1 rounded-full">
                          Coming Soon
                        </span>
                      )}
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="pb-6">
                  <CardDescription className="text-sm sm:text-base mb-6">{service.description}</CardDescription>
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
                    <span className="text-sm text-gray-500 dark:text-gray-400 capitalize">{service.category}</span>
                    {isAuthenticated && service.enabled ? (
                      <Button asChild variant="outline" size="sm" className="w-full sm:w-auto">
                        <Link href={`/services/${service.id}`}>Launch</Link>
                      </Button>
                    ) : (
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={!service.enabled}
                        className="w-full sm:w-auto"
                      >
                        {!isAuthenticated ? <Link href="/auth/signin">Sign In</Link> : 'Coming Soon'}
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>

        {/* Dashboard Link */}
        {isAuthenticated && (
          <div className="mt-8 sm:mt-12 text-center">
            <Button asChild size="lg" className="w-full sm:w-auto">
              <Link href="/dashboard">View All Services in Dashboard</Link>
            </Button>
          </div>
        )}
      </div>
    </section>
  )
}
