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
  ArrowLeftIcon
} from '@heroicons/react/24/outline'
import { CreateIncidentForm } from './create-incident-form'
import { IncidentAnalysis } from './incident-analysis'
import { IncidentReview } from './incident-review'
import { IncidentRemediation } from './incident-remediation'
import { IncidentManager } from './incident-manager'

type ServiceView =
  | 'main'
  | 'create'
  | 'analyse'
  | 'review'
  | 'remediation'
  | 'list'

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
    title: 'Create Incident',
    description: 'Create and log new incidents in the system',
    icon: PlusIcon,
    color: 'text-blue-600',
    bgColor: 'bg-blue-50 hover:bg-blue-100 dark:bg-blue-900/20 dark:hover:bg-blue-900/30'
  },
  {
    id: 'analyse',
    title: 'Analyse Incident',
    description: 'AI-powered incident analysis with step-by-step resolution',
    icon: MagnifyingGlassIcon,
    color: 'text-green-600',
    bgColor: 'bg-green-50 hover:bg-green-100 dark:bg-green-900/20 dark:hover:bg-green-900/30'
  },
  {
    id: 'review',
    title: 'Review Incidents',
    description: 'Review and assess incident details and progress',
    icon: DocumentCheckIcon,
    color: 'text-orange-600',
    bgColor: 'bg-orange-50 hover:bg-orange-100 dark:bg-orange-900/20 dark:hover:bg-orange-900/30'
  },
  {
    id: 'remediation',
    title: 'Remediation',
    description: 'Execute remediation steps and track resolution progress',
    icon: WrenchScrewdriverIcon,
    color: 'text-purple-600',
    bgColor: 'bg-purple-50 hover:bg-purple-100 dark:bg-purple-900/20 dark:hover:bg-purple-900/30'
  },
  {
    id: 'list',
    title: 'Manage Incidents',
    description: 'View and manage all incidents in the system',
    icon: ClipboardDocumentListIcon,
    color: 'text-gray-600',
    bgColor: 'bg-gray-50 hover:bg-gray-100 dark:bg-gray-900/20 dark:hover:bg-gray-900/30'
  }
]
export function IncidentServiceMain() {
  const [currentView, setCurrentView] = useState<ServiceView | null>(null)

  const handleCloseView = () => setCurrentView(null)

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-10">
      <h1 className="text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white text-center mb-6">
        Incident Services
      </h1>
      <p className="text-center text-gray-600 dark:text-gray-400 mb-10">
        Select a service to get started with AI-powered incident management
      </p>

      {/* --- Service Options Grid --- */}
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
                  <CardTitle className="text-lg font-semibold text-gray-900 dark:text-white">{option.title}</CardTitle>
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

      {/* --- Conditional Detail View --- */}
      {currentView && (
        <div className="mt-10">
          <Button variant="outline" onClick={handleCloseView} className="mb-4">
            <ArrowLeftIcon className="h-4 w-4 mr-2" />
            Back to all services
          </Button>

          {currentView === 'create' && <CreateIncidentForm onBack={handleCloseView} onSubmit={() => {}} isLoading={false} />}
          {currentView === 'analyse' && <IncidentAnalysis onBack={handleCloseView} />}
          {currentView === 'review' && <IncidentReview onBack={handleCloseView} />}
          {currentView === 'remediation' && <IncidentRemediation onBack={handleCloseView} />}
          {currentView === 'list' && <IncidentManager />}
        </div>
      )}
    </div>
  )
}