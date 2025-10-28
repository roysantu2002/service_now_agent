'use client';

import React, { useState } from 'react';
import { FileText, Play, Loader2, MessageSquare, Files } from 'lucide-react';
import { toast } from 'react-hot-toast';
import { API_BASE_URL } from '@/lib/api-config';

export default function LogAnalyzerPage() {
  const [selectedFiles, setSelectedFiles] = useState<FileList | null>(null);
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [requestId, setRequestId] = useState<string | null>(null);
  const [results, setResults] = useState<any>(null);

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
      if (!response.ok || !data.request_id) throw new Error(data.detail || 'Failed to queue analysis');

      const reqId = data.request_id;
      setRequestId(reqId);
      toast.success('Multi-file analysis queued successfully!');
      setUploading(false);
      setAnalyzing(true);

      // Poll progress every 2 seconds
      const intervalId = setInterval(async () => {
        try {
          const progRes = await fetch(`${API_BASE_URL}/log-analyzer/analyze/multi-results/${reqId}`);
          const progData = await progRes.json();

          setProgress(progData.progress || 0);

          if (progData.status === 'completed') {
            clearInterval(intervalId);
            setAnalyzing(false);
            setResults(progData.results);
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

      // Stop polling after 10 minutes max
      setTimeout(() => clearInterval(intervalId), 10 * 60 * 1000);
    } catch (err: any) {
      setUploading(false);
      setAnalyzing(false);
      toast.error(`Error starting multi-file analysis: ${err.message}`);
    }
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
            Upload multiple log files for combined intelligent analysis.
          </p>
        </div>

        {/* File Uploader */}
        <div className="bg-white p-6 border rounded-lg shadow-sm flex flex-col space-y-4">
          <label className="font-semibold text-gray-700 flex items-center gap-2">
            <FileText className="w-5 h-5" />
            Select log files to upload:
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
            disabled={uploading || analyzing || !selectedFiles?.length}
            className="flex items-center justify-center gap-2 px-6 py-3 bg-emerald-600 text-white rounded-lg font-semibold hover:bg-emerald-700 disabled:opacity-50"
          >
            {analyzing ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                <span>Analyzing... {progress}%</span>
              </>
            ) : uploading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                <span>Uploading files...</span>
              </>
            ) : (
              <>
                <Play className="w-5 h-5" />
                <span>Start Multi-Analysis</span>
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

        {/* Results Section */}
        {results && (
          <div className="bg-white p-6 border rounded-lg shadow space-y-4">
            <h2 className="text-xl font-bold flex items-center gap-2">
              <MessageSquare className="w-5 h-5 text-emerald-600" />
              Analysis Results
            </h2>

            {Object.entries(results).map(([filename, data]: [string, any]) => {
              // 🧹 Clean up summary string if it exists
              let cleanSummary = data.summary
                ? data.summary
                    .replace(/```json|```/g, '')   // remove code fences
                    .replace(/\n+/g, ' ')          // remove newlines
                    .replace(/\s{2,}/g, ' ')       // collapse extra spaces
                    .trim()
                : null;

              return (
                <div key={filename} className="border-t pt-4">
                  <h3 className="font-semibold text-gray-800 mb-2">{filename}</h3>

                  {data.error ? (
                    <p className="text-red-600">Error: {data.error}</p>
                  ) : cleanSummary ? (
                    <pre className="bg-gray-100 text-gray-800 text-sm p-3 rounded-lg overflow-x-auto whitespace-pre-wrap">
                      {cleanSummary}
                    </pre>
                  ) : (
                    <pre className="bg-gray-100 text-gray-800 text-sm p-3 rounded-lg overflow-x-auto whitespace-pre-wrap">
                      {JSON.stringify(data, null, 2)}
                    </pre>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
