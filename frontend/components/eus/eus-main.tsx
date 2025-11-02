'use client'

import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { DataTable } from '@/components/ui/data-table'
import { AnalysisModal } from '@/components/eus/analysis-modal'
import { CreateIncidentModal } from '@/components/eus/create-incident-modal'
import { PayloadModal } from '@/components/eus/payload-modal'
import { incidentService } from '@/lib/services/incident-service'
import type { Incident, IncidentAnalysis } from '@/types/index'
import { Loader2 } from 'lucide-react' // ✅ Spinner icon

export function EUSMain() {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null)
  const [analysis, setAnalysis] = useState<IncidentAnalysis | null>(null)
  const [showAnalysis, setShowAnalysis] = useState(false)
  const [showPayload, setShowPayload] = useState(false)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [loading, setLoading] = useState(false)
  const [analysisLoading, setAnalysisLoading] = useState(false) // ✅ new state

  useEffect(() => {
    fetchIncidents()
  }, [])

  // 🔹 Fetch list of webhook incidents
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

  // 🔹 Open analysis modal for an incident
  const handleOpenAnalysis = async (incident: Incident) => {
    try {
      setSelectedIncident(incident)
      setShowAnalysis(true)
      setAnalysis(null)
      setAnalysisLoading(true) // ✅ show spinner

      const res = await incidentService.getWebhookAnalysisByIncidentId(incident.incident_id)
      if (res?.data?.length) {
        setAnalysis(res.data[0])
      }
    } catch (error) {
      console.error('Error fetching specific analysis:', error)
    } finally {
      setAnalysisLoading(false) // ✅ hide spinner
    }
  }

  // 🔹 Open raw payload modal
  const handleViewPayload = (incident: Incident) => {
    setSelectedIncident(incident)
    setShowPayload(true)
  }

  // 🔹 Trigger update / reprocess for same incident
  const handleUpdateIncident = async (incident: Incident) => {
    try {
      setLoading(true)
      await incidentService.updateWebhookIncident(incident.incident_id, incident.payload)
      await fetchIncidents()
    } catch (error) {
      console.error('Failed to update incident:', error)
    } finally {
      setLoading(false)
    }
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
            <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
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
                {
                  header: 'AI Processed',
                  accessorKey: 'ai_processed',
                  cell: ({ row }) => (row.original.ai_processed ? '✅' : '❌'),
                },
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
                      <Button size="sm" variant="secondary" onClick={() => handleViewPayload(row.original)}>
                        View Payload
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleUpdateIncident(row.original)}
                      >
                        Update
                      </Button>
                    </div>
                  ),
                },
              ]}
            />
          )}
        </CardContent>
      </Card>

      {/* 🔹 Analysis Modal */}
      {showAnalysis && selectedIncident && (
        <AnalysisModal
          open={showAnalysis}
          incident={selectedIncident}
          analysis={analysis}
          loading={analysisLoading} // ✅ pass loading to modal
          onClose={() => {
            setShowAnalysis(false)
            setSelectedIncident(null)
            setAnalysis(null)
          }}
        />
      )}

      {/* 🔹 Payload Modal */}
      {showPayload && selectedIncident && (
        <PayloadModal
          open={showPayload}
          incident={selectedIncident}
          onClose={() => {
            setShowPayload(false)
            setSelectedIncident(null)
          }}
        />
      )}

      {/* 🔹 Create Incident Modal */}
      {showCreateModal && (
        <CreateIncidentModal
          onClose={() => setShowCreateModal(false)}
          onCreated={fetchIncidents}
        />
      )}
    </div>
  )
}
