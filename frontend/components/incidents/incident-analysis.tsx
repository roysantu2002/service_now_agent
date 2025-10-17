'use client'

//incident-analysis.tsx

import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { 
  ArrowLeftIcon,
  MagnifyingGlassIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ClockIcon,
  DocumentArrowDownIcon,
  CpuChipIcon
} from '@heroicons/react/24/outline'
import { incidentService } from '@/lib/services/incident-service'
import toast from 'react-hot-toast'

interface AnalysisResult {
  success: boolean
  sys_id: string
  analysis_type: string
  ai_model: string
  usage: {
    prompt_tokens: number
    completion_tokens: number
    total_tokens: number
  }
  data: {
    id: string
    issue: string
    issue_category: string
    description: string
    steps_to_resolve: string[]
    technical_details: string
    complete_description: string
  }
  pdf_path: string
  raw_ai_output_path: string
  parsing_error: string | null
  validation_error: string | null
}

interface IncidentAnalysisProps {
  onBack: () => void
}

export function IncidentAnalysis({ onBack }: IncidentAnalysisProps) {
  const [sysId, setSysId] = useState('')
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null)

  const analysisMutation = useMutation({
    mutationFn: (sys_id: string) => incidentService.analyzeIncident(sys_id, 'general'),
    onSuccess: (data: AnalysisResult) => {
      setAnalysisResult(data)
      toast.success('Analysis completed successfully')
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to analyze incident')
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!sysId.trim()) {
      toast.error('Please enter a valid sys_id')
      return
    }
    analysisMutation.mutate(sysId.trim())
  }

  const handleReset = () => {
    setSysId('')
    setAnalysisResult(null)
    analysisMutation.reset()
  }

  const formatDate = (timestamp: string) => {
    return new Date(timestamp).toLocaleString()
  }

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
        
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white">
              Incident Analysis
            </h1>
            <p className="mt-1 sm:mt-2 text-sm sm:text-base text-gray-600 dark:text-gray-400">
              AI-powered incident analysis with detailed resolution steps
            </p>
          </div>
          {analysisResult && (
            <Button onClick={handleReset} variant="outline">
              New Analysis
            </Button>
          )}
        </div>
      </div>

      {!analysisResult ? (
        /* Input Form */
        <Card className="max-w-2xl mx-auto">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <MagnifyingGlassIcon className="h-5 w-5" />
              <span>Start Analysis</span>
            </CardTitle>
            <CardDescription>
              Enter the system ID of the incident you want to analyze
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="sysId">System ID</Label>
                <Input
                  id="sysId"
                  type="text"
                  placeholder="e.g., bae75d10c3507210e66adaec0501313b"
                  value={sysId}
                  onChange={(e) => setSysId(e.target.value)}
                  disabled={analysisMutation.isPending}
                  className="font-mono"
                />
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Enter the unique system identifier for the incident
                </p>
              </div>
              
              <Button 
                type="submit" 
                disabled={analysisMutation.isPending || !sysId.trim()}
                className="w-full"
              >
                {analysisMutation.isPending ? (
                  <>
                    <ClockIcon className="h-4 w-4 mr-2 animate-spin" />
                    Analyzing Incident...
                  </>
                ) : (
                  <>
                    <MagnifyingGlassIcon className="h-4 w-4 mr-2" />
                    Analyze Incident
                  </>
                )}
              </Button>
            </form>
          </CardContent>
        </Card>
      ) : (
        /* Analysis Results */
        <div className="space-y-6">
          {/* Status Card */}
          <Card className={`border-2 ${
            analysisResult.success 
              ? 'border-green-200 bg-green-50 dark:bg-green-900/20 dark:border-green-800' 
              : 'border-red-200 bg-red-50 dark:bg-red-900/20 dark:border-red-800'
          }`}>
            <CardContent className="p-4">
              <div className="flex items-center space-x-3">
                {analysisResult.success ? (
                  <CheckCircleIcon className="h-6 w-6 text-green-600 dark:text-green-400" />
                ) : (
                  <ExclamationTriangleIcon className="h-6 w-6 text-red-600 dark:text-red-400" />
                )}
                <div>
                  <h3 className={`font-semibold ${
                    analysisResult.success 
                      ? 'text-green-900 dark:text-green-100' 
                      : 'text-red-900 dark:text-red-100'
                  }`}>
                    Analysis {analysisResult.success ? 'Completed' : 'Failed'}
                  </h3>
                  <p className={`text-sm ${
                    analysisResult.success 
                      ? 'text-green-700 dark:text-green-200' 
                      : 'text-red-700 dark:text-red-200'
                  }`}>
                    System ID: {analysisResult.sys_id}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* AI Model Info */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <CpuChipIcon className="h-5 w-5" />
                <span>Analysis Information</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div>
                  <Label className="text-xs text-gray-500 dark:text-gray-400">AI Model</Label>
                  <p className="font-mono text-sm">{analysisResult.ai_model}</p>
                </div>
                <div>
                  <Label className="text-xs text-gray-500 dark:text-gray-400">Analysis Type</Label>
                  <p className="text-sm capitalize">{analysisResult.analysis_type}</p>
                </div>
                <div>
                  <Label className="text-xs text-gray-500 dark:text-gray-400">Total Tokens</Label>
                  <p className="text-sm">{analysisResult.usage.total_tokens.toLocaleString()}</p>
                </div>
                <div>
                  <Label className="text-xs text-gray-500 dark:text-gray-400">Completion Tokens</Label>
                  <p className="text-sm">{analysisResult.usage.completion_tokens.toLocaleString()}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Incident Overview */}
          <Card>
            <CardHeader>
              <CardTitle>Incident Overview</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label className="text-sm font-medium text-gray-700 dark:text-gray-300">Issue</Label>
                <p className="text-lg font-semibold text-gray-900 dark:text-white mt-1">
                  {analysisResult.data.issue}
                </p>
              </div>
              
              <div>
                <Label className="text-sm font-medium text-gray-700 dark:text-gray-300">Category</Label>
                <span className="inline-block mt-1 px-3 py-1 bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 rounded-full text-sm">
                  {analysisResult.data.issue_category}
                </span>
              </div>
              
              <div>
                <Label className="text-sm font-medium text-gray-700 dark:text-gray-300">Description</Label>
                <p className="text-gray-900 dark:text-white mt-1 leading-relaxed">
                  {analysisResult.data.description}
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Resolution Steps */}
          <Card>
            <CardHeader>
              <CardTitle>Resolution Steps</CardTitle>
              <CardDescription>
                Follow these AI-generated steps to resolve the incident
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {analysisResult.data.steps_to_resolve.map((step, index) => (
                  <div key={index} className="flex items-start space-x-3 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                    <div className="flex-shrink-0 w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm font-medium">
                      {index + 1}
                    </div>
                    <p className="text-gray-900 dark:text-white text-sm leading-relaxed">
                      {step}
                    </p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Technical Details */}
          <Card>
            <CardHeader>
              <CardTitle>Technical Details</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-gray-900 dark:text-white leading-relaxed">
                {analysisResult.data.technical_details}
              </p>
            </CardContent>
          </Card>

          {/* Complete Description */}
          <Card>
            <CardHeader>
              <CardTitle>Complete Analysis</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-gray-900 dark:text-white leading-relaxed">
                {analysisResult.data.complete_description}
              </p>
            </CardContent>
          </Card>

          {/* Export Options */}
          {analysisResult.pdf_path && (
            <Card>
              <CardHeader>
                <CardTitle>Export Options</CardTitle>
                <CardDescription>
                  Download the analysis results in different formats
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-col sm:flex-row gap-3">
                  <Button variant="outline" className="flex items-center space-x-2">
                    <DocumentArrowDownIcon className="h-4 w-4" />
                    <span>Download PDF Report</span>
                  </Button>
                  {analysisResult.raw_ai_output_path && (
                    <Button variant="outline" className="flex items-center space-x-2">
                      <DocumentArrowDownIcon className="h-4 w-4" />
                      <span>Download Raw Output</span>
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Error Information */}
          {(analysisResult.parsing_error || analysisResult.validation_error) && (
            <Card className="border-yellow-200 bg-yellow-50 dark:bg-yellow-900/20 dark:border-yellow-800">
              <CardHeader>
                <CardTitle className="text-yellow-800 dark:text-yellow-200">
                  Processing Warnings
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {analysisResult.parsing_error && (
                  <div>
                    <Label className="text-sm font-medium text-yellow-700 dark:text-yellow-300">
                      Parsing Error
                    </Label>
                    <p className="text-sm text-yellow-800 dark:text-yellow-200">
                      {analysisResult.parsing_error}
                    </p>
                  </div>
                )}
                {analysisResult.validation_error && (
                  <div>
                    <Label className="text-sm font-medium text-yellow-700 dark:text-yellow-300">
                      Validation Error
                    </Label>
                    <p className="text-sm text-yellow-800 dark:text-yellow-200">
                      {analysisResult.validation_error}
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}