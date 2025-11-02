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
  if (!incident) return null

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl p-6">
        <DialogHeader>
          <DialogTitle>Incident Analysis – {incident.incident_id}</DialogTitle>
          <DialogDescription>
            {incident.short_description || 'No description available.'}
          </DialogDescription>
        </DialogHeader>

        <Separator className="my-3" />

        <ScrollArea className="max-h-[60vh] pr-3 space-y-4">
          {loading ? (
            // ✅ Spinner during load
            <div className="flex items-center justify-center py-10 text-muted-foreground">
              <Loader2 className="mr-2 h-5 w-5 animate-spin" />
              Loading analysis...
            </div>
          ) : analysis ? (
            // ✅ Render analysis content when ready
            <>
              <div className="text-sm">
                <strong>Category:</strong> {analysis.category || 'N/A'} <br />
                <strong>Severity:</strong> {analysis.severity || 'N/A'} <br />
                <strong>Confidence:</strong> {analysis.confidence || '-'}
              </div>

              <div className="text-sm leading-relaxed border rounded-md p-3 bg-muted/30">
                <strong>Reasoning:</strong> <br /> {analysis.reasoning || 'No reasoning provided.'}
              </div>

              {analysis.recommended_actions && (
                <div className="text-sm border rounded-md p-3 bg-muted/20">
                  <strong>Recommended Actions:</strong>
                  <ul className="list-disc pl-5 mt-1">
                    {Array.isArray(analysis.recommended_actions)
                      ? analysis.recommended_actions.map((a: string, i: number) => (
                          <li key={i}>{a}</li>
                        ))
                      : (() => {
                          try {
                            const parsed = JSON.parse(analysis.recommended_actions)
                            return parsed.map((a: string, i: number) => <li key={i}>{a}</li>)
                          } catch {
                            return <li>{analysis.recommended_actions}</li>
                          }
                        })()}
                  </ul>
                </div>
              )}
            </>
          ) : (
            // ✅ No analysis data yet
            <p className="italic text-muted-foreground text-sm text-center py-10">
              No AI analysis data available for this incident yet.
            </p>
          )}
        </ScrollArea>
      </DialogContent>
    </Dialog>
  )
}
