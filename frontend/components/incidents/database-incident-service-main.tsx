'use client'

import { useState } from 'react'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import {
  PlusIcon,
  MagnifyingGlassIcon,
  DocumentCheckIcon,
  WrenchScrewdriverIcon,
  ClipboardDocumentListIcon,
  ExclamationTriangleIcon
} from '@heroicons/react/24/outline'

import { CreateIncidentForm } from './create-incident-form'
import { IncidentAnalysis } from './incident-analysis'
import { IncidentReview } from './incident-review'
import { IncidentRemediation } from './incident-remediation'
import { IncidentManager } from './incident-manager'
import { AnalysisHistory } from './analysis-history'

type ServiceView =
  | 'main'
  | 'create'
  | 'analyse'
  | 'review'
  | 'remediation'
  | 'list'
  | 'analysis_history'

interface ServiceOption {
  id: ServiceView
  title: string
  description: string
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>
  color: string
  bgColor: string
}

const serviceOptions: ServiceOption[] = [
  {
    id: 'create',
    title: 'Log Database Incident',
    description: 'Create and register database-related incidents such as outages, latency, or failures',
    icon: PlusIcon,
    color: 'text-blue-600',
    bgColor: 'bg-blue-50 hover:bg-blue-100 dark:bg-blue-900/20 dark:hover:bg-blue-900/30'
  },
  {
    id: 'analyse',
    title: 'Analyse Database Issue',
    description: 'AI-driven analysis to identify root cause and recommend DB-specific resolution steps',
    icon: MagnifyingGlassIcon,
    color: 'text-green-600',
    bgColor: 'bg-green-50 hover:bg-green-100 dark:bg-green-900/20 dark:hover:bg-green-900/30'
  },
  {
    id: 'review',
    title: 'Review DB Incidents',
    description: 'Review database incident details, impact, severity, and investigation progress',
    icon: DocumentCheckIcon,
    color: 'text-orange-600',
    bgColor: 'bg-orange-50 hover:bg-orange-100 dark:bg-orange-900/20 dark:hover:bg-orange-900/30'
  },
  {
    id: 'remediation',
    title: 'Database Remediation',
    description: 'Execute approved remediation steps and track database recovery and stabilization',
    icon: WrenchScrewdriverIcon,
    color: 'text-purple-600',
    bgColor: 'bg-purple-50 hover:bg-purple-100 dark:bg-purple-900/20 dark:hover:bg-purple-900/30'
  },
  {
    id: 'list',
    title: 'Manage DB Incidents',
    description: 'View, filter, and manage all active and resolved database incidents',
    icon: ClipboardDocumentListIcon,
    color: 'text-gray-600',
    bgColor: 'bg-gray-50 hover:bg-gray-100 dark:bg-gray-900/20 dark:hover:bg-gray-900/30'
  },
  {
    id: 'analysis_history',
    title: 'DB Analysis History',
    description: 'Browse previously generated AI analyses for recurring database issues',
    icon: ExclamationTriangleIcon,
    color: 'text-red-600',
    bgColor: 'bg-red-50 hover:bg-red-100 dark:bg-red-900/20 dark:hover:bg-red-900/30'
  }
]

export function DatabaseIncidentServiceMain() {
  const [currentView, setCurrentView] = useState<ServiceView>('main')

  const handleBackToMain = () => setCurrentView('main')

  // --- Render individual views ---
  switch (currentView) {
    case 'create':
      return <CreateIncidentForm onBack={handleBackToMain} onSubmit={() => {}} isLoading={false} />
    case 'analyse':
      return <IncidentAnalysis onBack={handleBackToMain} />
    case 'review':
      return <IncidentReview onBack={handleBackToMain} />
    case 'remediation':
      return <IncidentRemediation onBack={handleBackToMain} />
    case 'list':
      return <IncidentManager />
    case 'analysis_history':
      return <AnalysisHistory onBack={handleBackToMain} />
  }

  // --- Main services grid ---
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <h1 className="text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white text-center mb-6">
        Database Incident Services
      </h1>
      <p className="text-center text-gray-600 dark:text-gray-400 mb-10">
        AI-powered database incident analysis, remediation, and operational visibility
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-6">
        {serviceOptions.map((option) => {
          const IconComponent = option.icon
          return (
            <Card
              key={option.id}
              className={`cursor-pointer transform transition duration-200 hover:scale-105 hover:shadow-lg border-2 ${option.bgColor}`}
              onClick={() => setCurrentView(option.id)}
            >
              <CardHeader>
                <div className="flex items-center space-x-3">
                  <div className="p-3 bg-white dark:bg-gray-800 rounded-lg shadow-sm flex-shrink-0">
                    <IconComponent className={`h-6 w-6 ${option.color}`} />
                  </div>
                  <CardTitle className="text-lg font-semibold text-gray-900 dark:text-white">
                    {option.title}
                  </CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <CardDescription className="text-sm text-gray-600 dark:text-gray-400">
                  {option.description}
                </CardDescription>
              </CardContent>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
