'use client'

import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import type { Incident } from '@/types/index'

interface PayloadModalProps {
  open: boolean
  incident: Incident
  onClose: () => void
}

export function PayloadModal({ open, incident, onClose }: PayloadModalProps) {
  const formattedPayload = JSON.stringify(incident.payload, null, 2)

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <DialogTitle>
            Payload for Incident {incident.incident_id}
          </DialogTitle>
        </DialogHeader>

        <div className="bg-muted rounded-md p-4 overflow-auto max-h-[70vh]">
          <pre className="text-sm whitespace-pre-wrap">{formattedPayload}</pre>
        </div>

        <div className="flex justify-end mt-4">
          <Button onClick={onClose}>Close</Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
