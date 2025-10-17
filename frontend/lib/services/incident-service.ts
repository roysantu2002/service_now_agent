import { apiClient } from '@/lib/api-client'
import { 
  Incident, 
  IncidentProcessRequest, 
  IncidentProcessResponse, 
  IncidentSummary 
} from '@/types'

export const incidentService = {
  // Create incident
  async createIncident(payload: {
    short_description: string
    description: string
    work_notes?: string
  }) {
    const response = await apiClient.post('/api/v1/incidents/create', payload)
    return response.data
  },

  // Update incident
  async updateIncident(sysId: string, payload: {
    short_description?: string
    description?: string
    work_notes?: string
  }) {
    const response = await apiClient.put(`/incidents/${sysId}/update`, payload)
    return response.data
  },

  // Process incident
  async processIncident(
    sysId: string, 
    request?: IncidentProcessRequest,
    provider?: string
  ): Promise<IncidentProcessResponse> {
    const params = provider ? { provider } : {}
    const response = await apiClient.post(
      `/incidents/process/${sysId}`, 
      request,
      { params }
    )
    return response.data
  },

  // Get incident summary
  async getIncidentSummary(sysId: string, provider?: string): Promise<IncidentSummary> {
    const params = provider ? { provider } : {}
    const response = await apiClient.get(`/incidents/${sysId}/summary`, { params })
    return response.data
  },

  // Get incident details
  async getIncidentDetails(sysId: string, provider?: string) {
    const params = provider ? { provider } : {}
    const response = await apiClient.get(`/incidents/${sysId}/details`, { params })
    return response.data
  },

  // Analyze incident
  async analyzeIncident(
    sysId: string, 
    analysisType: string = 'general',
    provider?: string
  ) {
    const params = { provider, analysis_type: analysisType }
    const response = await apiClient.post(`/incidents/${sysId}/analyze`, {}, { params })
    return response.data
  },

  // Filter incident data for compliance
  async filterIncidentData(
    sysId: string, 
    complianceLevel: string = 'internal',
    provider?: string
  ) {
    const params = { provider, compliance_level: complianceLevel }
    const response = await apiClient.post(`/incidents/${sysId}/compliance-filter`, {}, { params })
    return response.data
  },

  // Get incident insights
  async getIncidentInsights(
    sysId: string, 
    analysisType: string = 'general',
    provider?: string
  ) {
    const params = { provider, analysis_type: analysisType }
    const response = await apiClient.post(`/incidents/${sysId}/insights`, {}, { params })
    return response.data
  },

  // Get incident history
  async getIncidentHistory(sysId: string, provider?: string) {
    const params = provider ? { provider } : {}
    const response = await apiClient.get(`/incidents/${sysId}/history`, { params })
    return response.data
  },

  // List incidents (if you have such endpoint)
  async listIncidents(filters?: {
    state?: string
    priority?: string
    assigned_to?: string
    limit?: number
    offset?: number
  }) {
    const response = await apiClient.get('/incidents', { params: filters })
    return response.data
  },
}