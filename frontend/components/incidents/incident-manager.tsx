'use client'

import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/hooks/use-auth'
import { incidentService } from '@/lib/services/incident-service'
import { IncidentDetails } from './incident-details'
import { CreateIncidentForm } from './create-incident-form'
import { 
  ExclamationTriangleIcon,
  PlusIcon,
  MagnifyingGlassIcon,
  FunnelIcon
} from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'

interface Incident {
  sys_id: string
  number: string
  short_description: string
  description: string
  state: string
  priority: string
  severity: string
  category: string
  assigned_to?: string
  created_at: string
  updated_at: string
}

// Mock incidents data - replace with real API call
const mockIncidents: Incident[] = [
  {
    sys_id: 'inc001',
    number: 'INC0001234',
    short_description: 'Database Connection Issue',
    description: 'Users unable to access application due to database connectivity issues',
    state: 'In Progress',
    priority: 'High',
    severity: '2 - High',
    category: 'Infrastructure',
    assigned_to: 'John Doe',
    created_at: '2025-10-16T14:30:00Z',
    updated_at: '2025-10-16T16:15:00Z'
  },
  {
    sys_id: 'inc002',
    number: 'INC0001235',
    short_description: 'Login Service Down',
    description: 'Authentication service experiencing high error rates',
    state: 'Open',
    priority: 'Critical',
    severity: '1 - Critical',
    category: 'Application',
    assigned_to: 'Jane Smith',
    created_at: '2025-10-16T15:45:00Z',
    updated_at: '2025-10-16T15:45:00Z'
  },
  {
    sys_id: 'inc003',
    number: 'INC0001236',
    short_description: 'Email Delivery Delay',
    description: 'Email notifications experiencing delivery delays',
    state: 'Resolved',
    priority: 'Medium',
    severity: '3 - Medium',
    category: 'Communication',
    assigned_to: 'Mike Johnson',
    created_at: '2025-10-16T10:20:00Z',
    updated_at: '2025-10-16T17:30:00Z'
  }
]

export function IncidentManager() {
  const { isAdmin } = useAuth()
  const [selectedIncident, setSelectedIncident] = useState<string | null>(null)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [priorityFilter, setPriorityFilter] = useState<string>('all')
  const queryClient = useQueryClient()

  // Mock query - replace with real API call
  const { data: incidents = mockIncidents, isLoading, error } = useQuery({
    queryKey: ['incidents', { search: searchTerm, status: statusFilter, priority: priorityFilter }],
    queryFn: () => {
      // Simulate API call
      return new Promise<Incident[]>((resolve) => {
        setTimeout(() => {
          let filtered = mockIncidents
          
          if (searchTerm) {
            filtered = filtered.filter(incident => 
              incident.short_description.toLowerCase().includes(searchTerm.toLowerCase()) ||
              incident.number.toLowerCase().includes(searchTerm.toLowerCase())
            )
          }
          
          if (statusFilter !== 'all') {
            filtered = filtered.filter(incident => incident.state === statusFilter)
          }
          
          if (priorityFilter !== 'all') {
            filtered = filtered.filter(incident => incident.priority === priorityFilter)
          }
          
          resolve(filtered)
        }, 500)
      })
    },
    staleTime: 30000, // 30 seconds
  })

  const createIncidentMutation = useMutation({
    mutationFn: (data: { short_description: string; description: string; work_notes?: string }) =>
      incidentService.createIncident(data),
    onSuccess: () => {
      toast.success('Incident created successfully')
      queryClient.invalidateQueries({ queryKey: ['incidents'] })
      setShowCreateForm(false)
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to create incident')
    },
  })

  const filteredIncidents = incidents || []

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

  if (selectedIncident) {
    return (
      <IncidentDetails
        incidentId={selectedIncident}
        onBack={() => setSelectedIncident(null)}
      />
    )
  }

  if (showCreateForm) {
    return (
      <CreateIncidentForm
        onBack={() => setShowCreateForm(false)}
        onSubmit={(data) => createIncidentMutation.mutate(data)}
        isLoading={createIncidentMutation.isPending}
      />
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-6 sm:mb-8">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white">
              Incident Management
            </h1>
            <p className="mt-1 sm:mt-2 text-sm sm:text-base text-gray-600 dark:text-gray-400">
              Manage and analyze incidents with AI-powered insights
            </p>
          </div>
          {isAdmin && (
            <Button onClick={() => setShowCreateForm(true)} className="w-full sm:w-auto">
              <PlusIcon className="h-4 w-4 mr-2" />
              Create Incident
            </Button>
          )}
        </div>
      </div>

      {/* Filters */}
      <Card className="mb-4 sm:mb-6">
        <CardContent className="p-4 sm:p-6">
          <div className="flex flex-col gap-3 sm:gap-4">
            {/* Search */}
            <div className="w-full">
              <div className="relative">
                <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search incidents..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-10 pr-4 py-2.5 sm:py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent text-base sm:text-sm"
                />
              </div>
            </div>
            
            {/* Filter Row */}
            <div className="flex flex-col sm:flex-row gap-3 sm:gap-4">
              {/* Status Filter */}
              <div className="flex-1 sm:max-w-xs">
                <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1 sm:hidden">Status</label>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="w-full px-3 py-2.5 sm:py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent text-base sm:text-sm"
                >
                  <option value="all">All Status</option>
                  <option value="Open">Open</option>
                  <option value="In Progress">In Progress</option>
                  <option value="Resolved">Resolved</option>
                  <option value="Closed">Closed</option>
                </select>
              </div>
              
              {/* Priority Filter */}
              <div className="flex-1 sm:max-w-xs">
                <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1 sm:hidden">Priority</label>
                <select
                  value={priorityFilter}
                  onChange={(e) => setPriorityFilter(e.target.value)}
                  className="w-full px-3 py-2.5 sm:py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent text-base sm:text-sm"
                >
                  <option value="all">All Priority</option>
                  <option value="Critical">Critical</option>
                  <option value="High">High</option>
                  <option value="Medium">Medium</option>
                  <option value="Low">Low</option>
                </select>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Incidents List */}
      {isLoading ? (
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <Card key={i} className="animate-pulse">
              <CardContent className="p-6">
                <div className="h-4 bg-gray-200 rounded w-1/4 mb-2"></div>
                <div className="h-6 bg-gray-200 rounded w-3/4 mb-4"></div>
                <div className="flex space-x-2">
                  <div className="h-6 bg-gray-200 rounded w-16"></div>
                  <div className="h-6 bg-gray-200 rounded w-20"></div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : error ? (
        <Card>
          <CardContent className="p-6 text-center">
            <ExclamationTriangleIcon className="h-12 w-12 text-red-500 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
              Error Loading Incidents
            </h3>
            <p className="text-gray-600 dark:text-gray-400">
              There was an error loading incidents. Please try again.
            </p>
          </CardContent>
        </Card>
      ) : filteredIncidents.length === 0 ? (
        <Card>
          <CardContent className="p-6 text-center">
            <ExclamationTriangleIcon className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
              No Incidents Found
            </h3>
            <p className="text-gray-600 dark:text-gray-400">
              {searchTerm || statusFilter !== 'all' || priorityFilter !== 'all'
                ? 'No incidents match your filters.'
                : 'No incidents have been created yet.'}
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3 sm:space-y-4">
          {filteredIncidents.map((incident) => (
            <Card key={incident.sys_id} className="hover:shadow-md transition-shadow cursor-pointer">
              <CardContent className="p-4 sm:p-6" onClick={() => setSelectedIncident(incident.sys_id)}>
                <div className="flex flex-col space-y-3 sm:space-y-0 sm:flex-row sm:items-start sm:justify-between">
                  <div className="flex-1 min-w-0">
                    {/* Mobile: Incident Number */}
                    <div className="flex items-center justify-between sm:justify-start mb-2">
                      <span className="text-sm font-medium text-gray-500 dark:text-gray-400">
                        {incident.number}
                      </span>
                      <div className="sm:hidden">
                        <Button variant="outline" size="sm">
                          View
                        </Button>
                      </div>
                    </div>
                    
                    {/* Title */}
                    <h3 className="text-base sm:text-lg font-semibold text-gray-900 dark:text-white mb-2 break-words">
                      {incident.short_description}
                    </h3>
                    
                    {/* Description */}
                    <p className="text-sm sm:text-base text-gray-600 dark:text-gray-400 mb-3 line-clamp-2">
                      {incident.description}
                    </p>
                    
                    {/* Badges */}
                    <div className="flex flex-wrap items-center gap-2 mb-3">
                      <span className={`px-2 py-1 text-xs rounded-full ${getPriorityColor(incident.priority)}`}>
                        {incident.priority}
                      </span>
                      <span className={`px-2 py-1 text-xs rounded-full ${getStatusColor(incident.state)}`}>
                        {incident.state}
                      </span>
                    </div>
                    
                    {/* Meta Information */}
                    <div className="flex flex-col space-y-1 sm:flex-row sm:items-center sm:space-y-0 sm:space-x-4 text-xs sm:text-sm text-gray-500 dark:text-gray-400">
                      <span className="truncate">Category: {incident.category}</span>
                      {incident.assigned_to && (
                        <span className="truncate">Assigned to: {incident.assigned_to}</span>
                      )}
                      <span>Created: {new Date(incident.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                  
                  {/* Desktop: View Button */}
                  <div className="hidden sm:block ml-4 flex-shrink-0">
                    <Button variant="outline" size="sm">
                      View Details
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}