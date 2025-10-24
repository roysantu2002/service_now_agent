"use client"

import { useState, useEffect } from "react"
import { AlertTriangle, TrendingUp, Shield, BarChart3, Loader2 } from "lucide-react"
import { BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts"
import { API_BASE_URL } from "@/lib/api-config"

interface AnalysisResultsProps {
  analysisId: string
}

const COLORS = ["#059669", "#0891b2", "#7c3aed", "#dc2626", "#d97706"]

export default function AnalysisResults({ analysisId }: AnalysisResultsProps) {
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchResults()
  }, [analysisId])

  const fetchResults = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/log-analyzer/analyze/results/${analysisId}`)
      if (!response.ok) throw new Error("Failed to fetch results")
      const result = await response.json()
      setData(result)
      setLoading(false)
    } catch (err: any) {
      setError(err.message)
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 text-emerald-600 animate-spin" />
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <p className="text-red-900">Error: {error}</p>
      </div>
    )
  }

  const levelData = Object.entries(data.statistics?.level_distribution || {}).map(([level, count]) => ({
    level,
    count,
  }))

  const categoryData = Object.entries(data.statistics?.category_distribution || {}).map(([category, count]) => ({
    name: category,
    value: count as number,
  }))

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-gradient-to-br from-emerald-50 to-emerald-100 rounded-lg p-4 border border-emerald-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-emerald-700">Total Entries</p>
              <p className="text-2xl font-bold text-emerald-900">
                {data.summary?.total_entries?.toLocaleString() || 0}
              </p>
            </div>
            <BarChart3 className="w-8 h-8 text-emerald-600" />
          </div>
        </div>

        <div className="bg-gradient-to-br from-red-50 to-red-100 rounded-lg p-4 border border-red-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-red-700">Errors</p>
              <p className="text-2xl font-bold text-red-900">{data.summary?.error_count?.toLocaleString() || 0}</p>
              <p className="text-xs text-red-600">{data.summary?.error_rate || 0}% rate</p>
            </div>
            <AlertTriangle className="w-8 h-8 text-red-600" />
          </div>
        </div>

        <div className="bg-gradient-to-br from-orange-50 to-orange-100 rounded-lg p-4 border border-orange-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-orange-700">Critical</p>
              <p className="text-2xl font-bold text-orange-900">{data.summary?.critical_errors || 0}</p>
              <p className="text-xs text-orange-600">Avg: {data.summary?.average_severity || 0}/5</p>
            </div>
            <TrendingUp className="w-8 h-8 text-orange-600" />
          </div>
        </div>

        <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-lg p-4 border border-blue-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-blue-700">Compliance</p>
              <p className="text-lg font-bold text-blue-900">{data.summary?.compliance_status || "UNKNOWN"}</p>
              <p className="text-xs text-blue-600">Risk: {data.summary?.compliance_risk_score || 0}/100</p>
            </div>
            <Shield className="w-8 h-8 text-blue-600" />
          </div>
        </div>
      </div>

      {/* Charts */}
      {levelData.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Log Level Distribution</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={levelData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="level" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="count" fill="#059669" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {categoryData.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Error Categories</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={categoryData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={(entry) => entry.name}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
              >
                {categoryData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Top Errors */}
      {data.top_errors?.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Top Errors</h3>
          <div className="space-y-3">
            {data.top_errors.slice(0, 5).map((error: any, index: number) => (
              <div
                key={index}
                className="border border-gray-200 rounded-lg p-4 hover:border-emerald-400 transition-colors"
              >
                <div className="flex items-start justify-between mb-2">
                  <span className="text-sm font-medium text-gray-900">{error.category}</span>
                  <span className="px-2 py-1 bg-red-100 text-red-700 text-xs rounded">
                    Severity: {error.severity}/5
                  </span>
                </div>
                <p className="text-sm text-gray-700 mb-2">{error.message}</p>
                <p className="text-xs text-gray-500">Occurrences: {error.count}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
