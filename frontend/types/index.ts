export interface User {
  id: string
  email: string
  name: string
  role: 'USER' | 'ADMIN'
  createdAt?: Date
  updatedAt?: Date
}

export interface Incident {
  sys_id: string
  number: string
  short_description: string
  description: string
  state: string
  priority: string
  severity: string
  category: string
  subcategory?: string
  assigned_to?: string
  created_at: string
  updated_at: string
  work_notes?: string
}

export interface IncidentProcessRequest {
  sys_id: string
  analysis_type?: string
  compliance_level?: string
}

export interface IncidentProcessResponse {
  success: boolean
  incident?: Incident
  ai_analysis?: any
  compliance_info?: any
  processing_time: number
  message: string
  errors?: string[]
}

export interface IncidentSummary {
  sys_id: string
  number: string
  short_description: string
  state: string
  priority: string
  created_at: string
  ai_insights?: string
  compliance_status?: string
}

export interface Service {
  id: string
  name: string
  description: string
  icon: string
  color: string
  endpoint: string
  enabled: boolean
  category: 'analysis' | 'management' | 'monitoring' | 'integration' | 'data' | 'support' | 'operations' | 'communication' | 'analytics' | 'documentation' | 'governance'
}

export interface DashboardStats {
  totalIncidents: number
  activeIncidents: number
  resolvedIncidents: number
  criticalIncidents: number
  averageResolutionTime: number
  userActivity: number
}