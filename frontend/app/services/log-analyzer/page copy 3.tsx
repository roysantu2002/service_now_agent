'use client';

import React, { useState } from 'react';
import LogFileUpload, { UploadProgress } from '@/components/loganalyser/LogFileUpload';
import DateRangeFilter from '@/components/loganalyser/DateRangeFilter';
import { FileText, Play, Loader2, MessageSquare } from 'lucide-react';
import { toast } from 'react-hot-toast';
import { API_BASE_URL } from '@/lib/api-config';

interface DateFilterType {
  start_date?: string;
  end_date?: string;
  time_period?: number;
}

export default function LogAnalyzerPage() {
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null);
  const [dateFilter, setDateFilter] = useState<DateFilterType | null>(null);
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [analysisProgress, setAnalysisProgress] = useState<number>(0);
  const [analyzing, setAnalyzing] = useState(false);
  const [question, setQuestion] = useState<string>('');

  const handleUploadComplete = (upload: UploadProgress) => {
    setUploadProgress(upload);
    setDateFilter({
      start_date: upload.start_date,
      end_date: upload.end_date,
      time_period: undefined,
    });
    toast.success(`File "${upload.filename}" uploaded successfully!`);
  };

  const handleAnalyze = async () => {
    if (!uploadProgress?.upload_id) {
      toast.error('No uploaded file found');
      return;
    }
    if (!dateFilter?.start_date || !dateFilter?.end_date) {
      toast.error('Cannot start analysis: start_date or end_date missing');
      return;
    }
    if (!question.trim()) {
      toast.error('Please enter a question before starting analysis');
      return;
    }

    setAnalyzing(true);
    setAnalysisProgress(0);

    try {
      const response = await fetch(`${API_BASE_URL}/log-analyzer/analyze/${uploadProgress.upload_id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          start_date: dateFilter.start_date,
          end_date: dateFilter.end_date,
          time_period: dateFilter.time_period,
          question: question.trim(), // <-- send question to backend
        }),
      });

      const data = await response.json();
      if (!response.ok || !data.analysis_id) throw new Error(data.message || 'Failed to start analysis');

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
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 space-y-6">
        {/* Header */}
        <div className="bg-gradient-to-r from-gray-900 to-gray-700 text-white rounded-lg p-6">
          <h1 className="text-3xl font-bold mb-2">🏦 Log Analyzer Pro</h1>
          <p className="text-gray-200">
            Upload your logs and start comprehensive analysis
          </p>
        </div>

        {/* File Upload */}
        <LogFileUpload onUploadComplete={handleUploadComplete} />

        {/* Date Filter */}
        {uploadProgress && (
          <DateRangeFilter
            onFilterChange={setDateFilter}
            start_date={dateFilter?.start_date}
            end_date={dateFilter?.end_date}
            time_period={dateFilter?.time_period}
          />
        )}

        {/* Question Input */}
        {uploadProgress && (
          <div className="bg-white border border-gray-200 rounded-lg p-4 flex flex-col space-y-2">
            <label className="font-medium text-gray-700 flex items-center space-x-2">
              <MessageSquare className="w-4 h-4 text-gray-600" />
              <span>Enter your question for AI analysis:</span>
            </label>
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              className="border border-gray-300 rounded-lg p-2 w-full text-black"
              placeholder="e.g., Why did DB connections fail around 2AM?"
            />

            {/* Start Analysis Button */}
            <button
              onClick={handleAnalyze}
              disabled={analyzing || !question.trim()}
              className="flex items-center space-x-2 px-6 py-3 bg-emerald-600 text-white rounded-lg font-semibold hover:bg-emerald-700 disabled:opacity-50 mt-2"
            >
              {analyzing ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>Analyzing... {analysisProgress}%</span>
                </>
              ) : (
                <>
                  <Play className="w-5 h-5" />
                  <span>Start Analysis</span>
                </>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
