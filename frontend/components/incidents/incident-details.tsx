'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { incidentService } from '@/lib/services/incident-service'
import { useAuth } from '@/hooks/use-auth'
import { 
  ArrowLeftIcon,
  ExclamationTriangleIcon,
  CpuChipIcon,
  DocumentTextIcon,
  ShieldCheckIcon,
  ClockIcon,
  UserIcon
} from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'

interface IncidentDetailsProps {
  incidentId: string
  onBack: () => void
}

export function IncidentDetails({ incidentId, onBack }: IncidentDetailsProps) {
  const { isAdmin } = useAuth()
  const [activeTab, setActiveTab] = useState('details')
  const [isProcessing, setIsProcessing] = useState(false)
  const queryClient = useQueryClient()

  // Fetch incident details
  const { data: incident, isLoading: detailsLoading } = useQuery({
    queryKey: ['incident-details', incidentId],
    queryFn: () => incidentService.getIncidentDetails(incidentId),
    enabled: !!incidentId,
  })

  // Fetch incident summary
  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ['incident-summary', incidentId],
    queryFn: () => incidentService.getIncidentSummary(incidentId),
    enabled: !!incidentId,
  })

  // Fetch incident history
  const { data: history, isLoading: historyLoading } = useQuery({
    queryKey: ['incident-history', incidentId],
    queryFn: () => incidentService.getIncidentHistory(incidentId),
    enabled: !!incidentId && activeTab === 'history',
  })

  // AI Analysis mutation
  const analyzeIncidentMutation = useMutation({
    mutationFn: (analysisType: string) => incidentService.analyzeIncident(incidentId, analysisType),
    onSuccess: () => {
      toast.success('AI analysis completed')
      queryClient.invalidateQueries({ queryKey: ['incident-summary', incidentId] })
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Analysis failed')
    },
  })

  // Process incident mutation
  const processIncidentMutation = useMutation({
    mutationFn: () => incidentService.processIncident(incidentId),
    onSuccess: () => {
      toast.success('Incident processed successfully')
      queryClient.invalidateQueries({ queryKey: ['incident-details', incidentId] })
      queryClient.invalidateQueries({ queryKey: ['incident-summary', incidentId] })
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Processing failed')
    },
  })

  const tabs = [
    { id: 'details', name: 'Details', icon: DocumentTextIcon },
    { id: 'analysis', name: 'AI Analysis', icon: CpuChipIcon },
    { id: 'compliance', name: 'Compliance', icon: ShieldCheckIcon },
    { id: 'history', name: 'History', icon: ClockIcon },
  ]

  if (detailsLoading || summaryLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="animate-pulse space-y-6">
          <div className="h-8 bg-gray-200 rounded w-1/4"></div>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-6">
              <div className="h-64 bg-gray-200 rounded-lg"></div>
            </div>
            <div className="space-y-6">
              <div className="h-32 bg-gray-200 rounded-lg"></div>
              <div className="h-48 bg-gray-200 rounded-lg"></div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  const incidentData = incident?.incident || {
    sys_id: incidentId,
    number: 'INC0001234',
    short_description: 'Sample incident for demo',
    description: 'This is a sample incident for demonstration purposes.',
    state: 'Open',
    priority: 'High',
    severity: '2 - High',
    category: 'Infrastructure',
    assigned_to: 'Demo User',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  }

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'Critical': return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
      case 'High': return 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200'
      case 'Medium': return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
      case 'Low': return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
      default: return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200'
    }
  }

  const getStatusColor = (state: string) => {
    switch (state) {
      case 'Open': return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
      case 'In Progress': return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
      case 'Resolved': return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
      case 'Closed': return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200'
      default: return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200'
    }
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center space-x-4 mb-4">
          <Button variant="outline" size="sm" onClick={onBack}>
            <ArrowLeftIcon className="h-4 w-4 mr-2" />
            Back to Incidents
          </Button>
        </div>
        
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center space-x-3 mb-2">
              <span className="text-sm font-medium text-gray-500 dark:text-gray-400">
                {incidentData.number}
              </span>
              <span className={`px-2 py-1 text-xs rounded-full ${getPriorityColor(incidentData.priority)}`}>
                {incidentData.priority}
              </span>
              <span className={`px-2 py-1 text-xs rounded-full ${getStatusColor(incidentData.state)}`}>
                {incidentData.state}
              </span>
            </div>
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
              {incidentData.short_description}
            </h1>
          </div>
          
          <div className="flex items-center space-x-2">
            <Button 
              onClick={() => processIncidentMutation.mutate()}
              disabled={processIncidentMutation.isPending}
            >
              <CpuChipIcon className="h-4 w-4 mr-2" />
              {processIncidentMutation.isPending ? 'Processing...' : 'AI Process'}
            </Button>
            
            <Button 
              variant="outline"
              onClick={() => analyzeIncidentMutation.mutate('general')}
              disabled={analyzeIncidentMutation.isPending}
            >
              {analyzeIncidentMutation.isPending ? 'Analyzing...' : 'Analyze'}
            </Button>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="mb-6">
        <div className="border-b border-gray-200 dark:border-gray-700">
          <nav className="-mb-px flex space-x-8">
            {tabs.map((tab) => {
              const IconComponent = tab.icon
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center space-x-2 py-2 px-1 border-b-2 font-medium text-sm ${
                    activeTab === tab.id
                      ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                      : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300'
                  }`}
                >
                  <IconComponent className="h-4 w-4" />
                  <span>{tab.name}</span>
                </button>
              )
            })}
          </nav>
        </div>
      </div>

      {/* Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2">
          {activeTab === 'details' && (
            <Card>
              <CardHeader>
                <CardTitle>Incident Details</CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                <div>
                  <h4 className="font-medium text-gray-900 dark:text-white mb-2">Description</h4>
                  <p className="text-gray-600 dark:text-gray-400">
                    {incidentData.description}
                  </p>
                </div>
                
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <h4 className="font-medium text-gray-900 dark:text-white mb-2">Category</h4>
                    <p className="text-gray-600 dark:text-gray-400">{incidentData.category}</p>
                  </div>
                  <div>
                    <h4 className="font-medium text-gray-900 dark:text-white mb-2">Severity</h4>
                    <p className="text-gray-600 dark:text-gray-400">{incidentData.severity}</p>
                  </div>
                  <div>
                    <h4 className="font-medium text-gray-900 dark:text-white mb-2">Assigned To</h4>
                    <p className="text-gray-600 dark:text-gray-400">{incidentData.assigned_to || 'Unassigned'}</p>
                  </div>
                  <div>
                    <h4 className="font-medium text-gray-900 dark:text-white mb-2">Created</h4>
                    <p className="text-gray-600 dark:text-gray-400">
                      {new Date(incidentData.created_at).toLocaleString()}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {activeTab === 'analysis' && (
            <Card>
              <CardHeader>
                <CardTitle>AI Analysis</CardTitle>
                <CardDescription>
                  AI-powered insights and recommendations for this incident
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                    <h4 className="font-medium text-blue-900 dark:text-blue-200 mb-2">
                      Severity Assessment
                    </h4>
                    <p className="text-blue-800 dark:text-blue-300 text-sm">
                      Based on the incident description and historical patterns, this appears to be a high-priority infrastructure issue requiring immediate attention.
                    </p>
                  </div>
                  
                  <div className="p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
                    <h4 className="font-medium text-green-900 dark:text-green-200 mb-2">
                      Recommended Actions
                    </h4>
                    <ul className="text-green-800 dark:text-green-300 text-sm space-y-1">
                      <li>• Check database connection pool status</li>
                      <li>• Verify network connectivity to database servers</li>
                      <li>• Review recent configuration changes</li>
                      <li>• Monitor system resources and performance metrics</li>
                    </ul>
                  </div>
                  
                  <div className="p-4 bg-orange-50 dark:bg-orange-900/20 rounded-lg">
                    <h4 className="font-medium text-orange-900 dark:text-orange-200 mb-2">
                      Similar Incidents
                    </h4>
                    <p className="text-orange-800 dark:text-orange-300 text-sm">
                      3 similar incidents found in the past 30 days with average resolution time of 2.5 hours.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {activeTab === 'compliance' && (
            <Card>
              <CardHeader>
                <CardTitle>Compliance Information</CardTitle>
                <CardDescription>
                  Data classification and compliance requirements
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
                    <span className="font-medium text-green-900 dark:text-green-200">Data Classification</span>
                    <span className="px-2 py-1 text-xs bg-green-100 dark:bg-green-800 text-green-800 dark:text-green-200 rounded">
                      Internal
                    </span>
                  </div>
                  
                  <div className="flex items-center justify-between p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                    <span className="font-medium text-blue-900 dark:text-blue-200">GDPR Compliance</span>
                    <span className="px-2 py-1 text-xs bg-blue-100 dark:bg-blue-800 text-blue-800 dark:text-blue-200 rounded">
                      Compliant
                    </span>
                  </div>
                  
                  <div className="flex items-center justify-between p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg">
                    <span className="font-medium text-yellow-900 dark:text-yellow-200">Retention Policy</span>
                    <span className="px-2 py-1 text-xs bg-yellow-100 dark:bg-yellow-800 text-yellow-800 dark:text-yellow-200 rounded">
                      7 Years
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {activeTab === 'history' && (
            <Card>
              <CardHeader>
                <CardTitle>Incident History</CardTitle>
                <CardDescription>
                  Timeline of actions and updates
                </CardDescription>
              </CardHeader>
              <CardContent>
                {historyLoading ? (
                  <div className="space-y-3">
                    {[...Array(3)].map((_, i) => (
                      <div key={i} className="animate-pulse">
                        <div className="h-4 bg-gray-200 rounded w-1/4 mb-2"></div>
                        <div className="h-6 bg-gray-200 rounded w-3/4"></div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="flex items-start space-x-3 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                      <div className="flex-shrink-0 w-2 h-2 bg-blue-500 rounded-full mt-2"></div>
                      <div className="flex-1">
                        <p className="text-sm font-medium text-gray-900 dark:text-white">
                          Incident created
                        </p>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          {new Date(incidentData.created_at).toLocaleString()}
                        </p>
                      </div>
                    </div>
                    
                    <div className="flex items-start space-x-3 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                      <div className="flex-shrink-0 w-2 h-2 bg-green-500 rounded-full mt-2"></div>
                      <div className="flex-1">
                        <p className="text-sm font-medium text-gray-900 dark:text-white">
                          Status updated to In Progress
                        </p>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          {new Date(incidentData.updated_at).toLocaleString()}
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Quick Actions */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Quick Actions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Button className="w-full" size="sm">
                <CpuChipIcon className="h-4 w-4 mr-2" />
                Get AI Insights
              </Button>
              <Button variant="outline" className="w-full" size="sm">
                <ShieldCheckIcon className="h-4 w-4 mr-2" />
                Filter Data
              </Button>
              {isAdmin && (
                <Button variant="outline" className="w-full" size="sm">
                  <UserIcon className="h-4 w-4 mr-2" />
                  Assign User
                </Button>
              )}
            </CardContent>
          </Card>

          {/* Summary */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-gray-600 dark:text-gray-400">Priority:</span>
                <span className="font-medium">{incidentData.priority}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-600 dark:text-gray-400">Status:</span>
                <span className="font-medium">{incidentData.state}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-600 dark:text-gray-400">Category:</span>
                <span className="font-medium">{incidentData.category}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-600 dark:text-gray-400">Assigned:</span>
                <span className="font-medium">{incidentData.assigned_to || 'Unassigned'}</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}