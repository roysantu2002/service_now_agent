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
  const [results, setResults] = useState<any>(null);
  const reportRef = useRef<HTMLDivElement>(null);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSelectedFiles(e.target.files);
  };

  const handleAnalyzeMultiple = async () => {
    if (!selectedFiles || selectedFiles.length === 0) {
      toast.error('Please select one or more log files');
      return;
    }

    setUploading(true);
    setProgress(0);

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
      if (!response.ok || !data.request_id)
        throw new Error(data.detail || 'Failed to queue analysis');

      const reqId = data.request_id;
      setRequestId(reqId);
      toast.success('Multi-file analysis queued successfully!');
      setUploading(false);
      setAnalyzing(true);

      const intervalId = setInterval(async () => {
        try {
          const progRes = await fetch(
            `${API_BASE_URL}/log-analyzer/analyze/multi-results/${reqId}`
          );
          const progData = await progRes.json();

          setProgress(progData.progress || 0);

          if (progData.status === 'completed') {
            clearInterval(intervalId);
            setAnalyzing(false);

            // handle nested results properly
            const parsedResults =
              progData.results && typeof progData.results === 'object'
                ? Object.entries(progData.results).reduce(
                    (acc: any, [key, val]: [string, any]) => {
                      acc[key] = val.summary
                        ? JSON.parse(val.summary.replace(/```json|```/g, '').trim())
                        : val;
                      return acc;
                    },
                    {}
                  )
                : progData.results;

            setResults(parsedResults);
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

      setTimeout(() => clearInterval(intervalId), 10 * 60 * 1000);
    } catch (err: any) {
      setUploading(false);
      setAnalyzing(false);
      toast.error(`Error starting multi-file analysis: ${err.message}`);
    }
  };

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

    // @ts-ignore - library has no types
    html2pdf().set(opt).from(element).save();
  };

  const renderReport = (data: any, filename: string) => {
    const { summary, observations, planning, events, traffic_patterns, highest_severity } =
      data;

    return (
      <div key={filename} className="border-t pt-6 space-y-4">
        <h2 className="text-2xl font-bold mb-4 text-gray-800">{filename}</h2>

        {/* Summary */}
        {summary && (
          <section>
            <h3 className="text-lg font-semibold mb-2 text-emerald-700">Summary</h3>
            <p className="text-gray-700 leading-relaxed">
              The log analysis detected <b>{summary.total_auth_failures}</b> authentication
              failures from <b>{summary.unique_ips}</b> unique IPs. There were{' '}
              <b>{summary.sessions_opened}</b> session openings and{' '}
              <b>{summary.sessions_closed}</b> closings. Additionally,{' '}
              <b>{summary.logrotate_alerts}</b> log rotation alerts were recorded.
            </p>
          </section>
        )}

        {/* Observations */}
        {observations && observations.length > 0 && (
          <section>
            <h3 className="text-lg font-semibold mb-2 text-emerald-700">Observations</h3>
            <table className="w-full text-sm border-collapse border border-gray-300">
              <thead className="bg-gray-100 text-gray-700">
                <tr>
                  <th className="border p-2">Date</th>
                  <th className="border p-2">IP</th>
                  <th className="border p-2">User</th>
                  <th className="border p-2">Auth Failures</th>
                  <th className="border p-2">FTP Connections</th>
                </tr>
              </thead>
              <tbody>
                {observations.map((obs: any, i: number) => (
                  <tr key={i} className="odd:bg-white even:bg-gray-50">
                    <td className="border p-2">{obs.date}</td>
                    <td className="border p-2">{obs.ip}</td>
                    <td className="border p-2">{obs.user || '-'}</td>
                    <td className="border p-2">{obs.auth_failures || '-'}</td>
                    <td className="border p-2">{obs.ftp_connections || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}

        {/* Events */}
        {events && (
          <section>
            <h3 className="text-lg font-semibold mb-2 text-emerald-700">Event Counts</h3>
            <ul className="list-disc ml-6 text-gray-700">
              {events.map((e: any, i: number) => (
                <li key={i}>
                  {e.event}: <b>{e.count}</b>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* Traffic Patterns */}
        {traffic_patterns?.high_auth_failure_ips?.length > 0 && (
          <section>
            <h3 className="text-lg font-semibold mb-2 text-emerald-700">Traffic Patterns</h3>
            <p className="text-gray-700 mb-2">
              The following IPs exhibited a high number of authentication failures:
            </p>
            <ul className="list-disc ml-6 text-gray-700">
              {traffic_patterns.high_auth_failure_ips.map((ip: any, i: number) => (
                <li key={i}>
                  <b>{ip.ip}</b>: {ip.failures} failures
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* Highest Severity */}
        {highest_severity && (
          <section>
            <h3 className="text-lg font-semibold mb-2 text-red-600">
              Highest Severity Indicator
            </h3>
            <p className="text-gray-700">
              The most critical IP is <b>{highest_severity.ip}</b> with{' '}
              <b>{highest_severity.failures}</b> failures, associated with user{' '}
              <b>{highest_severity.user}</b>.
            </p>
          </section>
        )}

        {/* Recommendations */}
        {planning?.recommendations?.length > 0 && (
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
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 space-y-6">
        {/* Header */}
        <div className="bg-gradient-to-r from-gray-900 to-gray-700 text-white rounded-lg p-6">
          <h1 className="text-3xl font-bold mb-2 flex items-center gap-2">
            <Files className="w-6 h-6" /> Multi Log Analyzer
          </h1>
          <p className="text-gray-200">
            Upload multiple log files for comprehensive, document-style analysis.
          </p>
        </div>

        {/* File Upload */}
        <div className="bg-white p-6 border rounded-lg shadow-sm space-y-4">
          <label className="font-semibold text-gray-700 flex items-center gap-2">
            <FileText className="w-5 h-5" />
            Select log files:
          </label>
          <input
            type="file"
            multiple
            accept=".log,.txt"
            onChange={handleFileSelect}
            className="border p-2 rounded-lg text-gray-800"
          />
          {selectedFiles && (
            <div className="text-sm text-gray-600">
              {Array.from(selectedFiles).map((f) => (
                <div key={f.name}>📄 {f.name}</div>
              ))}
            </div>
          )}
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
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-emerald-600 h-2 rounded-full transition-all duration-500"
                style={{ width: `${progress}%` }}
              ></div>
            </div>
          )}
        </div>

        {/* Report Display */}
        {results && (
          <div className="bg-white p-8 border rounded-lg shadow space-y-6" ref={reportRef}>
            <h2 className="text-2xl font-bold flex items-center gap-2">
              <MessageSquare className="w-6 h-6 text-emerald-600" />
              Log Analysis Report
            </h2>
            {Object.entries(results).map(([filename, data]: [string, any]) =>
              renderReport(data, filename)
            )}
          </div>
        )}

        {/* PDF Download Button */}
        {results && (
          <div className="flex justify-end">
            <button
              onClick={handleDownloadPDF}
              className="flex items-center gap-2 px-5 py-3 bg-gray-800 text-white rounded-lg font-semibold hover:bg-gray-900"
            >
              <Download className="w-5 h-5" /> Download PDF
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
