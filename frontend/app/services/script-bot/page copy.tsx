'use client';

import React, { useState } from 'react';
import {
  FileText,
  Loader2,
  FileCode,
  CheckCircle2,
  RefreshCcw,
  Rocket,
} from 'lucide-react';
import { toast } from 'react-hot-toast';
import { API_BASE_URL } from '@/lib/api-config';

export default function ScriptBotPage() {
  const [name, setName] = useState('Restart VM');
  const [description, setDescription] = useState(
    'Generate an Ansible playbook to restart VM service on Ubuntu.'
  );
  const [techComment, setTechComment] = useState(
    'Include pre-check for service status.'
  );

  const [loading, setLoading] = useState(false);
  const [usecase, setUsecase] = useState<any>(null);
  const [scriptResult, setScriptResult] = useState<any>(null);

  // Submit new use case
  const handleSubmitUsecase = async () => {
    if (!name || !description) {
      toast.error('Please fill in name and description.');
      return;
    }

    setLoading(true);
    setUsecase(null);
    setScriptResult(null);

    try {
      const response = await fetch(`${API_BASE_URL}/script/usecases/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description, tech_comment: techComment }),
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Submission failed');

      toast.success('✅ Use case submitted successfully');
      setUsecase(data.data);
    } catch (err: any) {
      toast.error(`Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Fetch use case details by ID
  const handleFetchUsecase = async (id?: string) => {
    const usecaseId = id || usecase?.id;
    if (!usecaseId) {
      toast.error('No use case ID available');
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/script/usecases/${usecaseId}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to fetch use case');

      toast.success('📦 Use case details fetched');
      setUsecase(data.data);
    } catch (err: any) {
      toast.error(`Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Generate the playbook
  const handleGenerateScript = async () => {
    if (!usecase?.id) {
      toast.error('Please submit or fetch a use case first.');
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/script/script/create?provider=gemini`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          uid: usecase.id,
          name,
          query: `Create an Ansible playbook to ${description}`,
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Script generation failed');

      toast.success('🚀 Script generated successfully');
      setScriptResult(data.data);
    } catch (err: any) {
      toast.error(`Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-900 py-10">
      <div className="max-w-4xl mx-auto bg-gray-800 shadow-lg rounded-xl p-8 space-y-6">
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

        {/* Form */}
        <div className="space-y-4 border-t border-gray-700 pt-4">
          <div>
            <label className="block text-sm font-medium text-gray-400">
              Use Case Name
            </label>
            <input
              type="text"
              className="w-full p-2 border border-gray-700 bg-gray-900 rounded-md focus:ring-emerald-500 focus:border-emerald-500 text-gray-200 placeholder-gray-500"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Restart VM"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400">
              Description
            </label>
            <textarea
              className="w-full p-2 border border-gray-700 bg-gray-900 rounded-md focus:ring-emerald-500 focus:border-emerald-500 text-gray-200 placeholder-gray-500"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe what the playbook should do..."
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400">
              Technical Comment (optional)
            </label>
            <input
              type="text"
              className="w-full p-2 border border-gray-700 bg-gray-900 rounded-md focus:ring-emerald-500 focus:border-emerald-500 text-gray-200 placeholder-gray-500"
              value={techComment}
              onChange={(e) => setTechComment(e.target.value)}
              placeholder="Additional implementation details..."
            />
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3 pt-2 flex-wrap">
            <button
              onClick={handleSubmitUsecase}
              disabled={loading}
              className="bg-emerald-600 hover:bg-emerald-700 text-white px-5 py-2 rounded-md flex items-center gap-2 font-semibold disabled:opacity-50"
            >
              {loading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Rocket className="w-5 h-5" />
              )}
              Submit Use Case
            </button>

            {usecase && (
              <>
                <button
                  onClick={() => handleFetchUsecase(usecase.id)}
                  disabled={loading}
                  className="bg-amber-500 hover:bg-amber-600 text-white px-5 py-2 rounded-md flex items-center gap-2 font-semibold disabled:opacity-50"
                >
                  {loading ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <RefreshCcw className="w-5 h-5" />
                  )}
                  Fetch Use Case
                </button>

                <button
                  onClick={handleGenerateScript}
                  disabled={loading}
                  className="bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2 rounded-md flex items-center gap-2 font-semibold disabled:opacity-50"
                >
                  {loading ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <FileCode className="w-5 h-5" />
                  )}
                  Generate Script
                </button>
              </>
            )}
          </div>
        </div>

        {/* Use Case Result */}
        {usecase && (
          <div className="bg-gray-900 border border-gray-700 rounded-lg p-5 space-y-3 text-gray-200">
            <h2 className="text-xl font-semibold flex items-center gap-2 text-gray-100">
              <CheckCircle2 className="text-emerald-400" /> Use Case Details
            </h2>
            <div className="text-sm space-y-1">
              <p><b>ID:</b> {usecase.id}</p>
              <p><b>Name:</b> {usecase.name}</p>
              <p><b>Description:</b> {usecase.description}</p>
              <p><b>Tech Comment:</b> {usecase.tech_comment}</p>
              <p><b>Status:</b> {usecase.status}</p>
              <p><b>Created:</b> {new Date(usecase.created_at).toLocaleString()}</p>
            </div>
          </div>
        )}

        {/* Script Result */}
        {scriptResult && (
          <div className="bg-gray-900 border border-gray-700 rounded-lg p-5 space-y-3 text-gray-200">
            <h2 className="text-xl font-semibold flex items-center gap-2 text-gray-100">
              <FileCode className="text-indigo-400" /> Script Generation Result
            </h2>
            <div className="text-sm space-y-1">
              <p><b>Git URL:</b> {scriptResult.git_url}</p>
              <p><b>Branch:</b> {scriptResult.git_branch}</p>
              <p><b>Total Steps:</b> {scriptResult.total_steps}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
