'use client'

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog'
import { Separator } from '@/components/ui/separator'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Loader2 } from 'lucide-react'
import { Incident, IncidentAnalysis } from '@/types/index'
import { useMemo } from 'react'

interface AnalysisModalProps {
  open: boolean
  incident: Incident
  analysis?: IncidentAnalysis | null
  loading?: boolean
  onClose: () => void
}

export function AnalysisModal({
  open,
  incident,
  analysis,
  loading = false,
  onClose,
}: AnalysisModalProps) {
  // ✅ Safely parse metadata (it’s a JSON string in the response)
  const parsedMetadata = useMemo(() => {
    try {
      return analysis?.metadata ? JSON.parse(analysis.metadata) : null
    } catch {
      return null
    }
  }, [analysis])

  // ✅ Utility for formatting timestamps
  const formatDateTime = (dateStr?: string) => {
    if (!dateStr) return '-'
    const d = new Date(dateStr)
    return d.toLocaleString('en-GB', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  }

  // ✅ Pretty print JSON-like strings
  const renderJSON = (value: string) => {
    try {
      const obj = JSON.parse(value)
      return (
        <pre className="text-xs bg-muted/30 p-2 rounded-md overflow-x-auto whitespace-pre-wrap">
          {JSON.stringify(obj, null, 2)}
        </pre>
      )
    } catch {
      return <span className="text-sm break-words">{value}</span>
    }
  }

  if (!incident) return null

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl p-6">
        <DialogHeader>
          <DialogTitle>Incident Analysis – {incident.incident_id}</DialogTitle>
          <DialogDescription>
            {incident.short_description || 'No description available.'}
          </DialogDescription>
        </DialogHeader>

        <Separator className="my-3" />

        <ScrollArea className="max-h-[70vh] pr-3 space-y-5">
          {loading ? (
            <div className="flex items-center justify-center py-10 text-muted-foreground">
              <Loader2 className="mr-2 h-5 w-5 animate-spin" />
              Loading analysis...
            </div>
          ) : analysis ? (
            <>
              {/* 🔹 Basic Info */}
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <strong>Incident ID:</strong> {analysis.incident_id}
                </div>
                <div>
                  <strong>Sys ID:</strong> {analysis.sys_id}
                </div>
                <div>
                  <strong>Category:</strong> {analysis.category || 'N/A'}
                </div>
                <div>
                  <strong>Severity:</strong> {analysis.severity || 'N/A'}
                </div>
                <div>
                  <strong>Confidence:</strong> {analysis.confidence || '-'}
                </div>
                <div>
                  <strong>Suggested Priority:</strong> {analysis.suggested_priority || '-'}
                </div>
                <div>
                  <strong>AI Model Used:</strong> {analysis.ai_model_used || 'Unknown'}
                </div>
                <div>
                  <strong>Analysis Level:</strong> {analysis.analysis_level || 'N/A'}
                </div>
              </div>

              {/* 🔹 Reasoning */}
              <div className="text-sm leading-relaxed border rounded-md p-3 bg-muted/30">
                <strong>Reasoning:</strong>
                <p className="mt-1 whitespace-pre-line">
                  {analysis.reasoning || 'No reasoning provided.'}
                </p>
              </div>

              {/* 🔹 Supporting Evidence */}
              {analysis.supporting_evidence && (
                <div className="text-sm border rounded-md p-3 bg-muted/20">
                  <strong>Supporting Evidence:</strong>
                  {renderJSON(analysis.supporting_evidence)}
                </div>
              )}

              {/* 🔹 Recommended Actions */}
              {analysis.recommended_actions && (
                <div className="text-sm border rounded-md p-3 bg-muted/20">
                  <strong>Recommended Actions:</strong>
                  {renderJSON(analysis.recommended_actions)}
                </div>
              )}

              {/* 🔹 Related Metadata */}
              {parsedMetadata && (
                <div className="text-sm border rounded-md p-3 bg-muted/20">
                  <strong>Metadata:</strong>
                  <pre className="text-xs bg-muted/30 p-2 rounded-md overflow-x-auto whitespace-pre-wrap">
                    {JSON.stringify(parsedMetadata, null, 2)}
                  </pre>
                </div>
              )}

              {/* 🔹 System Info */}
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <strong>Created At:</strong> {formatDateTime(analysis.created_at)}
                </div>
                <div>
                  <strong>Updated At:</strong> {formatDateTime(analysis.updated_at)}
                </div>
              </div>
            </>
          ) : (
            <p className="italic text-muted-foreground text-sm text-center py-10">
              No AI analysis data available for this incident yet.
            </p>
          )}
        </ScrollArea>
      </DialogContent>
    </Dialog>
  )
}
