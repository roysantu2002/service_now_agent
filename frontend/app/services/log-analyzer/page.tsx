"use client";

import React, { useState, useRef } from "react";
import {
  FileText,
  Play,
  Loader2,
  MessageSquare,
  Download,
  Files,
} from "lucide-react";
import { toast } from "react-hot-toast";
import { API_BASE_URL } from "@/lib/api-config";
import html2pdf from "html2pdf.js";

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

  // --- Helper: parse fenced JSON safely ---
  function parseFencedJson(str: any): any | null {
    if (!str) return null;
    if (typeof str !== "string") return null;
    const cleaned = str
      .replace(/^```(?:json)?\s*/, "")
      .replace(/\s*```$/, "")
      .trim();
    try {
      return JSON.parse(cleaned);
    } catch (e) {
      try {
        const replaced = cleaned.replace(/\\n/g, "").replace(/\r/g, "");
        return JSON.parse(replaced);
      } catch (e2) {
        console.warn("Failed to parse fenced JSON summary", e, e2);
        return null;
      }
    }
  }

  const handleAnalyzeMultiple = async () => {
    if (!selectedFiles || selectedFiles.length === 0) {
      toast.error("Please select one or more log files");
      return;
    }

    setUploading(true);
    setProgress(0);
    setResults(null);
    setRequestId(null);

    try {
      const formData = new FormData();
      for (let i = 0; i < selectedFiles.length; i++) {
        formData.append("files", selectedFiles[i]);
      }

      const response = await fetch(
        `${API_BASE_URL}/log-analyzer/analyze-multiple`,
        {
          method: "POST",
          body: formData,
        }
      );

      const data = await response.json();
      if (!response.ok || !data.request_id)
        throw new Error(data.detail || "Failed to queue analysis");

      const reqId = data.request_id;
      setRequestId(reqId);
      toast.success("Multi-file analysis queued successfully!");
      setUploading(false);
      setAnalyzing(true);

      const intervalId = setInterval(async () => {
        try {
          const progRes = await fetch(
            `${API_BASE_URL}/log-analyzer/analyze/multi-results/${reqId}`
          );
          const progData = await progRes.json();

          setProgress(progData.progress || 0);

          if (progData.status === "completed") {
            clearInterval(intervalId);
            setAnalyzing(false);

            const finalResults: Record<string, any> = {};

            if (progData.results && typeof progData.results === "object") {
              for (const [filename, fileObj] of Object.entries<any>(
                progData.results
              )) {
                let merged: any = {
                  summary: null,
                  observations: [],
                  planning: {},
                  events: [],
                  traffic_patterns: {},
                  highest_severity: null,
                  api_error_code_summary: fileObj.api_error_code_summary ?? {},
                  __raw: fileObj,
                };

                const parsed = parseFencedJson(fileObj.summary);

                if (parsed && typeof parsed === "object") {
                  merged.summary = parsed.summary ?? null;
                  merged.observations =
                    parsed.observations ?? fileObj.observations ?? [];
                  merged.planning = parsed.planning ?? fileObj.planning ?? {};
                  merged.events = parsed.events ?? fileObj.events ?? [];
                  merged.traffic_patterns =
                    parsed.traffic_patterns ?? fileObj.traffic_patterns ?? {};
                  merged.highest_severity =
                    parsed.highest_severity ?? fileObj.highest_severity ?? null;
                } else {
                  merged.summary =
                    typeof fileObj.summary === "object"
                      ? fileObj.summary
                      : null;
                  merged.observations = fileObj.observations ?? [];
                  merged.planning = fileObj.planning ?? {};
                  merged.events = fileObj.events ?? [];
                  merged.traffic_patterns = fileObj.traffic_patterns ?? {};
                  merged.highest_severity = fileObj.highest_severity ?? null;

                  if (!merged.summary && typeof fileObj.summary === "string") {
                    try {
                      merged.summary = JSON.parse(fileObj.summary);
                    } catch {
                      merged.summary_text = String(fileObj.summary)
                        .replace(/^```(?:json)?\s*/, "")
                        .replace(/\s*```$/, "")
                        .replace(/\n+/g, " ")
                        .trim();
                    }
                  }
                }

                if (merged.summary && typeof merged.summary === "object") {
                  const s = merged.summary;
                  s.total_sessions_opened =
                    s.total_sessions_opened ??
                    s.sessions_opened ??
                    s.total_sessions ??
                    null;
                  s.total_sessions_closed =
                    s.total_sessions_closed ?? s.sessions_closed ?? null;
                  s.total_auth_failures =
                    s.total_auth_failures ??
                    s.auth_failures ??
                    s.auth_failure_count ??
                    s.auth_failures_total ??
                    null;
                  s.unique_ips = s.unique_ips ?? s.unique_ip_count ?? null;
                }

                finalResults[filename] = merged;
              }
            }

            setResults(finalResults);
            toast.success("✅ Multi-file analysis completed!");
          } else if (progData.status === "failed") {
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

  // --- PDF Download ---
  const handleDownloadPDF = () => {
    if (!reportRef.current) return;
    const element = reportRef.current;
    const opt = {
      margin: 0.5,
      filename: `log-analysis-report-${new Date()
        .toISOString()
        .slice(0, 10)}.pdf`,
      image: { type: "jpeg" as const, quality: 0.98 },
      html2canvas: { scale: 2 },
      jsPDF: {
        unit: "in" as const,
        format: "a4",
        orientation: "portrait" as const,
      },
    };
    // @ts-ignore
    html2pdf().set(opt).from(element).save();
  };

  // --- Render Each File Report ---
  const renderReport = (data: any, filename: string) => {
    const summary = data.summary ?? null;
    const observations = data.observations ?? [];
    const planning = data.planning ?? {};
    const events = data.events ?? [];
    const traffic_patterns = data.traffic_patterns ?? {};
    const highest_severity = data.highest_severity ?? null;
    const summaryTextFallback = data.summary_text ?? null;

    const show = (v: any) =>
      v === null || v === undefined || v === "" ? "—" : v;

    return (
      <div key={filename} className="pt-8 border-t border-gray-300">
        <h2 className="text-2xl font-bold text-gray-800 mb-3">{filename}</h2>

        {/* Summary */}
        {summary ? (
          <section className="mb-5">
            <h3 className="text-lg font-semibold text-emerald-700 mb-2">
              Summary
            </h3>
            <p className="text-gray-700 leading-relaxed">
              The log analysis detected{" "}
              <b>{show(summary.total_auth_failures)}</b> authentication failures
              from <b>{show(summary.unique_ips)}</b> unique IPs. There were{" "}
              <b>{show(summary.total_sessions_opened)}</b> session openings and{" "}
              <b>{show(summary.total_sessions_closed)}</b> closings.
              Additionally, <b>{show(summary.logrotate_alerts)}</b> log rotation
              alerts were recorded.
            </p>
          </section>
        ) : summaryTextFallback ? (
          <section className="mb-5">
            <h3 className="text-lg font-semibold text-emerald-700 mb-2">
              Summary
            </h3>
            <p className="text-gray-700 leading-relaxed">
              {summaryTextFallback}
            </p>
          </section>
        ) : null}

        {/* Events */}
        {events && events.length > 0 ? (
          <section className="mb-5">
            <h3 className="text-lg font-semibold text-emerald-700 mb-2">
              Event Counts
            </h3>
            <ul className="list-disc ml-6 text-gray-700">
              {events.map((e: any, i: number) => {
                const label = e.event ?? e.type ?? `event ${i + 1}`;
                const cnt = e.count ?? null;
                const ts = e.timestamp ?? null;
                const user = e.user ?? null;
                return (
                  <li key={i}>
                    <span className="font-medium">{label}:</span>{" "}
                    {cnt !== null ? <b>{cnt}</b> : ts ? ts : "—"}
                    {user ? ` — user: ${user}` : ""}
                  </li>
                );
              })}
            </ul>
          </section>
        ) : null}

        {/* Traffic Patterns */}
        {traffic_patterns && Object.keys(traffic_patterns).length > 0 && (
          <section className="mb-5">
            <h3 className="text-lg font-semibold text-emerald-700 mb-2">
              Traffic Patterns
            </h3>
            <pre className="bg-gray-50 p-3 rounded text-sm text-gray-700 overflow-x-auto">
              {JSON.stringify(traffic_patterns, null, 2)}
            </pre>
          </section>
        )}

        {/* ✅ NEW: API Error Code Summary */}
        {data.api_error_code_summary &&
          Object.keys(data.api_error_code_summary).length > 0 && (
            <section className="mb-5">
              <h3 className="text-lg font-semibold text-emerald-700 mb-2">
                API Error Code Summary
              </h3>
              {(() => {
                const summary = data.api_error_code_summary as Record<
                  string,
                  number
                >;

                const group4xx = Object.entries(summary)
                  .filter(([code]) => code.startsWith("4"))
                  .reduce(
                    (sum, [, count]) =>
                      sum + (typeof count === "number" ? count : 0),
                    0
                  );

                const group5xx = Object.entries(summary)
                  .filter(([code]) => code.startsWith("5"))
                  .reduce(
                    (sum, [, count]) =>
                      sum + (typeof count === "number" ? count : 0),
                    0
                  );

                return (
                  <>
                    <p className="text-gray-700 mb-2">
                      <b className="text-orange-600">Client Errors (4xx):</b>{" "}
                      {group4xx || "—"} &nbsp;&nbsp;
                      <b className="text-red-600">Server Errors (5xx):</b>{" "}
                      {group5xx || "—"}
                    </p>
                    <ul className="list-disc ml-6 text-gray-700">
                      {Object.entries(summary).map(([code, count]) => (
                        <li key={code}>
                          <span
                            className={
                              code.startsWith("5")
                                ? "text-red-600 font-medium"
                                : code.startsWith("4")
                                ? "text-orange-600 font-medium"
                                : "font-medium"
                            }
                          >
                            {code}
                          </span>
                          : {String(count)}
                        </li>
                      ))}
                    </ul>
                  </>
                );
              })()}
            </section>
          )}

        {/* Highest Severity */}
        {highest_severity ? (
          <section className="mb-5">
            <h3 className="text-lg font-semibold text-red-600 mb-2">
              Highest Severity Indicator
            </h3>
            <p className="text-gray-700">
              The most critical activity: <b>{show(highest_severity.type)}</b> —
              count: <b>{show(highest_severity.count)}</b>. IP:{" "}
              <b>{show(highest_severity.ip)}</b>. User:{" "}
              <b>{show(highest_severity.user)}</b>.
            </p>
          </section>
        ) : null}

        {/* Recommendations */}
        {planning?.recommendations && planning.recommendations.length > 0 && (
          <section className="mb-5">
            <h3 className="text-lg font-semibold text-emerald-700 mb-2">
              Recommendations
            </h3>
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
      <div className="max-w-6xl mx-auto px-4 space-y-6">
        {/* Header */}
        <div className="bg-gradient-to-r from-gray-900 to-gray-700 text-white rounded-lg p-6">
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <Files className="w-6 h-6" /> Multi Log Analyzer
          </h1>
          <p className="text-gray-300">
            Upload multiple log files for structured, document-style analysis.
          </p>
        </div>

        {/* File Upload */}
        <div className="bg-white p-6 border rounded-lg shadow-sm space-y-4">
          <label className="font-semibold text-gray-700 flex items-center gap-2">
            <FileText className="w-5 h-5" /> Select log files:
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

          <div className="flex items-center gap-3 mt-2">
            <button
              onClick={handleAnalyzeMultiple}
              disabled={uploading || analyzing}
              className="flex items-center justify-center gap-2 px-6 py-3 bg-emerald-600 text-white rounded-lg font-semibold hover:bg-emerald-700 disabled:opacity-50"
            >
              {analyzing ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />{" "}
                  <span>Analyzing... {progress}%</span>
                </>
              ) : (
                <>
                  <Play className="w-5 h-5" /> <span>Start Analysis</span>
                </>
              )}
            </button>

            {analyzing && (
              <div className="w-full max-w-md bg-gray-200 rounded-full h-2">
                <div
                  className="bg-emerald-600 h-2 rounded-full transition-all duration-500"
                  style={{ width: `${progress}%` }}
                />
              </div>
            )}
          </div>
        </div>

        {/* Report */}
        {results ? (
          <>
            <div
              className="bg-white p-8 border rounded-lg shadow space-y-6"
              ref={reportRef}
            >
              <h2 className="text-2xl font-bold flex items-center gap-2 text-gray-800">
                <MessageSquare className="w-6 h-6 text-emerald-600" /> Log
                Analysis Report
              </h2>
              {Object.entries(results).map(([filename, data]) =>
                renderReport(data, filename)
              )}
            </div>

            <div className="flex justify-end">
              <button
                onClick={handleDownloadPDF}
                className="flex items-center gap-2 px-5 py-3 bg-gray-800 text-white rounded-lg font-semibold hover:bg-gray-900"
              >
                <Download className="w-5 h-5" /> Download PDF
              </button>
            </div>
          </>
        ) : (
          <div className="text-center text-gray-500 italic">
            No report to display yet.
          </div>
        )}
      </div>
    </div>
  );
}
