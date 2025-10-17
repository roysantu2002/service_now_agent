'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/hooks/use-auth'
import { Navigation } from '@/components/layout/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Footer } from '@/components/layout/footer'
import { 
  ExclamationTriangleIcon,
  CpuChipIcon,
  DocumentTextIcon,
  ChartBarIcon
} from '@heroicons/react/24/outline'
import Link from 'next/link'

const services = [
  {
    id: 'incident',
    name: 'Incident Management',
    description: 'AI-powered incident processing and analysis with ServiceNow integration',
    longDescription: 'Comprehensive incident management system that leverages artificial intelligence to analyze, categorize, and provide insights for faster resolution. Integrates seamlessly with ServiceNow to streamline your workflow.',
    icon: ExclamationTriangleIcon,
    color: 'from-red-500 to-pink-600',
    features: [
      'AI-powered incident analysis',
      'ServiceNow integration',
      'Automated categorization',
      'Resolution recommendations',
      'Compliance filtering',
      'Historical pattern analysis'
    ],
    href: '/incidents'
  },
  {
    id: 'rag',
    name: 'RAG System',
    description: 'Retrieval-Augmented Generation for intelligent document processing',
    longDescription: 'Advanced RAG system that combines retrieval and generation capabilities to provide intelligent answers from your knowledge base and documents.',
    icon: DocumentTextIcon,
    color: 'from-green-500 to-emerald-600',
    features: [
      'Document ingestion',
      'Semantic search',
      'Context-aware responses',
      'Multi-format support',
      'Knowledge extraction',
      'Citation tracking'
    ],
    href: '/services/rag'
  },
  {
    id: 'log-analyzer',
    name: 'Log Analyzer',
    description: 'Advanced log analysis and pattern recognition',
    longDescription: 'Intelligent log analysis system that identifies patterns, anomalies, and potential issues in your system logs using machine learning algorithms.',
    icon: DocumentTextIcon,
    color: 'from-blue-500 to-cyan-600',
    features: [
      'Real-time log monitoring',
      'Anomaly detection',
      'Pattern recognition',
      'Custom alerts',
      'Trend analysis',
      'Integration APIs'
    ],
    href: '/services/log-analyzer'
  },
  {
    id: 'analytics',
    name: 'Analytics Dashboard',
    description: 'Comprehensive analytics and reporting platform',
    longDescription: 'Advanced analytics platform providing real-time insights, predictive analytics, and comprehensive reporting for data-driven decision making.',
    icon: ChartBarIcon,
    color: 'from-purple-500 to-violet-600',
    features: [
      'Real-time dashboards',
      'Predictive analytics',
      'Custom reports',
      'Data visualization',
      'Performance metrics',
      'Export capabilities'
    ],
    href: '/services/analytics'
  }
]

export default function ServicesPage() {
  const { isAuthenticated, isLoading } = useAuth()
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
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* Header */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
              AI Services
            </h1>
            <p className="mt-2 text-gray-600 dark:text-gray-400">
              Comprehensive suite of AI-powered tools for enterprise operations
            </p>
          </div>

          {/* Services Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {services.map((service) => {
              const IconComponent = service.icon
              
              return (
                <Card key={service.id} className="group hover:shadow-lg transition-all duration-300">
                  <CardHeader>
                    <div className="flex items-center space-x-3 mb-4">
                      <div className={`p-3 rounded-lg bg-gradient-to-r ${service.color} bg-opacity-10`}>
                        <IconComponent className="h-8 w-8 text-gray-700 dark:text-gray-300" />
                      </div>
                      <div>
                        <CardTitle className="text-xl">{service.name}</CardTitle>
                        <CardDescription className="text-base">
                          {service.description}
                        </CardDescription>
                      </div>
                    </div>
                  </CardHeader>
                  
                  <CardContent>
                    <div className="space-y-4">
                      <p className="text-gray-600 dark:text-gray-400">
                        {service.longDescription}
                      </p>
                      
                      <div>
                        <h4 className="font-medium text-gray-900 dark:text-white mb-2">
                          Key Features
                        </h4>
                        <ul className="grid grid-cols-1 sm:grid-cols-2 gap-1 text-sm text-gray-600 dark:text-gray-400">
                          {service.features.map((feature, index) => (
                            <li key={index} className="flex items-center space-x-2">
                              <span className="text-green-500">•</span>
                              <span>{feature}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                      
                      <div className="flex items-center justify-between pt-4 border-t border-gray-200 dark:border-gray-700">
                        <span className="text-sm text-gray-500 dark:text-gray-400">
                          Enterprise Ready
                        </span>
                        <Button asChild>
                          <Link href={service.href}>
                            Launch Service
                          </Link>
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )
            })}
          </div>

          {/* Coming Soon Section */}
          <div className="mt-12">
            <h2 className="text-2xl font-semibold text-gray-900 dark:text-white mb-6">
              Coming Soon
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
              <Card className="opacity-75">
                <CardContent className="p-6 text-center">
                  <CpuChipIcon className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <h3 className="font-medium text-gray-900 dark:text-white mb-2">
                    ML Insights
                  </h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    Advanced machine learning models for predictive analytics
                  </p>
                  <div className="mt-4">
                    <span className="px-3 py-1 text-xs bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200 rounded-full">
                      Q1 2026
                    </span>
                  </div>
                </CardContent>
              </Card>
              
              <Card className="opacity-75">
                <CardContent className="p-6 text-center">
                  <ExclamationTriangleIcon className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <h3 className="font-medium text-gray-900 dark:text-white mb-2">
                    Compliance Monitor
                  </h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    Automated compliance checking and validation
                  </p>
                  <div className="mt-4">
                    <span className="px-3 py-1 text-xs bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200 rounded-full">
                      Q2 2026
                    </span>
                  </div>
                </CardContent>
              </Card>
              
              <Card className="opacity-75">
                <CardContent className="p-6 text-center">
                  <ChartBarIcon className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <h3 className="font-medium text-gray-900 dark:text-white mb-2">
                    Custom Workflows
                  </h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    Build custom AI workflows for specific use cases
                  </p>
                  <div className="mt-4">
                    <span className="px-3 py-1 text-xs bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200 rounded-full">
                      Q3 2026
                    </span>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  )
}