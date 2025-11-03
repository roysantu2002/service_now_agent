'use client'

import { useState, useEffect } from 'react'
import { Loader2 } from 'lucide-react'
import { incidentService } from '@/lib/services/incident-service'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import incidentConfig from '@/config/incident-config.json'

interface UpdateIncidentModalProps {
  open: boolean
  sysId: string
  onClose: () => void
  onUpdated: () => void
}

type IncidentForm = {
  short_description: string
  category: string
  assignment_group: string
  assigned_to: string
  work_notes: string
  urgency: string
  impact: string
}

export function UpdateIncidentModal({
  open,
  sysId,
  onClose,
  onUpdated,
}: UpdateIncidentModalProps) {
  const [form, setForm] = useState<IncidentForm>({
    short_description: '',
    category: '',
    assignment_group: '',
    assigned_to: '',
    work_notes: '',
    urgency: '',
    impact: '',
  })

  const [loading, setLoading] = useState(false)
  const [fetching, setFetching] = useState(false)
  const [fetchError, setFetchError] = useState<string | null>(null)

  const [options, setOptions] = useState({
    categories: [] as string[],
    assignment_groups: [] as string[],
    assignees: [] as string[],
    urgencies: [] as string[],
    impacts: [] as string[],
  })

  // Load static dropdown options
  useEffect(() => {
    setOptions(incidentConfig)
  }, [])

  // Fetch data when modal opens
  useEffect(() => {
    if (!open || !sysId) return
    fetchIncidentDetails()
  }, [open, sysId])

  const fetchIncidentDetails = async () => {
  try {
    setFetching(true)
    setFetchError(null)

    const res = await fetch(`http://localhost:8000/api/v1/incidents/${sysId}/summary`, {
      headers: { accept: 'application/json' },
    })

    const text = await res.text()

    // try parsing JSON (even for error responses)
    let json: any
    try {
      json = JSON.parse(text)
    } catch {
      json = { detail: text }
    }

    if (!res.ok) {
      // handle “not found” and other backend messages cleanly
      const message =
        json?.detail || `Failed with status ${res.status}: ${res.statusText}`
      throw new Error(message)
    }

    const data = json
    const details =
      data?.additional_fields?.additional_fields ||
      data?.additional_fields ||
      data ||
      {}

    setForm({
      short_description: details.short_description || '',
      category: details.category || '',
      assignment_group: details.assignment_group || '',
      assigned_to: details.assigned_to || '',
      work_notes: details.work_notes || '',
      urgency: details.urgency || '',
      impact: details.impact || '',
    })
  } catch (err: any) {
    console.error('Error fetching incident details:', err)
    setFetchError(err.message || 'Failed to load incident details')
  } finally {
    setFetching(false)
  }
}

  const handleChange = (field: keyof IncidentForm, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  const handleSubmit = async () => {
    try {
      setLoading(true)
      await incidentService.updateServiceNowIncident(sysId, form)
      onUpdated()
      onClose()
    } catch (err) {
      console.error('Failed to update incident:', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Update ServiceNow Incident</DialogTitle>
        </DialogHeader>

        {fetching ? (
          <div className="flex justify-center items-center py-6 text-muted-foreground text-sm">
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            Loading incident details...
          </div>
        ) : fetchError ? (
          <div className="p-4 text-sm text-red-500 bg-red-50 rounded-md">
            ⚠️ Failed to load incident: {fetchError}
          </div>
        ) : (
          <div className="space-y-4 py-2">
            {/* Short Description (read-only) */}
            <div>
              <Label>Short Description</Label>
              <Input
                value={form.short_description}
                disabled
                placeholder="Short description (read-only)"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              {/* Category */}
              <div>
                <Label>Category</Label>
                <Select
                  value={form.category}
                  onValueChange={(v) => handleChange('category', v)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select category" />
                  </SelectTrigger>
                  <SelectContent>
                    {options.categories.map((c) => (
                      <SelectItem key={c} value={c}>
                        {c}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Assignment Group */}
              <div>
                <Label>Assignment Group</Label>
                <Select
                  value={form.assignment_group}
                  onValueChange={(v) => handleChange('assignment_group', v)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select group" />
                  </SelectTrigger>
                  <SelectContent>
                    {options.assignment_groups.map((g) => (
                      <SelectItem key={g} value={g}>
                        {g}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Assigned To */}
              <div>
                <Label>Assigned To</Label>
                <Select
                  value={form.assigned_to}
                  onValueChange={(v) => handleChange('assigned_to', v)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select assignee" />
                  </SelectTrigger>
                  <SelectContent>
                    {options.assignees.map((a) => (
                      <SelectItem key={a} value={a}>
                        {a}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Urgency */}
              <div>
                <Label>Urgency</Label>
                <Select
                  value={form.urgency}
                  onValueChange={(v) => handleChange('urgency', v)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select urgency" />
                  </SelectTrigger>
                  <SelectContent>
                    {options.urgencies.map((u) => (
                      <SelectItem key={u} value={u}>
                        {u}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Impact */}
              <div>
                <Label>Impact</Label>
                <Select
                  value={form.impact}
                  onValueChange={(v) => handleChange('impact', v)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select impact" />
                  </SelectTrigger>
                  <SelectContent>
                    {options.impacts.map((i) => (
                      <SelectItem key={i} value={i}>
                        {i}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Work Notes */}
            <div>
              <Label>Work Notes</Label>
              <Input
                value={form.work_notes}
                onChange={(e) => handleChange('work_notes', e.target.value)}
                placeholder="Enter work notes"
              />
            </div>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={loading || fetching}>
            {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Update
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
