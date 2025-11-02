'use client'

import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { DataTable } from '@/components/ui/data-table'
import { AnalysisModal } from '@/components/eus/analysis-modal'
import { CreateIncidentModal } from '@/components/eus/create-incident-modal'
import { incidentService } from '@/lib/services/incident-service'
import type { Incident, IncidentAnalysis } from '@/types/index'

export function EUSMain() {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null)
  const [analysis, setAnalysis] = useState<IncidentAnalysis | null>(null)
  const [showAnalysis, setShowAnalysis] = useState(false)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetchIncidents()
  }, [])

  const fetchIncidents = async () => {
    try {
      setLoading(true)
      const response = await incidentService.listWebhookIncidents({ page: 1, page_size: 10 })
      setIncidents(response.data || [])
    } catch (error) {
      console.error('Failed to fetch webhook incidents:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleOpenAnalysis = async (incident: Incident) => {
    try {
      setSelectedIncident(incident)
      setShowAnalysis(true)
      setAnalysis(null)

      const res = await incidentService.getWebhookAnalysisByIncidentId(incident.incident_id)
      if (res?.data?.length) {
        setAnalysis(res.data[0])
      }
    } catch (error) {
      console.error('Error fetching specific analysis:', error)
    }
  }

  const handleDelete = async (id: string) => {
    console.warn(`Delete not implemented for webhook incident ID: ${id}`)
  }

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '-'
    return new Date(dateStr).toLocaleDateString('en-GB', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    })
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex items-center justify-between">
          <CardTitle>ServiceNow Webhook Incidents</CardTitle>
          <Button onClick={() => setShowCreateModal(true)}>Create New</Button>
        </CardHeader>

        <CardContent>
          {loading ? (
            <div className="text-center py-4 text-sm text-muted-foreground">
              Loading incidents...
            </div>
          ) : (
            <DataTable
              data={incidents}
              columns={[
                { header: 'Incident ID', accessorKey: 'incident_id' },
                { header: 'Sys ID', accessorKey: 'sys_id' },
                { header: 'Action', accessorKey: 'action_type' },
                { header: 'Status', accessorKey: 'status' },
                { header: 'AI Processed', accessorKey: 'ai_processed' },
                {
                  header: 'Created At',
                  accessorKey: 'created_at',
                  cell: ({ row }) => formatDate(row.original.created_at),
                },
                {
                  header: 'Actions',
                  cell: ({ row }) => (
                    <div className="flex gap-2">
                      <Button size="sm" onClick={() => handleOpenAnalysis(row.original)}>
                        View Analysis
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleDelete(row.original.id!)}
                      >
                        Delete
                      </Button>
                    </div>
                  ),
                },
              ]}
            />
          )}
        </CardContent>
      </Card>

      {showAnalysis && selectedIncident && (
        <AnalysisModal
          open={showAnalysis}
          incident={selectedIncident}
          analysis={analysis}
          onClose={() => {
            setShowAnalysis(false)
            setSelectedIncident(null)
            setAnalysis(null)
          }}
        />
      )}

      {showCreateModal && (
        <CreateIncidentModal onClose={() => setShowCreateModal(false)} onCreated={fetchIncidents} />
      )}
    </div>
  )
}
