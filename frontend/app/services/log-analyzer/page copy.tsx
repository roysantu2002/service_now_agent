'use client';

import React, { useState } from 'react';
import LogFileUpload from '@/components/loganalyser/LogFileUpload';
import DateRangeFilter from '@/components/loganalyser/DateRangeFilter';
import AnalysisResults from '@/components/loganalyser/AnalysisResults';
import SearchInterface from '@/components/loganalyser/SearchInterface';
import AIAssistant from '@/components/loganalyser/AIAssistant';
import { Play, Loader2, FileText, Search, Bot, Shield } from 'lucide-react';
import { toast } from 'react-hot-toast';
import { API_BASE_URL } from '@/lib/api-config';

interface DateFilterType {
  start_date?: string;
  end_date?: string;
  time_period?: number;
}

interface UploadProgress {
  upload_id: string;
  status: string;
  progress: number;
  total_size: number;
  uploaded_size: number;
  filename: string;
  log_content?: string;
  start_date?: string;
  end_date?: string;
}

export default function LogAnalyzerPage() {
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null);
  const [dateFilter, setDateFilter] = useState<DateFilterType | null>(null);
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [analysisProgress, setAnalysisProgress] = useState<number>(0);
  const [analyzing, setAnalyzing] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'analysis' | 'search' | 'ai' | 'compliance'>('analysis');

  // --- Extract dates from log ---
  const extractLogDates = (logContent: string) => {
    const lines = logContent.split(/\r?\n/).filter(Boolean);
    if (!lines.length) return {};
    const parseDate = (line: string) => line.match(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z/)?.[0];
    return { start_date: parseDate(lines[0]), end_date: parseDate(lines[lines.length - 1]) };
  };

  // --- File upload ---
  const handleUploadComplete = (upload: UploadProgress) => {
    setUploadProgress(upload);
    if (upload.log_content) {
      const { start_date, end_date } = extractLogDates(upload.log_content);
      setDateFilter({ start_date, end_date, time_period: undefined });
    }
    toast.success(`File "${upload.filename}" uploaded successfully!`);
  };

  // --- Analysis ---
  const handleAnalyze = async () => {
    if (!uploadProgress?.upload_id) {
      toast.error('No file uploaded yet');
      return;
    }

    setAnalyzing(true);
    setAnalysisProgress(0);

    try {
      const body = {
        start_date: dateFilter?.start_date || uploadProgress.start_date,
        end_date: dateFilter?.end_date || uploadProgress.end_date,
        time_period: dateFilter?.time_period,
      };

      const response = await fetch(`${API_BASE_URL}/log-analyzer/analyze/${uploadProgress.upload_id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      const text = await response.text();
      let data: any = null;
      try { data = JSON.parse(text); } catch {}

      if (!response.ok) throw new Error(`Failed to start analysis: ${text}`);
      const newAnalysisId = data.analysis_id;
      setAnalysisId(newAnalysisId);
      toast.success('Analysis started successfully!');

      const intervalId = setInterval(async () => {
        try {
          const progRes = await fetch(`${API_BASE_URL}/log-analyzer/analyze/progress/${newAnalysisId}`);
          const progData = await progRes.json();
          setAnalysisProgress(progData.progress || 0);

          if (progData.status === 'completed') {
            setAnalyzing(false);
            toast.success('Analysis completed!');
            clearInterval(intervalId);
          } else if (progData.status === 'failed') {
            setAnalyzing(false);
            toast.error(`Analysis failed: ${progData.message}`);
            clearInterval(intervalId);
          }
        } catch (err: any) {
          setAnalyzing(false);
          toast.error(`Error fetching analysis progress: ${err.message}`);
          clearInterval(intervalId);
        }
      }, 1000);

      setTimeout(() => clearInterval(intervalId), 10 * 60 * 1000);

    } catch (err: any) {
      setAnalyzing(false);
      toast.error(`Error starting analysis: ${err.message}`);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="bg-gradient-to-r from-gray-900 to-gray-700 text-white rounded-lg p-6 mb-6">
          <h1 className="text-3xl font-bold mb-2">🏦 Log Analyzer Pro</h1>
          <p className="text-gray-200">
            Enterprise-grade log analysis with AI-powered insights and compliance protection
          </p>
        </div>

        {/* Upload + Date Filter */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
          <div className="lg:col-span-2">
            <LogFileUpload onUploadComplete={handleUploadComplete} />
          </div>
          <div>
            <DateRangeFilter
              onFilterChange={setDateFilter}
              start_date={dateFilter?.start_date}
              end_date={dateFilter?.end_date}
              time_period={dateFilter?.time_period}
              inputClassName="text-black" // <-- changed input text color
            />
          </div>
        </div>

        {/* Analyze Button */}
        {uploadProgress?.upload_id && (
          <div className="bg-white border border-gray-200 rounded-lg p-4 mb-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <FileText className="w-5 h-5 text-emerald-600" />
                <span className="font-medium text-gray-900">
                  Ready to analyze: {uploadProgress.filename}
                </span>
              </div>
              <button
                onClick={handleAnalyze}
                disabled={analyzing}
                className="flex items-center space-x-2 px-6 py-3 bg-emerald-600 text-white rounded-lg font-semibold hover:bg-emerald-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {analyzing ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>Analyzing... {analysisProgress}%</span>
                  </>
                ) : (
                  <>
                    <Play className="w-5 h-5" />
                    <span>Start Comprehensive Analysis</span>
                  </>
                )}
              </button>
            </div>

            {analyzing && (
              <div className="mt-4">
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-emerald-600 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${analysisProgress}%` }}
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* Results & Tabs */}
        {analysisId && !analyzing && (
          <div className="space-y-6">
            <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
              <div className="flex border-b border-gray-200">
                {[
                  { key: 'analysis', label: 'Analysis', icon: FileText },
                  { key: 'search', label: 'RAG Search', icon: Search },
                  { key: 'ai', label: 'AI Assistant', icon: Bot },
                  { key: 'compliance', label: 'Compliance', icon: Shield },
                ].map((tab) => (
                  <button
                    key={tab.key}
                    onClick={() => setActiveTab(tab.key as any)}
                    className={`flex items-center space-x-2 px-6 py-3 font-medium transition-colors ${
                      activeTab === tab.key
                        ? 'bg-emerald-50 text-emerald-700 border-b-2 border-emerald-600'
                        : 'text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    <tab.icon className="w-5 h-5" />
                    <span>{tab.label}</span>
                  </button>
                ))}
              </div>

              <div className="p-6">
                {activeTab === 'analysis' && <AnalysisResults analysisId={analysisId} />}
                {activeTab === 'search' && <SearchInterface analysisId={analysisId} />}
                {activeTab === 'ai' && <AIAssistant analysisId={analysisId} />}
                {activeTab === 'compliance' && (
                  <div className="text-center py-12 text-gray-500">
                    Compliance report feature - implement as needed
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
