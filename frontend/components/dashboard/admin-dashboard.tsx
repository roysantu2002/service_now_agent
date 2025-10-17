'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import {
  Card,
  CardHeader,
  CardContent,
  CardTitle,
} from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { ExclamationTriangleIcon, ClockIcon, CheckCircleIcon, ChartBarIcon, CpuChipIcon, UsersIcon } from '@heroicons/react/24/outline'
import { DashboardStats, Service } from '@/types'
import { services as serviceRoutes } from '@/app/services/routes'

/* -----------------------------
   Mock Data
----------------------------- */
const mockStats: DashboardStats = {
  totalIncidents: 1247,
  activeIncidents: 23,
  resolvedIncidents: 1224,
  criticalIncidents: 3,
  averageResolutionTime: 4.2,
  userActivity: 89,
}

const recentIncidents = [
  { id: 'INC0001234', title: 'Database Connection Issue', priority: 'High', status: 'In Progress', time: '2h ago' },
  { id: 'INC0001235', title: 'Login Service Down', priority: 'Critical', status: 'Open', time: '1h ago' },
  { id: 'INC0001236', title: 'Email Delivery Delay', priority: 'Medium', status: 'Resolved', time: '30m ago' },
  { id: 'INC0001237', title: 'API Rate Limit Exceeded', priority: 'Low', status: 'In Progress', time: '15m ago' },
]

/* -----------------------------
   Admin Dashboard
----------------------------- */
export function AdminDashboard() {
  const [stats, setStats] = useState<DashboardStats>(mockStats)
  const [loading, setLoading] = useState(true)
  const router = useRouter()

  useEffect(() => {
    const timer = setTimeout(() => setLoading(false), 1000)
    return () => clearTimeout(timer)
  }, [])

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 animate-pulse space-y-6">
        <div className="h-8 bg-gray-200 rounded w-1/4"></div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-32 bg-gray-200 rounded-lg"></div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header */}
      <header>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Admin Dashboard</h1>
        <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">
          Centralized view of AI systems, incidents, and performance metrics.
        </p>
      </header>

      {/* Stats */}
      <section className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 sm:gap-6">
        <StatCard title="Total Incidents" value={stats.totalIncidents.toLocaleString()} icon={<ExclamationTriangleIcon className="h-6 w-6 text-orange-500" />} />
        <StatCard title="Active Incidents" value={stats.activeIncidents} icon={<ClockIcon className="h-6 w-6 text-blue-500" />} />
        <StatCard title="Resolved" value={stats.resolvedIncidents.toLocaleString()} icon={<CheckCircleIcon className="h-6 w-6 text-green-500" />} />
        <StatCard title="User Activity" value={`${stats.userActivity}%`} icon={<UsersIcon className="h-6 w-6 text-purple-500" />} />
      </section>

      {/* Incidents */}
      <section className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <Card>
          <CardHeader className="flex items-center justify-between">
            <CardTitle>Recent Incidents</CardTitle>
            <Button variant="outline" size="sm">View All</Button>
          </CardHeader>
          <CardContent className="space-y-3">
            {recentIncidents.map((incident) => (
              <IncidentItem key={incident.id} incident={incident} />
            ))}
          </CardContent>
        </Card>

        {/* Services */}
        <Card>
          <CardHeader>
            <CardTitle>Services Overview</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {serviceRoutes.map((service) => (
              <ServiceItem key={service.id} service={service} />
            ))}
          </CardContent>
        </Card>
      </section>

      {/* Quick Actions */}
      <section>
        <Card>
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
            {serviceRoutes
              .filter((s) => s.enabled)
              .map((service) => (
                <Button
                  key={service.id}
                  variant="outline"
                  className="h-16 sm:h-20 flex flex-col items-center justify-center space-y-1 sm:space-y-2 p-2 text-xs sm:text-sm"
                  onClick={() => router.push(service.endpoint)}
                >
                  <span className="text-center">{service.name}</span>
                </Button>
              ))}
          </CardContent>
        </Card>
      </section>
    </div>
  )
}

/* -----------------------------
   Subcomponents
----------------------------- */
function StatCard({ title, value, icon }: { title: string; value: string | number; icon: React.ReactNode }) {
  return (
    <Card>
      <CardContent className="p-4 sm:p-6 flex items-center">
        <div className="flex-shrink-0">{icon}</div>
        <div className="ml-4 min-w-0 flex-1">
          <p className="text-xs sm:text-sm font-medium text-gray-500 dark:text-gray-400 truncate">{title}</p>
          <p className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-white">{value}</p>
        </div>
      </CardContent>
    </Card>
  )
}

function IncidentItem({ incident }: { incident: { id: string; title: string; priority: string; status: string; time: string } }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between p-3 sm:p-4 bg-gray-50 dark:bg-gray-800 rounded-lg space-y-2 sm:space-y-0">
      <div className="flex-1 min-w-0">
        <p className="font-medium text-gray-900 dark:text-white text-sm sm:text-base break-words">{incident.title}</p>
        <p className="text-xs sm:text-sm text-gray-500 dark:text-gray-400">{incident.id} • {incident.time}</p>
      </div>
      <div className="flex items-center gap-2 flex-wrap">
        <Badge color={priorityColor(incident.priority)}>{incident.priority}</Badge>
        <Badge color={statusColor(incident.status)}>{incident.status}</Badge>
      </div>
    </div>
  )
}

function ServiceItem({ service }: { service: Service }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between p-3 sm:p-4 bg-gray-50 dark:bg-gray-800 rounded-lg space-y-2 sm:space-y-0">
      <div className="flex items-center space-x-3 flex-1 min-w-0">
        <div className={`h-3 w-3 rounded-full flex-shrink-0 ${service.enabled ? 'bg-green-500' : 'bg-gray-400'}`}></div>
        <span className="font-medium text-gray-900 dark:text-white text-sm sm:text-base truncate">{service.name}</span>
      </div>
      <div className="text-xs sm:text-sm text-gray-500 dark:text-gray-400">{service.category}</div>
    </div>
  )
}

/* -----------------------------
   Helpers
----------------------------- */
function Badge({ children, color }: { children: React.ReactNode; color: string }) {
  return <span className={`px-2 py-1 text-xs rounded-full ${color}`}>{children}</span>
}

function priorityColor(priority: string) {
  switch (priority) {
    case 'Critical': return 'bg-red-100 text-red-800'
    case 'High': return 'bg-orange-100 text-orange-800'
    case 'Medium': return 'bg-yellow-100 text-yellow-800'
    default: return 'bg-green-100 text-green-800'
  }
}

function statusColor(status: string) {
  switch (status) {
    case 'Open': return 'bg-red-100 text-red-800'
    case 'In Progress': return 'bg-blue-100 text-blue-800'
    default: return 'bg-green-100 text-green-800'
  }
}
