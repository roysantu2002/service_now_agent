'use client'

import Link from 'next/link'

export function Footer() {
  return (
    <footer className="fixed bottom-0 left-0 w-full bg-gray-900 text-gray-300 border-t border-gray-700">
      <div className="max-w-7xl mx-auto flex flex-col sm:flex-row justify-between items-center px-6 py-3 text-sm">
        {/* Left: Info */}
        <p className="mb-2 sm:mb-0 text-center sm:text-left">
          © 2025 AI Services Platform · Internal Use Only
        </p>

        {/* Center: Quick Links */}
        <div className="flex flex-wrap justify-center gap-4">
          <Link href="/services/rag" className="hover:text-white">
            RAG System
          </Link>
          <Link href="/services/incident" className="hover:text-white">
            Incident Management
          </Link>
          <Link href="/services/log-analyzer" className="hover:text-white">
            Log Analyzer
          </Link>
          <Link href="/services/analytics" className="hover:text-white">
            Analytics
          </Link>
        </div>

        {/* Right: Status */}
        <div className="hidden sm:flex items-center gap-2">
          <span className="text-xs">Status: Operational</span>
          <span className="h-2 w-2 bg-green-500 rounded-full animate-pulse" />
        </div>
      </div>
    </footer>
  )
}
