'use client'

import { useState } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { incidentService } from '@/lib/services/incident-service'

export function CreateIncidentModal({
  onClose,
  onCreated,
}: {
  onClose: () => void
  onCreated: () => void
}) {
  const [shortDescription, setShortDescription] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async () => {
    if (!shortDescription.trim()) return
    setLoading(true)
    try {
      await incidentService.createWebhookIncident({
        short_description: shortDescription,
        created_via: 'frontend',
      })
      onCreated()
      onClose()
    } catch (error) {
      console.error('Error creating incident:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Create New Incident</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <Input
            placeholder="Short Description"
            value={shortDescription}
            onChange={(e) => setShortDescription(e.target.value)}
          />
          <Button onClick={handleSubmit} disabled={loading}>
            {loading ? 'Creating...' : 'Create Incident'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
