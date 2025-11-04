'use client'

import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Loader2 } from 'lucide-react'

interface AnalysisRecord {
  id: string
  sys_id: string
  issue: string
  issue_category: string
  level: string
  analyzed_at: string
  pdf_path: string | null
  json_path: string | null
  md_path: string | null
}

export function AnalysisHistory({ onBack }: { onBack: () => void }) {
  const [data, setData] = useState<AnalysisRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const res = await fetch(
          'http://localhost:8000/api/v1/incidents/resolution/analysis?limit=100&offset=0'
        )
        if (!res.ok) throw new Error('Failed to fetch history')
        const json = await res.json()
        setData(json)
      } catch (err: any) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }
    fetchHistory()
  }, [])

  if (loading) {
    return (
      <div className="flex justify-center items-center py-20">
        <Loader2 className="animate-spin h-12 w-12 text-blue-600" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="px-6 py-10">
        <p className="text-red-500 text-center">{error}</p>
        <div className="text-center mt-4">
          <Button onClick={onBack}>Back</Button>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-10">
      <div className="flex justify-between mb-6">
        <h2 className="text-2xl font-bold">Previous Incident Analysis</h2>
        <Button onClick={onBack}>Back</Button>
      </div>

      <div className="grid gap-4">
        {data.map((record) => (
          <Card key={record.id} className="border border-gray-200 hover:shadow-md">
            <CardHeader>
              <CardTitle className="text-lg">{record.issue}</CardTitle>
            </CardHeader>
            <CardContent>
              <p><strong>Sys ID:</strong> {record.sys_id}</p>
              <p><strong>Category:</strong> {record.issue_category}</p>
              <p><strong>Level:</strong> {record.level}</p>
              <p><strong>Analyzed At:</strong> {record.analyzed_at}</p>

              <div className="flex space-x-2 mt-3">
                {record.pdf_path && (
                  <a href={record.pdf_path} target="_blank" className="text-blue-600 underline">PDF</a>
                )}
                {record.json_path && (
                  <a href={record.json_path} target="_blank" className="text-blue-600 underline">JSON</a>
                )}
                {record.md_path && (
                  <a href={record.md_path} target="_blank" className="text-blue-600 underline">Markdown</a>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
