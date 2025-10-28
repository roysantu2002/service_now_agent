'use client';

import React, { useState, useRef } from 'react';
import { FileText, Play, Loader2, MessageSquare, Download, Files } from 'lucide-react';
import { toast } from 'react-hot-toast';
import { API_BASE_URL } from '@/lib/api-config';
import html2pdf from 'html2pdf.js';

export default function LogAnalyzerPage() {
  const [selectedFiles, setSelectedFiles] = useState<FileList | null>(null);
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [requestId, setRequestId] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, any> | null>(null);
  const reportRef = useRef<HTMLDivElement>(null);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSelectedFiles(e.target.files);
  };

  // Helper: if a value is a fenced JSON string like ```json\n{ ... }\n```, return parsed object; else null
  function parseFencedJson(str: any): any | null {
    if (typeof str !== 'string') return null;
    // remove fenced codeblock markers and surrounding whitespace
    const cleaned = str.replace(/^```(?:json)?\s*/, '').replace(/\s*```$/, '');
    try {
      // cleaned may contain escaped newlines; ensure we have a valid JSON string
      const parsed = JSON.parse(cleaned);
      return parsed;
    } catch (e) {
      // try to remove literal "\n" sequences and parse again
      try {
        const replaced = cleaned.replace(/\\n/g, '').replace(/\r/g, '');
        return JSON.parse(replaced);
      } catch (e2) {
        console.warn('Failed to parse fenced JSON summary', e, e2);
        return null;
      }
    }
  }

  const handleAnalyzeMultiple = async () => {
    if (!selectedFiles || selectedFiles.length === 0) {
      toast.error('Please select one or more log files');
      return;
    }

    setUploading(true);
    setProgress(0);
    setResults(null);
    setRequestId(null);

    try {
      const formData = new FormData();
      for (let i = 0; i < selectedFiles.length; i++) {
        formData.append('files', selectedFiles[i]);
      }

      const response = await fetch(`${API_BASE_URL}/log-analyzer/analyze-multiple`, {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();
      if (!response.ok || !data.request_id) throw new Error(data.detail || 'Failed to queue analysis');

      const reqId = data.request_id;
      setRequestId(reqId);
      toast.success('Multi-file analysis queued successfully!');
      setUploading(false);
      setAnalyzing(true);

      const intervalId = setInterval(async () => {
        try {
          const progRes = await fetch(`${API_BASE_URL}/log-analyzer/analyze/multi-results/${reqId}`);
          const progData = await progRes.json();

          setProgress(progData.progress || 0);

          if (progData.status === 'completed') {
            clearInterval(intervalId);
            setAnalyzing(false);

            // progData.results is an object keyed by filename
            const finalResults: Record<string, any> = {};

            if (progData.results && typeof progData.results === 'object') {
              for (const [filename, fileObj] of Object.entries<any>(progData.results)) {
                // fileObj may already contain separate keys, but fileObj.summary may be a fenced JSON string.
                let merged: any = {};

                // If summary is a fenced JSON string that itself contains keys (summary, observations, etc.)
                const parsed = parseFencedJson(fileObj.summary);
                if (parsed && typeof parsed === 'object') {
                  // parsed likely has top-level keys: summary, observations, planning, events, traffic_patterns, highest_severity
                  // prefer parsed.summary for the "summary" object, and parsed fields for observations/planning/events
                  merged.summary = parsed.summary ?? fileObj.summary;
                  merged.observations = parsed.observations ?? fileObj.observations ?? [];
                  merged.planning = parsed.planning ?? fileObj.planning ?? {};
                  merged.events = parsed.events ?? fileObj.events ?? [];
                  merged.traffic_patterns = parsed.traffic_patterns ?? fileObj.traffic_patterns ?? {};
                  merged.highest_severity = parsed.highest_severity ?? fileObj.highest_severity ?? null;
                  merged.requires_immediate_attention = parsed.requires_immediate_attention ?? fileObj.requires_immediate_attention ?? false;
                } else {
                  // Not parseable — try that fileObj.summary may itself be a plain object or a simple string
                  merged.summary = (typeof fileObj.summary === 'object') ? fileObj.summary : null;
                  merged.observations = fileObj.observations ?? [];
                  merged.planning = fileObj.planning ?? {};
                  merged.events = fileObj.events ?? [];
                  merged.traffic_patterns = fileObj.traffic_patterns ?? {};
                  merged.highest_severity = fileObj.highest_severity ?? null;
                  merged.requires_immediate_attention = fileObj.requires_immediate_attention ?? false;

                  // If merged.summary is null but fileObj contains other keys, and fileObj has nested JSON in other props, keep fileObj as fallback
                  if (!merged.summary && fileObj.summary && typeof fileObj.summary === 'string') {
                    // remove fences and collapse newlines for display as fallback text
                    merged.summary_text = String(fileObj.summary).replace(/^```(?:json)?\s*/, '').replace(/\s*```$/, '').replace(/\n+/g, ' ').trim();
                  }
                }

                finalResults[filename] = merged;
              }
            }

            setResults(finalResults);
            toast.success('✅ Multi-file analysis completed!');
          } else if (progData.status === 'failed') {
            clearInterval(intervalId);
            setAnalyzing(false);
            toast.error(`❌ Analysis failed: ${progData.message}`);
          }
        } catch (err: any) {
          clearInterval(intervalId);
          setAnalyzing(false);
          toast.error(`Error fetching progress: ${err.message}`);
        }
      }, 2000);

      // stop polling after 10 minutes
      setTimeout(() => clearInterval(intervalId), 10 * 60 * 1000);
    } catch (err: any) {
      setUploading(false);
      setAnalyzing(false);
      toast.error(`Error starting multi-file analysis: ${err.message}`);
    }
  };

  // minimal Html2Pdf options typing (html2pdf.js is JS-only)
  interface Html2PdfOptions {
    margin?: number | [number, number];
    filename?: string;
    image?: {
      type?: 'jpeg' | 'png' | 'webp';
      quality?: number;
    };
    html2canvas?: {
      scale?: number;
    };
    jsPDF?: {
      unit?: 'pt' | 'mm' | 'cm' | 'in';
      format?: string | [number, number];
      orientation?: 'portrait' | 'landscape';
    };
  }

  const handleDownloadPDF = () => {
    if (!reportRef.current) return;
    const element = reportRef.current;

    const opt: Html2PdfOptions = {
      margin: 0.6,
      filename: `log-analysis-report-${new Date().toISOString().slice(0, 10)}.pdf`,
      image: { type: 'jpeg', quality: 0.98 },
      html2canvas: { scale: 2 },
      jsPDF: { unit: 'in', format: 'a4', orientation: 'portrait' },
    };

    // html2pdf has no TS defs in many installs — ignore for runtime
    // @ts-ignore
    html2pdf().set(opt).from(element).save();
  };

  const renderReport = (data: any, filename: string) => {
    // data should have: summary (object), observations (array), planning (object), events (array), traffic_patterns (obj), highest_severity (obj)
    const summary = data.summary ?? null;
    const observations = data.observations ?? [];
    const planning = data.planning ?? {};
    const events = data.events ?? [];
    const traffic_patterns = data.traffic_patterns ?? {};
    const highest_severity = data.highest_severity ?? null;

    // fallback summary text if parsing failed and we stored summary_text
    const summaryTextFallback = data.summary_text ?? null;

    return (
      <div key={filename} className="border-t pt-6 space-y-4">
        <h2 className="text-2xl font-bold mb-2 text-gray-800">{filename}</h2>

        {/* Summary */}
        {summary ? (
          <section>
            <h3 className="text-lg font-semibold mb-2 text-emerald-700">Summary</h3>
            <p className="text-gray-700 leading-relaxed">
              The log analysis detected <b>{summary.total_auth_failures ?? '—'}</b> authentication failures
              from <b>{summary.unique_ips ?? '—'}</b> unique IPs. There were{' '}
              <b>{summary.total_sessions_opened ?? summary.sessions_opened ?? summary.sessions_opened ?? '—'}</b> session openings and{' '}
              <b>{summary.total_sessions_closed ?? summary.sessions_closed ?? '—'}</b> closings. Additionally,{' '}
              <b>{summary.logrotate_alerts ?? '—'}</b> log rotation alerts were recorded.
            </p>
          </section>
        ) : summaryTextFallback ? (
          <section>
            <h3 className="text-lg font-semibold mb-2 text-emerald-700">Summary</h3>
            <p className="text-gray-700 leading-relaxed">{summaryTextFallback}</p>
          </section>
        ) : null}

        {/* Observations */}
        {observations && observations.length > 0 && (
          <section>
            <h3 className="text-lg font-semibold mb-2 text-emerald-700">Observations</h3>
            <table className="w-full text-sm border-collapse border border-gray-300">
              <thead className="bg-gray-100 text-gray-700">
                <tr>
                  <th className="border p-2 text-left">Date</th>
                  <th className="border p-2 text-left">IP</th>
                  <th className="border p-2 text-left">User</th>
                  <th className="border p-2 text-left">Auth Failures</th>
                  <th className="border p-2 text-left">FTP Connections</th>
                </tr>
              </thead>
              <tbody>
                {observations.map((obs: any, i: number) => (
                  <tr key={i} className="odd:bg-white even:bg-gray-50">
                    <td className="border p-2">{obs.date ?? '-'}</td>
                    <td className="border p-2">{obs.ip ?? '-'}</td>
                    <td className="border p-2">{obs.user ?? '-'}</td>
                    <td className="border p-2">{obs.auth_failures ?? '-'}</td>
                    <td className="border p-2">{obs.ftp_connections ?? '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}

        {/* Events */}
        {events && events.length > 0 && (
          <section>
            <h3 className="text-lg font-semibold mb-2 text-emerald-700">Event Counts</h3>
            <ul className="list-disc ml-6 text-gray-700">
              {events.map((e: any, i: number) => (
                <li key={i}>
                  {e.event ?? e.type ?? 'event'}: <b>{e.count ?? e.timestamp ?? '—'}</b>
                  {e.user ? ` — user: ${e.user}` : ''}
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* Traffic Patterns */}
        {traffic_patterns && Object.keys(traffic_patterns).length > 0 && (
          <section>
            <h3 className="text-lg font-semibold mb-2 text-emerald-700">Traffic Patterns</h3>

            {/* If traffic_patterns has 'ssh' or 'ftp' structure */}
            {traffic_patterns.ssh && (
              <div className="mb-2">
                <p className="text-gray-700">SSH high-activity IPs:</p>
                <ul className="list-disc ml-6 text-gray-700">
                  {(traffic_patterns.ssh.high_activity_ips ?? []).map((ip: string, i: number) => (
                    <li key={i}>{ip}</li>
                  ))}
                </ul>
                <p className="text-sm text-gray-500">Total SSH connections: {traffic_patterns.ssh.total_connections ?? '—'}</p>
              </div>
            )}

            {traffic_patterns.ftp && (
              <div>
                <p className="text-gray-700">FTP high-activity IPs:</p>
                <ul className="list-disc ml-6 text-gray-700">
                  {(traffic_patterns.ftp.high_activity_ips ?? []).map((ip: string, i: number) => (
                    <li key={i}>{ip}</li>
                  ))}
                </ul>
                <p className="text-sm text-gray-500">Total FTP connections: {traffic_patterns.ftp.total_connections ?? '—'}</p>
              </div>
            )}

            {/* Generic fallback */}
            {!traffic_patterns.ssh && !traffic_patterns.ftp && (
              <pre className="bg-gray-50 p-3 rounded text-sm text-gray-700 overflow-x-auto">
                {JSON.stringify(traffic_patterns, null, 2)}
              </pre>
            )}
          </section>
        )}

        {/* Highest severity */}
        {highest_severity && (
          <section>
            <h3 className="text-lg font-semibold mb-2 text-red-600">Highest Severity Indicator</h3>
            <p className="text-gray-700">
              The most critical activity: <b>{highest_severity.type ?? '—'}</b> — count: <b>{highest_severity.count ?? '—'}</b>.
              IP: <b>{highest_severity.ip ?? '—'}</b>. User: <b>{highest_severity.user ?? '—'}</b>.
            </p>
          </section>
        )}

        {/* Recommendations */}
        {planning?.recommendations && planning.recommendations.length > 0 && (
          <section>
            <h3 className="text-lg font-semibold mb-2 text-emerald-700">Recommendations</h3>
            <ul className="list-disc ml-6 text-gray-700">
              {planning.recommendations.map((rec: string, i: number) => (
                <li key={i}>{rec}</li>
              ))}
            </ul>
          </section>
        )}
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 space-y-6">
        {/* Header */}
        <div className="bg-gradient-to-r from-gray-900 to-gray-700 text-white rounded-lg p-6">
          <h1 className="text-3xl font-bold mb-2 flex items-center gap-2">
            <Files className="w-6 h-6" /> Multi Log Analyzer
          </h1>
          <p className="text-gray-200">Upload multiple log files for comprehensive, document-style analysis.</p>
        </div>

        {/* File Upload */}
        <div className="bg-white p-6 border rounded-lg shadow-sm space-y-4">
          <label className="font-semibold text-gray-700 flex items-center gap-2">
            <FileText className="w-5 h-5" /> Select log files:
          </label>

          <input type="file" multiple accept=".log,.txt" onChange={handleFileSelect} className="border p-2 rounded-lg text-gray-800" />

          {selectedFiles && (
            <div className="text-sm text-gray-600">
              {Array.from(selectedFiles).map((f) => (
                <div key={f.name}>📄 {f.name}</div>
              ))}
            </div>
          )}

          <div className="flex items-center gap-3 mt-2">
            <button
              onClick={handleAnalyzeMultiple}
              disabled={uploading || analyzing}
              className="flex items-center justify-center gap-2 px-6 py-3 bg-emerald-600 text-white rounded-lg font-semibold hover:bg-emerald-700 disabled:opacity-50"
            >
              {analyzing ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>Analyzing... {progress}%</span>
                </>
              ) : (
                <>
                  <Play className="w-5 h-5" />
                  <span>Start Analysis</span>
                </>
              )}
            </button>

            {analyzing && (
              <div className="w-full max-w-md bg-gray-200 rounded-full h-2">
                <div className="bg-emerald-600 h-2 rounded-full transition-all duration-500" style={{ width: `${progress}%` }} />
              </div>
            )}
          </div>
        </div>

        {/* Report Display */}
        {results ? (
          <div className="bg-white p-8 border rounded-lg shadow space-y-6" ref={reportRef}>
            <h2 className="text-2xl font-bold flex items-center gap-2">
              <MessageSquare className="w-6 h-6 text-emerald-600" /> Log Analysis Report
            </h2>

            {Object.entries(results).map(([filename, data]) => renderReport(data, filename))}
          </div>
        ) : (
          <div className="text-center text-gray-500 italic">No report to display yet.</div>
        )}

        {/* PDF Download Button */}
        {results && (
          <div className="flex justify-end">
            <button onClick={handleDownloadPDF} className="flex items-center gap-2 px-5 py-3 bg-gray-800 text-white rounded-lg font-semibold hover:bg-gray-900">
              <Download className="w-5 h-5" /> Download PDF
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
