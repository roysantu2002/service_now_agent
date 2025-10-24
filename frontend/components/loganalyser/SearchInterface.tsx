"use client"

import { useState } from "react"
import { Search, Loader2 } from "lucide-react"
import { API_BASE_URL } from "@/lib/api-config"

interface SearchInterfaceProps {
  analysisId: string
}

export default function SearchInterface({ analysisId }: SearchInterfaceProps) {
  const [query, setQuery] = useState("")
  const [searching, setSearching] = useState(false)
  const [results, setResults] = useState<any>(null)

  const handleSearch = async () => {
    if (!query.trim()) return
    setSearching(true)

    try {
      const response = await fetch(`${API_BASE_URL}/log-analyzer/search/${analysisId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          max_results: 10,
        }),
      })

      if (!response.ok) throw new Error("Search failed")
      const data = await response.json()
      setResults(data)
    } catch (err: any) {
      alert("Search failed: " + err.message)
    } finally {
      setSearching(false)
    }
  }

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-900 flex items-center space-x-2">
        <Search className="w-5 h-5 text-emerald-600" />
        <span>Search Logs</span>
      </h3>

      <div className="flex gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyPress={(e) => e.key === "Enter" && handleSearch()}
          placeholder="Search logs..."
          className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
          disabled={searching}
        />
        <button
          onClick={handleSearch}
          disabled={searching || !query.trim()}
          className="px-6 py-2 bg-emerald-600 text-white rounded-lg font-semibold hover:bg-emerald-700 disabled:opacity-50 transition-colors flex items-center space-x-2"
        >
          {searching ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Searching...</span>
            </>
          ) : (
            <>
              <Search className="w-4 h-4" />
              <span>Search</span>
            </>
          )}
        </button>
      </div>

      {results && (
        <div className="space-y-3">
          <p className="text-sm text-gray-600">Found {results.total_results} results</p>
          {results.results?.map((result: any, index: number) => (
            <div key={index} className="bg-gray-50 border border-gray-200 rounded-lg p-3">
              <p className="text-xs text-gray-500 mb-1">Line {result.line_number}</p>
              <p className="text-sm text-gray-900 font-mono">{result.message}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
