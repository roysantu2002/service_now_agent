/**
 * API Configuration for Log Analyzer
 * 
 * This file centralizes all API endpoint URLs and configuration
 */

// Get API base URL from environment variable or default to localhost
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1';

// Log Analyzer API endpoints
export const LOG_ANALYZER_API = {
  // Upload endpoints
  upload: `${API_BASE_URL}/log-analyzer/upload`,
  uploadProgress: (sessionId: string) => `${API_BASE_URL}/log-analyzer/upload/progress/${sessionId}`,
  
  // Analysis endpoints
  analyze: (sessionId: string) => `${API_BASE_URL}/log-analyzer/analyze/${sessionId}`,
  analysisStatus: (taskId: string) => `${API_BASE_URL}/log-analyzer/analyze/status/${taskId}`,
  
  // Compliance endpoints
  compliance: (sessionId: string) => `${API_BASE_URL}/log-analyzer/compliance/${sessionId}`,
  
  // Search endpoints
  searchInitialize: (sessionId: string) => `${API_BASE_URL}/log-analyzer/search/initialize/${sessionId}`,
  search: (sessionId: string) => `${API_BASE_URL}/log-analyzer/search/${sessionId}`,
  
  // AI endpoints
  aiInsights: (sessionId: string) => `${API_BASE_URL}/log-analyzer/ai/insights/${sessionId}`,
  aiChat: (sessionId: string) => `${API_BASE_URL}/log-analyzer/ai/chat/${sessionId}`,
  
  // Utility endpoints
  health: `${API_BASE_URL}/log-analyzer/health`,
  cleanup: (sessionId: string) => `${API_BASE_URL}/log-analyzer/session/${sessionId}`,
};

// Helper function to handle API errors
export const handleApiError = async (response: Response) => {
  if (!response.ok) {
    let errorMessage = 'An error occurred';
    try {
      const errorData = await response.json();
      errorMessage = errorData.detail || errorData.message || errorMessage;
    } catch {
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }
  return response;
};
