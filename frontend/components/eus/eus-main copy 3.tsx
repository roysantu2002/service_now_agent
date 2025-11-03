'use client'

import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { DataTable } from '@/components/ui/data-table'
import { AnalysisModal } from '@/components/eus/analysis-modal'
import { CreateIncidentModal } from '@/components/eus/create-incident-modal'
import { PayloadModal } from '@/components/eus/payload-modal'
import { UpdateIncidentModal } from '@/components/eus/update-incident-modal'
import { incidentService } from '@/lib/services/incident-service'
import type { Incident, IncidentAnalysis } from '@/types'
import { Loader2 } from 'lucide-react'

export function EUSMain() {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null)
  const [selectedSysId, setSelectedSysId] = useState<string | null>(null)

  const [analysis, setAnalysis] = useState<IncidentAnalysis | null>(null)

  const [showAnalysis, setShowAnalysis] = useState(false)
  const [showPayload, setShowPayload] = useState(false)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showUpdateModal, setShowUpdateModal] = useState(false)

  const [loading, setLoading] = useState(false)
  const [analysisLoading, setAnalysisLoading] = useState(false)

  useEffect(() => {
    fetchIncidents()
  }, [])

  // 🔹 Fetch all webhook incidents
  const fetchIncidents = async () => {
    try {
      setLoading(true)
      const res = await incidentService.listWebhookIncidents({ page: 1, page_size: 10 })
      setIncidents(res?.data || [])
    } catch (error) {
      console.error('Error fetching incidents:', error)
    } finally {
      setLoading(false)
    }
  }

  // 🔹 Open analysis modal
  const handleOpenAnalysis = async (incident: Incident) => {
    try {
      setSelectedIncident(incident)
      setShowAnalysis(true)
      setAnalysis(null)
      setAnalysisLoading(true)

      const res = await incidentService.getWebhookAnalysisByIncidentId(incident.incident_id)
      if (res?.data?.length) setAnalysis(res.data[0])
    } catch (error) {
      console.error('Error fetching analysis:', error)
    } finally {
      setAnalysisLoading(false)
    }
  }

  // 🔹 View payload modal
  const handleViewPayload = (incident: Incident) => {
    setSelectedIncident(incident)
    setShowPayload(true)
  }

// 🔹 Open ServiceNow “Update Fields” modal
const handleOpenUpdate = (incident: Incident) => {
  setSelectedSysId(incident.sys_id ?? null)
  setShowUpdateModal(true)
}

  // 🔹 Reprocess / trigger webhook again
  const handleReprocessIncident = async (incident: Incident) => {
    try {
      setLoading(true)
      await incidentService.updateWebhookIncident(incident.incident_id, incident.payload)
      await fetchIncidents()
    } catch (error) {
      console.error('Error reprocessing incident:', error)
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
          <CardTitle className="text-lg font-semibold">ServiceNow Webhook Incidents</CardTitle>
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
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" onClick={() => handleOpenAnalysis(row.original)}>
                        Analysis
                      </Button>
                      <Button size="sm" variant="secondary" onClick={() => handleViewPayload(row.original)}>
                        Payload
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => handleOpenUpdate(row.original)}>
                        Update Fields
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => handleReprocessIncident(row.original)}>
                        Reprocess
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
          loading={analysisLoading}
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

      {/* 🔹 Update Fields Modal */}
      {showUpdateModal && selectedSysId && (
        <UpdateIncidentModal
          open={showUpdateModal}
          sysId={selectedSysId}
          onClose={() => {
            setShowUpdateModal(false)
            setSelectedSysId(null)
          }}
          onUpdated={fetchIncidents}
        />
      )}
    </div>
  )
}
