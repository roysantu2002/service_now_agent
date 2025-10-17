'use client'

import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { 
  ArrowLeftIcon,
  DocumentCheckIcon,
  ClockIcon
} from '@heroicons/react/24/outline'

interface IncidentReviewProps {
  onBack: () => void
}

export function IncidentReview({ onBack }: IncidentReviewProps) {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-6">
        <Button 
          variant="outline" 
          onClick={onBack}
          className="mb-4"
        >
          <ArrowLeftIcon className="h-4 w-4 mr-2" />
          Back to Services
        </Button>
        
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white">
            Incident Review
          </h1>
          <p className="mt-1 sm:mt-2 text-sm sm:text-base text-gray-600 dark:text-gray-400">
            Review and assess incident details and progress
          </p>
        </div>
      </div>

      {/* Coming Soon Card */}
      <Card className="max-w-2xl mx-auto">
        <CardHeader className="text-center">
          <div className="mx-auto w-12 h-12 bg-orange-100 dark:bg-orange-900/20 rounded-lg flex items-center justify-center mb-4">
            <DocumentCheckIcon className="h-6 w-6 text-orange-600 dark:text-orange-400" />
          </div>
          <CardTitle className="text-xl">Incident Review</CardTitle>
          <CardDescription>
            This feature is coming soon! You'll be able to review incident details, 
            assess progress, and track resolution status.
          </CardDescription>
        </CardHeader>
        <CardContent className="text-center">
          <div className="space-y-4">
            <div className="flex items-center justify-center space-x-2 text-sm text-gray-500 dark:text-gray-400">
              <ClockIcon className="h-4 w-4" />
              <span>Feature in development</span>
            </div>
            <Button onClick={onBack} variant="outline">
              Back to Services
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}