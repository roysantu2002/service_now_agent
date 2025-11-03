// frontend/lib/services/incident-service.ts

import { apiClient } from '@/lib/api-client'
import {
  Incident,
  IncidentAnalysis,
  IncidentProcessRequest,
  IncidentProcessResponse,
  IncidentSummary,
} from '@/types'

export const incidentService = {
  // ----------------------------------------
  // 🔹 Core Incident APIs
  // ----------------------------------------

  // Create incident
  async createIncident(payload: {
    short_description: string
    description: string
    work_notes?: string
  }): Promise<Incident> {
    const response = await apiClient.post('/api/v1/incidents/create', payload)
    return response.data
  },

  // Update incident
  async updateIncident(
    sysId: string,
    payload: {
      short_description?: string
      description?: string
      work_notes?: string
    }
  ): Promise<Incident> {
    const response = await apiClient.put(`/api/v1/incidents/${sysId}/update`, payload)
    return response.data
  },

  // Process incident
  async processIncident(
    sysId: string,
    request?: IncidentProcessRequest,
    provider?: string
  ): Promise<IncidentProcessResponse> {
    const params = provider ? { provider } : {}
    const response = await apiClient.post(`/api/v1/incidents/process/${sysId}`, request, { params })
    return response.data
  },

  // Get incident summary
  async getIncidentSummary(sysId: string, provider?: string): Promise<IncidentSummary> {
    const params = provider ? { provider } : {}
    const response = await apiClient.get(`/api/v1/incidents/${sysId}/summary`, { params })
    return response.data
  },

  // Get incident details
  async getIncidentDetails(sysId: string, provider?: string): Promise<Incident> {
    const params = provider ? { provider } : {}
    const response = await apiClient.get(`/api/v1/incidents/${sysId}/details`, { params })
    return response.data
  },

  // Analyze incident
  async analyzeIncident(
    sysId: string,
    analysisType: string = 'general',
    provider?: string
  ): Promise<IncidentAnalysis> {
    const params = { provider, analysis_type: analysisType }
    const response = await apiClient.post(`/api/v1/incidents/${sysId}/analyze`, {}, { params })
    return response.data
  },

  // Filter incident data (for compliance)
  async filterIncidentData(
    sysId: string,
    complianceLevel: string = 'internal',
    provider?: string
  ): Promise<any> {
    const params = { provider, compliance_level: complianceLevel }
    const response = await apiClient.post(
      `/api/v1/incidents/${sysId}/compliance-filter`,
      {},
      { params }
    )
    return response.data
  },

  // Get incident insights
  async getIncidentInsights(
    sysId: string,
    analysisType: string = 'general',
    provider?: string
  ): Promise<any> {
    const params = { provider, analysis_type: analysisType }
    const response = await apiClient.post(`/api/v1/incidents/${sysId}/insights`, {}, { params })
    return response.data
  },

  // Get incident history
  async getIncidentHistory(sysId: string, provider?: string): Promise<any> {
    const params = provider ? { provider } : {}
    const response = await apiClient.get(`/api/v1/incidents/${sysId}/history`, { params })
    return response.data
  },

  // List all incidents
  async listIncidents(filters?: {
    state?: string
    priority?: string
    assigned_to?: string
    limit?: number
    offset?: number
  }): Promise<{ data: Incident[] }> {
    const response = await apiClient.get('/api/v1/incidents', { params: filters })
    return response.data
  },

  // ----------------------------------------
  // 🔹 ServiceNow Webhook Incident APIs
  // ----------------------------------------

  /**
   * Fetch paginated ServiceNow webhook incident logs.
   * Example: /api/v1/webhooks/servicenow/incidents?page=1&page_size=10
   */
 async listWebhookIncidents(params?: {
  page?: number
  page_size?: number
  start_date?: string | null
  end_date?: string | null
}): Promise<{ data: Incident[] }> {
  try {
    const response = await apiClient.get<{ data: Incident[] }>(
      '/api/v1/webhooks/servicenow/incidents',
      { params }
    )
    return response.data
  } catch (error: any) {
    if (process.env.NODE_ENV !== 'production') {
      console.error('Network or API error in listWebhookIncidents:', error)
    }
    return { data: [] } // fallback
  }
},



  /**
   * 🔹 List AI analysis (filtered)
   */
  async listWebhookAnalysis(params?: {
    page?: number
    page_size?: number
    sys_id?: string | null
    incident_id?: string | null
  }): Promise<{ data: IncidentAnalysis[] }> {
    const response = await apiClient.get('/api/v1/webhooks/servicenow/analysis', { params })
    return response.data
  },

  /**
   * 🔹 Get specific AI analysis by incident_id
   */
  async getWebhookAnalysisByIncidentId(
    incident_id: string
  ): Promise<{ data: IncidentAnalysis[] }> {
    const response = await apiClient.get(
      `/api/v1/webhooks/servicenow/analysis/${encodeURIComponent(incident_id)}`
    )
    return response.data
  },

  /**
   * 🔹 Create new simulated webhook incident
   */
  async createWebhookIncident(payload: {
    short_description: string
    source?: string
    created_via?: string
  }): Promise<Incident> {
    const response = await apiClient.post('/api/v1/webhooks/servicenow/incidents', payload)
    return response.data
  },

  /**
   * 🔹 Update existing webhook incident (for reprocessing or modification)
   */
  async updateWebhookIncident(
    incident_id: string,
    payload: any
  ): Promise<{ message: string }> {
    const response = await apiClient.put(
      `/api/v1/webhooks/servicenow/${encodeURIComponent(incident_id)}`,
      payload
    )
    return response.data
  },

  async updateServiceNowIncident(sysId: string, payload: any) {
  return apiClient.post(`/api/v1/webhooks/servicenow/incident/${sysId}/update-fields`, payload)
}
}

