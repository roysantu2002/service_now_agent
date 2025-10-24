'use client';

import React, { useState, useCallback } from 'react';
import { Upload, FileText, AlertCircle, CheckCircle, Loader2 } from 'lucide-react';
import { useDropzone } from 'react-dropzone';
import { API_BASE_URL } from '@/lib/api-config';

interface UploadProgress {
  upload_id: string;
  status: string;
  progress: number;
  total_size: number;
  uploaded_size: number;
  filename: string;
}

interface LogFileUploadProps {
  onUploadComplete: (uploadId: string, filename: string) => void;
}

export default function LogFileUpload({ onUploadComplete }: LogFileUploadProps) {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState<UploadProgress | null>(null);
  const [error, setError] = useState<string | null>(null);

  const uploadFile = async (file: File) => {
    setUploading(true);
    setError(null);
    setProgress(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(`${API_BASE_URL}/log-analyzer/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Upload failed');
      }

      const { upload_id } = await response.json();

      const pollInterval = setInterval(async () => {
        try {
          const res = await fetch(`${API_BASE_URL}/log-analyzer/upload/progress/${upload_id}`);
          const data: UploadProgress = await res.json();
          setProgress(data);

          if (data.status === 'completed') {
            clearInterval(pollInterval);
            setUploading(false);
            onUploadComplete(upload_id, data.filename);
          } else if (data.status === 'error') {
            clearInterval(pollInterval);
            setUploading(false);
            setError('Upload failed');
          }
        } catch {
          clearInterval(pollInterval);
          setUploading(false);
          setError('Failed to fetch upload progress');
        }
      }, 1000);

      setTimeout(() => clearInterval(pollInterval), 5 * 60 * 1000);
    } catch (err: any) {
      setUploading(false);
      setError(err.message || 'Upload failed');
    }
  };

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      const file = acceptedFiles[0];
      const MAX_SIZE = 1 * 1024 * 1024 * 1024; // 1GB
      if (file.size > MAX_SIZE) {
        setError('File size exceeds 1GB limit');
        return;
      }
      uploadFile(file);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'text/plain': ['.log', '.txt'] },
    multiple: false,
    maxSize: 1 * 1024 * 1024 * 1024,
    disabled: uploading,
  });

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
  };

  return (
    <div className="w-full space-y-4">
      {/* Upload Dropzone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-lg p-8 text-center transition-all ${
          isDragActive
            ? 'border-emerald-500 bg-emerald-50'
            : 'border-gray-300 hover:border-emerald-400 hover:bg-gray-50'
        } ${uploading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
      >
        <input {...getInputProps()} />
        <div className="flex flex-col items-center space-y-3">
          {uploading ? (
            <Loader2 className="w-12 h-12 text-emerald-500 animate-spin" />
          ) : (
            <Upload className="w-12 h-12 text-gray-400" />
          )}
          <p className="text-gray-700 font-medium">
            {isDragActive ? 'Drop your log file here...' : 'Drag & drop or click to browse'}
          </p>
          <p className="text-sm text-gray-500">Supports .log or .txt (up to 1GB)</p>
        </div>
      </div>

      {/* Progress Display */}
      {progress && (
        <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <FileText className="w-5 h-5 text-emerald-600" />
              <span className="font-medium text-gray-900">{progress.filename}</span>
            </div>
            <span className="text-sm text-gray-500">
              {formatBytes(progress.uploaded_size)} / {formatBytes(progress.total_size)}
            </span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2.5">
            <div
              className="bg-emerald-600 h-2.5 rounded-full transition-all duration-300"
              style={{ width: `${progress.progress}%` }}
            />
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">
              {progress.status === 'completed' ? 'Upload complete!' : 'Uploading...'}
            </span>
            <span className="text-emerald-600 font-medium">{progress.progress}%</span>
          </div>
        </div>
      )}

      {progress?.status === 'completed' && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4 flex items-center space-x-2">
          <CheckCircle className="w-5 h-5 text-emerald-600" />
          <span className="text-emerald-900 font-medium">
            File uploaded successfully! Ready for analysis.
          </span>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center space-x-2">
          <AlertCircle className="w-5 h-5 text-red-600" />
          <span className="text-red-900 font-medium">{error}</span>
        </div>
      )}
    </div>
  );
}
