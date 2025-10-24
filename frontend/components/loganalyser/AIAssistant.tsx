'use client';

import React, { useState } from 'react';
import { Bot, Loader2, AlertCircle, TrendingUp, Shield, MessageCircle } from 'lucide-react';

interface AIAssistantProps {
  analysisId: string;
}

type AnalysisType = 'error' | 'pattern' | 'security' | 'query';

export default function AIAssistant({ analysisId }: AIAssistantProps) {
  const [activeAnalysis, setActiveAnalysis] = useState<AnalysisType>('query');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [errorMessage, setErrorMessage] = useState('');
  const [naturalQuery, setNaturalQuery] = useState('');

  const handleErrorAnalysis = async () => {
    if (!errorMessage.trim()) return;

    setLoading(true);
    setResult(null);

    try {
      const response = await fetch(`/api/log-analyzer/ai/analyze-error/${analysisId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ error_message: errorMessage }),
      });

      if (!response.ok) throw new Error('Analysis failed');

      const data = await response.json();
      setResult(data);
    } catch (err: any) {
      alert('Error analysis failed: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handlePatternAnalysis = async () => {
    setLoading(true);
    setResult(null);

    try {
      const response = await fetch(`/api/log-analyzer/ai/analyze-patterns/${analysisId}`, {
        method: 'POST',
      });

      if (!response.ok) throw new Error('Pattern analysis failed');

      const data = await response.json();
      setResult(data);
    } catch (err: any) {
      alert('Pattern analysis failed: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSecurityAnalysis = async () => {
    setLoading(true);
    setResult(null);

    try {
      const response = await fetch(`/api/log-analyzer/ai/security-analysis/${analysisId}`, {
        method: 'POST',
      });

      if (!response.ok) throw new Error('Security analysis failed');

      const data = await response.json();
      setResult(data);
    } catch (err: any) {
      alert('Security analysis failed: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleNaturalQuery = async () => {
    if (!naturalQuery.trim()) return;

    setLoading(true);
    setResult(null);

    try {
      const response = await fetch(
        `/api/log-analyzer/ai/natural-query/${analysisId}?query=${encodeURIComponent(naturalQuery)}`,
        { method: 'POST' }
      );

      if (!response.ok) throw new Error('Query failed');

      const data = await response.json();
      setResult(data);
    } catch (err: any) {
      alert('Natural query failed: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-emerald-600 to-teal-600 text-white rounded-lg p-6">
        <h3 className="text-2xl font-bold mb-2 flex items-center space-x-2">
          <Bot className="w-7 h-7" />
          <span>AI-Powered Analysis</span>
        </h3>
        <p className="text-emerald-50">
          Get intelligent insights and resolution recommendations with compliance-aware AI analysis.
        </p>
      </div>

      {/* Analysis Type Tabs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <button
          onClick={() => setActiveAnalysis('query')}
          className={`
            flex flex-col items-center p-4 rounded-lg border-2 transition-all
            ${
              activeAnalysis === 'query'
                ? 'border-emerald-600 bg-emerald-50 text-emerald-900'
                : 'border-gray-300 bg-white text-gray-700 hover:border-emerald-400'
            }
          `}
        >
          <MessageCircle className="w-6 h-6 mb-2" />
          <span className="text-sm font-medium">Natural Query</span>
        </button>

        <button
          onClick={() => setActiveAnalysis('error')}
          className={`
            flex flex-col items-center p-4 rounded-lg border-2 transition-all
            ${
              activeAnalysis === 'error'
                ? 'border-emerald-600 bg-emerald-50 text-emerald-900'
                : 'border-gray-300 bg-white text-gray-700 hover:border-emerald-400'
            }
          `}
        >
          <AlertCircle className="w-6 h-6 mb-2" />
          <span className="text-sm font-medium">Error Analysis</span>
        </button>

        <button
          onClick={() => setActiveAnalysis('pattern')}
          className={`
            flex flex-col items-center p-4 rounded-lg border-2 transition-all
            ${
              activeAnalysis === 'pattern'
                ? 'border-emerald-600 bg-emerald-50 text-emerald-900'
                : 'border-gray-300 bg-white text-gray-700 hover:border-emerald-400'
            }
          `}
        >
          <TrendingUp className="w-6 h-6 mb-2" />
          <span className="text-sm font-medium">Pattern Analysis</span>
        </button>

        <button
          onClick={() => setActiveAnalysis('security')}
          className={`
            flex flex-col items-center p-4 rounded-lg border-2 transition-all
            ${
              activeAnalysis === 'security'
                ? 'border-emerald-600 bg-emerald-50 text-emerald-900'
                : 'border-gray-300 bg-white text-gray-700 hover:border-emerald-400'
            }
          `}
        >
          <Shield className="w-6 h-6 mb-2" />
          <span className="text-sm font-medium">Security Analysis</span>
        </button>
      </div>

      {/* Analysis Interface */}
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        {/* Natural Query */}
        {activeAnalysis === 'query' && (
          <div className="space-y-4">
            <h4 className="text-lg font-semibold text-gray-900">Ask a Natural Language Question</h4>
            <textarea
              value={naturalQuery}
              onChange={(e) => setNaturalQuery(e.target.value)}
              placeholder="e.g., 'What caused the most errors today?', 'Are there any security issues?'"
              rows={3}
              className="
                w-full px-4 py-3 border border-gray-300 rounded-lg
                focus:ring-2 focus:ring-emerald-500 focus:border-transparent
                resize-none
              "
              disabled={loading}
            />
            <button
              onClick={handleNaturalQuery}
              disabled={loading || !naturalQuery.trim()}
              className="
                w-full px-6 py-3 bg-emerald-600 text-white rounded-lg
                font-semibold hover:bg-emerald-700 transition-colors
                disabled:opacity-50 disabled:cursor-not-allowed
                flex items-center justify-center space-x-2
              "
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>Analyzing...</span>
                </>
              ) : (
                <>
                  <Bot className="w-5 h-5" />
                  <span>Ask AI Assistant</span>
                </>
              )}
            </button>
          </div>
        )}

        {/* Error Analysis */}
        {activeAnalysis === 'error' && (
          <div className="space-y-4">
            <h4 className="text-lg font-semibold text-gray-900">Analyze Specific Error</h4>
            <input
              type="text"
              value={errorMessage}
              onChange={(e) => setErrorMessage(e.target.value)}
              placeholder="Enter part of an error message to analyze..."
              className="
                w-full px-4 py-3 border border-gray-300 rounded-lg
                focus:ring-2 focus:ring-emerald-500 focus:border-transparent
              "
              disabled={loading}
            />
            <button
              onClick={handleErrorAnalysis}
              disabled={loading || !errorMessage.trim()}
              className="
                w-full px-6 py-3 bg-emerald-600 text-white rounded-lg
                font-semibold hover:bg-emerald-700 transition-colors
                disabled:opacity-50 disabled:cursor-not-allowed
                flex items-center justify-center space-x-2
              "
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>Analyzing...</span>
                </>
              ) : (
                <>
                  <AlertCircle className="w-5 h-5" />
                  <span>Analyze Error with AI</span>
                </>
              )}
            </button>
          </div>
        )}

        {/* Pattern Analysis */}
        {activeAnalysis === 'pattern' && (
          <div className="space-y-4">
            <h4 className="text-lg font-semibold text-gray-900">AI Pattern Analysis</h4>
            <p className="text-sm text-gray-600">
              Analyze error patterns across all logs to identify systemic issues and recommendations.
            </p>
            <button
              onClick={handlePatternAnalysis}
              disabled={loading}
              className="
                w-full px-6 py-3 bg-emerald-600 text-white rounded-lg
                font-semibold hover:bg-emerald-700 transition-colors
                disabled:opacity-50 disabled:cursor-not-allowed
                flex items-center justify-center space-x-2
              "
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>Analyzing Patterns...</span>
                </>
              ) : (
                <>
                  <TrendingUp className="w-5 h-5" />
                  <span>Analyze Patterns with AI</span>
                </>
              )}
            </button>
          </div>
        )}

        {/* Security Analysis */}
        {activeAnalysis === 'security' && (
          <div className="space-y-4">
            <h4 className="text-lg font-semibold text-gray-900">AI Security Analysis</h4>
            <p className="text-sm text-gray-600">
              Get security-focused insights about potential threats and vulnerabilities in your logs.
            </p>
            <button
              onClick={handleSecurityAnalysis}
              disabled={loading}
              className="
                w-full px-6 py-3 bg-emerald-600 text-white rounded-lg
                font-semibold hover:bg-emerald-700 transition-colors
                disabled:opacity-50 disabled:cursor-not-allowed
                flex items-center justify-center space-x-2
              "
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>Analyzing Security...</span>
                </>
              ) : (
                <>
                  <Shield className="w-5 h-5" />
                  <span>Security Analysis with AI</span>
                </>
              )}
            </button>
          </div>
        )}
      </div>

      {/* Results */}
      {result && (
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h4 className="text-lg font-semibold text-gray-900">AI Analysis Results</h4>
            {result.confidence_score && (
              <div className="text-sm text-gray-600">
                Confidence: <span className="font-medium">{(result.confidence_score * 100).toFixed(0)}%</span>
              </div>
            )}
          </div>

          {/* Response Text */}
          <div className="prose max-w-none">
            <div className="bg-gray-50 rounded-lg p-4 whitespace-pre-wrap">
              {result.ai_analysis || result.ai_insights || result.ai_security_assessment || result.response}
            </div>
          </div>

          {/* Error Details (if error analysis) */}
          {result.error_details && (
            <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
              <h5 className="font-semibold text-red-900 mb-2">Error Details</h5>
              <div className="space-y-1 text-sm">
                <p><span className="font-medium">Level:</span> {result.error_details.level}</p>
                <p><span className="font-medium">Category:</span> {result.error_details.category}</p>
                <p><span className="font-medium">Severity:</span> {result.error_details.severity}/5</p>
                <p><span className="font-medium">Timestamp:</span> {result.error_details.timestamp}</p>
              </div>
            </div>
          )}

          {/* Pattern Summary (if pattern analysis) */}
          {result.pattern_summary && (
            <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <h5 className="font-semibold text-blue-900 mb-2">Pattern Summary</h5>
              <div className="space-y-1 text-sm">
                <p><span className="font-medium">Total Errors:</span> {result.pattern_summary.total_errors}</p>
                <p><span className="font-medium">Unique Patterns:</span> {result.pattern_summary.unique_patterns}</p>
              </div>
            </div>
          )}

          {/* Processing Info */}
          {result.processing_time && (
            <div className="mt-4 text-xs text-gray-500">
              Processing time: {result.processing_time.toFixed(2)}s
            </div>
          )}
        </div>
      )}
    </div>
  );
}
