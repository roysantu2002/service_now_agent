'use client'
//create-incident-form.tsx

import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { ArrowLeftIcon } from '@heroicons/react/24/outline'

interface CreateIncidentFormProps {
  onBack: () => void
  onSubmit: (data: {
    short_description: string
    description: string
    work_notes?: string
  }) => void
  isLoading: boolean
}

export function CreateIncidentForm({ onBack, onSubmit, isLoading }: CreateIncidentFormProps) {
  const [formData, setFormData] = useState({
    short_description: '',
    description: '',
    work_notes: ''
  })

  const [errors, setErrors] = useState<Record<string, string>>({})

  const validateForm = () => {
    const newErrors: Record<string, string> = {}
    
    if (!formData.short_description.trim()) {
      newErrors.short_description = 'Short description is required'
    }
    
    if (!formData.description.trim()) {
      newErrors.description = 'Description is required'
    }
    
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    
    if (validateForm()) {
      onSubmit({
        short_description: formData.short_description.trim(),
        description: formData.description.trim(),
        work_notes: formData.work_notes.trim() || undefined
      })
    }
  }

  const handleInputChange = (field: string, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }))
    
    // Clear error when user starts typing
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: '' }))
    }
  }

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center space-x-4 mb-4">
          <Button variant="outline" size="sm" onClick={onBack}>
            <ArrowLeftIcon className="h-4 w-4 mr-2" />
            Back to Incidents
          </Button>
        </div>
        
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          Create New Incident
        </h1>
        <p className="mt-2 text-gray-600 dark:text-gray-400">
          Fill in the incident details to create a new ServiceNow incident
        </p>
      </div>

      {/* Form */}
      <Card>
        <CardHeader>
          <CardTitle>Incident Information</CardTitle>
          <CardDescription>
            Provide detailed information about the incident
          </CardDescription>
        </CardHeader>
        
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Short Description */}
            <div>
              <label 
                htmlFor="short_description" 
                className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
              >
                Short Description *
              </label>
              <input
                id="short_description"
                type="text"
                value={formData.short_description}
                onChange={(e) => handleInputChange('short_description', e.target.value)}
                className={`w-full px-3 py-2 border rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                  errors.short_description 
                    ? 'border-red-300 dark:border-red-600' 
                    : 'border-gray-300 dark:border-gray-600'
                }`}
                placeholder="Brief summary of the incident"
                maxLength={160}
              />
              {errors.short_description && (
                <p className="mt-1 text-sm text-red-600 dark:text-red-400">
                  {errors.short_description}
                </p>
              )}
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                {formData.short_description.length}/160 characters
              </p>
            </div>

            {/* Description */}
            <div>
              <label 
                htmlFor="description" 
                className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
              >
                Description *
              </label>
              <textarea
                id="description"
                rows={6}
                value={formData.description}
                onChange={(e) => handleInputChange('description', e.target.value)}
                className={`w-full px-3 py-2 border rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-vertical ${
                  errors.description 
                    ? 'border-red-300 dark:border-red-600' 
                    : 'border-gray-300 dark:border-gray-600'
                }`}
                placeholder="Detailed description of the incident, including symptoms, impact, and any troubleshooting steps already taken"
              />
              {errors.description && (
                <p className="mt-1 text-sm text-red-600 dark:text-red-400">
                  {errors.description}
                </p>
              )}
            </div>

            {/* Work Notes */}
            <div>
              <label 
                htmlFor="work_notes" 
                className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
              >
                Work Notes
              </label>
              <textarea
                id="work_notes"
                rows={4}
                value={formData.work_notes}
                onChange={(e) => handleInputChange('work_notes', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-vertical"
                placeholder="Additional notes, comments, or initial investigation details (optional)"
              />
            </div>

            {/* Form Actions */}
            <div className="flex items-center justify-end space-x-4 pt-6 border-t border-gray-200 dark:border-gray-700">
              <Button 
                type="button" 
                variant="outline" 
                onClick={onBack}
                disabled={isLoading}
              >
                Cancel
              </Button>
              <Button 
                type="submit" 
                disabled={isLoading || !formData.short_description.trim() || !formData.description.trim()}
              >
                {isLoading ? 'Creating...' : 'Create Incident'}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Help Text */}
      <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
        <h3 className="text-sm font-medium text-blue-900 dark:text-blue-200 mb-2">
          Tips for Creating Effective Incidents
        </h3>
        <ul className="text-sm text-blue-800 dark:text-blue-300 space-y-1">
          <li>• Use clear, descriptive titles that summarize the problem</li>
          <li>• Include specific error messages, symptoms, and impact details</li>
          <li>• Mention affected systems, users, or business processes</li>
          <li>• Document any troubleshooting steps already attempted</li>
          <li>• Include relevant timestamps and frequency of the issue</li>
        </ul>
      </div>
    </div>
  )
}