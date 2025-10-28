'use client';

import React, { useState } from 'react';
import { Loader2, FileText, FileCode, RefreshCcw, Rocket } from 'lucide-react';
import { API_BASE_URL } from '@/lib/api-config';

export default function ScriptBotPage() {
  const [name, setName] = useState('Restart VM');
  const [description, setDescription] = useState(
    'Generate an Ansible playbook to restart VM service on Ubuntu.'
  );
  const [techComment, setTechComment] = useState('Include pre-check for service status.');

  const [loading, setLoading] = useState(false);
  const [submitResult, setSubmitResult] = useState<any>(null);
  const [usecaseDetails, setUsecaseDetails] = useState<any>(null);
  const [scriptResult, setScriptResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  // Step 1: Submit Use Case
  const handleSubmitUsecase = async () => {
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE_URL}/script/usecases/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description, tech_comment: techComment }),
      });

      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.detail || data.message || 'Submission failed');
      setSubmitResult(data);
    } catch (err: any) {
      setError(err.message || 'Unexpected error');
    } finally {
      setLoading(false);
    }
  };

  // Step 2: Get Use Case Details
  const handleGetUsecaseDetails = async () => {
    if (!submitResult?.uid) return;
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE_URL}/script/usecases/${submitResult.uid}`);
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.detail || 'Failed to fetch details');
      setUsecaseDetails(data.data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Step 3: Generate Script
  const handleGenerateScript = async () => {
    if (!submitResult?.uid) return;
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE_URL}/script/script/create?provider=gemini`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          uid: submitResult.uid,
          name,
          query: `Create an Ansible playbook to ${description}`,
        }),
      });

      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.detail || data.message || 'Script creation failed');
      setScriptResult(data.data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-900 py-10">
      <div className="max-w-4xl mx-auto bg-gray-800 rounded-xl shadow-lg p-8 space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3">
          <FileText className="w-6 h-6 text-emerald-400" />
          <h1 className="text-3xl font-bold text-gray-100">
            Script Bot – Use Case Builder
          </h1>
        </div>
        <p className="text-gray-400">
          Submit a use case, retrieve its metadata, and generate an Ansible playbook automatically.
        </p>

        {/* --- Section 1: Submit Use Case --- */}
        <div className="space-y-4 border-t border-gray-700 pt-4">
          <h2 className="text-lg font-semibold text-gray-300">Step 1: Submit Use Case</h2>

          <div>
            <label className="block text-sm font-medium text-gray-400">Use Case Name</label>
            <input
              type="text"
              className="w-full p-2 border border-gray-700 bg-gray-900 rounded-md text-gray-200 placeholder-gray-500 focus:ring-emerald-500 focus:border-emerald-500"
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={!!submitResult}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400">Description</label>
            <textarea
              className="w-full p-2 border border-gray-700 bg-gray-900 rounded-md text-gray-200 placeholder-gray-500 focus:ring-emerald-500 focus:border-emerald-500"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={!!submitResult}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400">
              Technical Comment (optional)
            </label>
            <input
              type="text"
              className="w-full p-2 border border-gray-700 bg-gray-900 rounded-md text-gray-200 placeholder-gray-500 focus:ring-emerald-500 focus:border-emerald-500"
              value={techComment}
              onChange={(e) => setTechComment(e.target.value)}
              disabled={!!submitResult}
            />
          </div>

          <button
            onClick={handleSubmitUsecase}
            disabled={loading || !!submitResult}
            className="bg-emerald-600 hover:bg-emerald-700 text-white px-5 py-2 rounded-md flex items-center gap-2 font-semibold disabled:opacity-50"
          >
            {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Rocket className="w-5 h-5" />}
            {submitResult ? 'Use Case Submitted' : 'Submit Use Case'}
          </button>
        </div>

        {/* Success Message */}
        {submitResult && (
          <div className="mt-4 bg-emerald-700 text-white p-4 rounded-lg space-y-2">
            <p className="font-semibold">✅ {submitResult.message}</p>
            <p>
              <b>UID:</b>{' '}
              <span className="font-mono text-gray-200">{submitResult.uid}</span>
            </p>
          </div>
        )}

        {/* --- Section 2: Post-Submission Actions --- */}
        {submitResult && (
          <div className="border-t border-gray-700 pt-4 space-y-4">
            <h2 className="text-lg font-semibold text-gray-300">
              Step 2: Manage Submitted Use Case
            </h2>
            <div className="flex gap-3 flex-wrap">
              <button
                onClick={handleGetUsecaseDetails}
                disabled={loading}
                className="bg-amber-500 hover:bg-amber-600 text-white px-4 py-2 rounded-md flex items-center gap-2 disabled:opacity-50"
              >
                {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <RefreshCcw className="w-5 h-5" />}
                Fetch Use Case Details
              </button>

              <button
                onClick={handleGenerateScript}
                disabled={loading}
                className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-md flex items-center gap-2 disabled:opacity-50"
              >
                {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <FileCode className="w-5 h-5" />}
                Generate Script
              </button>
            </div>
          </div>
        )}

        {/* --- Error Message --- */}
        {error && <div className="bg-red-700 text-white p-3 rounded-md">❌ {error}</div>}

        {/* --- Details Section --- */}
        {usecaseDetails && (
          <div className="bg-gray-900 border border-gray-700 rounded-lg p-4 text-gray-200 space-y-2">
            <h2 className="text-xl font-semibold text-emerald-400">📦 Use Case Details</h2>
            <p><b>ID:</b> {usecaseDetails.id}</p>
            <p><b>Name:</b> {usecaseDetails.name}</p>
            <p><b>Description:</b> {usecaseDetails.description}</p>
            <p><b>Tech Comment:</b> {usecaseDetails.tech_comment}</p>
            <p><b>Status:</b> {usecaseDetails.status}</p>
            <p><b>Created:</b> {new Date(usecaseDetails.created_at).toLocaleString()}</p>
          </div>
        )}

        {/* --- Script Result Section --- */}
        {scriptResult && (
          <div className="bg-gray-900 border border-gray-700 rounded-lg p-4 text-gray-200 space-y-2">
            <h2 className="text-xl font-semibold text-indigo-400">🚀 Script Created</h2>
            <p><b>Git URL:</b> {scriptResult.git_url}</p>
            <p><b>Branch:</b> {scriptResult.git_branch}</p>
            <p><b>Total Steps:</b> {scriptResult.total_steps}</p>
          </div>
        )}
      </div>
    </div>
  );
}
