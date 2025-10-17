'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/hooks/use-auth'
import { 
  DocumentMagnifyingGlassIcon,
  ExclamationTriangleIcon,
  DocumentTextIcon,
  ChartBarIcon,
  ClockIcon,
  CheckCircleIcon
} from '@heroicons/react/24/outline'

const availableServices = [
  {
    id: 'incident',
    name: 'Incident Management',
    description: 'Analyze and manage incidents with AI-powered insights',
    icon: ExclamationTriangleIcon,
    color: 'from-red-500 to-pink-600',
    href: '/services/incident'
  },
  {
    id: 'rag',
    name: 'RAG System',
    description: 'Query documents and knowledge bases intelligently',
    icon: DocumentMagnifyingGlassIcon,
    color: 'from-green-500 to-emerald-600',
    href: '/services/rag'
  },
  {
    id: 'log-analyzer',
    name: 'Log Analyzer',
    description: 'Analyze system logs for patterns and anomalies',
    icon: DocumentTextIcon,
    color: 'from-blue-500 to-cyan-600',
    href: '/services/log-analyzer'
  },
  {
    id: 'analytics',
    name: 'Analytics',
    description: 'View insights and performance metrics',
    icon: ChartBarIcon,
    color: 'from-purple-500 to-violet-600',
    href: '/services/analytics'
  }
]

const recentActivity = [
  {
    id: '1',
    action: 'Analyzed incident INC0001234',
    service: 'Incident Management',
    time: '2 hours ago',
    status: 'completed'
  },
  {
    id: '2',
    action: 'Queried documentation for API errors',
    service: 'RAG System',
    time: '4 hours ago',
    status: 'completed'
  },
  {
    id: '3',
    action: 'Analyzed error logs from web server',
    service: 'Log Analyzer',
    time: '1 day ago',
    status: 'completed'
  }
]

export function UserDashboard() {
  const { user } = useAuth()
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    // Simulate loading
    const timer = setTimeout(() => setIsLoading(false), 800)
    return () => clearTimeout(timer)
  }, [])

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="animate-pulse space-y-6">
          <div className="h-8 bg-gray-200 rounded w-1/3"></div>
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-40 bg-gray-200 rounded-lg"></div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 sm:py-6">
      {/* Header */}
      <div className="mb-6 sm:mb-8">
        <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white">
          Welcome back, {user?.name}!
        </h1>
        <p className="mt-1 sm:mt-2 text-sm sm:text-base text-gray-600 dark:text-gray-400">
          Access AI-powered services to analyze incidents and gain insights
        </p>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 gap-4 sm:gap-6 sm:grid-cols-2 lg:grid-cols-3 mb-6 sm:mb-8">
        <Card>
          <CardContent className="p-4 sm:p-6">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <CheckCircleIcon className="h-6 w-6 sm:h-8 sm:w-8 text-green-500" />
              </div>
              <div className="ml-3 sm:ml-4 min-w-0 flex-1">
                <p className="text-xs sm:text-sm font-medium text-gray-500 dark:text-gray-400 truncate">
                  Tasks Completed
                </p>
                <p className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-white">
                  24
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 sm:p-6">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <ClockIcon className="h-6 w-6 sm:h-8 sm:w-8 text-blue-500" />
              </div>
              <div className="ml-3 sm:ml-4 min-w-0 flex-1">
                <p className="text-xs sm:text-sm font-medium text-gray-500 dark:text-gray-400 truncate">
                  Active Sessions
                </p>
                <p className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-white">
                  3
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 sm:p-6">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <ExclamationTriangleIcon className="h-6 w-6 sm:h-8 sm:w-8 text-orange-500" />
              </div>
              <div className="ml-3 sm:ml-4 min-w-0 flex-1">
                <p className="text-xs sm:text-sm font-medium text-gray-500 dark:text-gray-400 truncate">
                  Assigned Incidents
                </p>
                <p className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-white">
                  5
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Services Grid */}
      <div className="mb-6 sm:mb-8">
        <h2 className="text-lg sm:text-xl font-semibold text-gray-900 dark:text-white mb-4 sm:mb-6">
          Available Services
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {availableServices.map((service) => {
            const IconComponent = service.icon
            return (
              <Card key={service.id} className="group hover:shadow-lg transition-all duration-300 cursor-pointer">
                <CardHeader className="pb-3 sm:pb-4">
                  <div className="flex items-center space-x-3">
                    <div className={`p-2 sm:p-3 rounded-lg bg-gradient-to-r ${service.color} bg-opacity-10`}>
                      <IconComponent className="h-5 w-5 sm:h-6 sm:w-6 text-gray-700 dark:text-gray-300" />
                    </div>
                  </div>
                  <CardTitle className="text-base sm:text-lg">{service.name}</CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                  <CardDescription className="mb-3 sm:mb-4 text-sm">
                    {service.description}
                  </CardDescription>
                  <Button asChild className="w-full text-sm">
                    <Link href={service.href}>
                      Launch Service
                    </Link>
                  </Button>
                </CardContent>
              </Card>
            )
          })}
        </div>
      </div>

      {/* Recent Activity */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Activity</CardTitle>
          <CardDescription>
            Your recent interactions with AI services
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3 sm:space-y-4">
            {recentActivity.map((activity) => (
              <div key={activity.id} className="flex flex-col sm:flex-row sm:items-center sm:justify-between p-3 sm:p-4 bg-gray-50 dark:bg-gray-800 rounded-lg space-y-2 sm:space-y-0">
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-900 dark:text-white text-sm sm:text-base break-words">
                    {activity.action}
                  </p>
                  <p className="text-xs sm:text-sm text-gray-500 dark:text-gray-400">
                    {activity.service} • {activity.time}
                  </p>
                </div>
                <div className="flex items-center">
                  <span className="px-2 py-1 text-xs bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200 rounded-full">
                    {activity.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-4 sm:mt-6 text-center">
            <Button variant="outline" className="w-full sm:w-auto">
              View All Activity
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}