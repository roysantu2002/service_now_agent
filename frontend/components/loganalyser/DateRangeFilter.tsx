"use client"

import { useState, useEffect } from "react"

export interface DateRangeFilterProps {
  onFilterChange: (value: { start_date?: string; end_date?: string; time_period?: number }) => void
  start_date?: string
  end_date?: string
  time_period?: number
}

export default function DateRangeFilter({ onFilterChange, start_date, end_date, time_period }: DateRangeFilterProps) {
  const [startDate, setStartDate] = useState(start_date || "")
  const [endDate, setEndDate] = useState(end_date || "")
  const [period, setPeriod] = useState(time_period || 0)

  useEffect(() => {
    if (start_date) setStartDate(start_date)
    if (end_date) setEndDate(end_date)
    if (time_period !== undefined) setPeriod(time_period)
  }, [start_date, end_date, time_period])

  const handleChange = () => {
    onFilterChange({
      start_date: startDate || undefined,
      end_date: endDate || undefined,
      time_period: period || undefined,
    })
  }

  const quickSelect = (hours: number) => {
    if (!endDate) return
    const end = new Date(endDate)
    const start = new Date(end.getTime() - hours * 60 * 60 * 1000)
    setStartDate(start.toISOString().slice(0, 16))
    setPeriod(hours)
    onFilterChange({
      start_date: start.toISOString().slice(0, 16),
      end_date: endDate,
      time_period: hours,
    })
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Start Date</label>
          <input
            type="datetime-local"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            onBlur={handleChange}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-emerald-500 focus:border-transparent text-gray-200"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">End Date</label>
          <input
            type="datetime-local"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            onBlur={handleChange}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-emerald-500 focus:border-transparent  text-gray-200"
          />
        </div>
      </div>

      <div className="flex gap-2 flex-wrap">
        <button
          onClick={() => quickSelect(6)}
          className="px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded-md text-sm font-medium text-gray-700 transition-colors"
        >
          Last 6h
        </button>
        <button
          onClick={() => quickSelect(12)}
          className="px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded-md text-sm font-medium text-gray-700 transition-colors"
        >
          Last 12h
        </button>
        <button
          onClick={() => quickSelect(24)}
          className="px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded-md text-sm font-medium text-gray-700 transition-colors"
        >
          Last 24h
        </button>
        <button
          onClick={() => quickSelect(36)}
          className="px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded-md text-sm font-medium text-gray-700 transition-colors"
        >
          Last 36h
        </button>
      </div>
    </div>
  )
}
