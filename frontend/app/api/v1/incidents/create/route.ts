import { NextRequest, NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '../../../auth/[...nextauth]/route'

interface CreateIncidentRequest {
  short_description: string
  description: string
  work_notes?: string
}

interface CreateIncidentResponse {
  success: boolean
  data: {
    sys_id: string
    number: string
    short_description: string
    description: string
    work_notes?: string
    state: string
    priority: string
    created_at: string
    created_by: string
  }
  message: string
}

export async function POST(request: NextRequest) {
  try {
    // Get session for authentication
    const session = await getServerSession(authOptions)
    
    if (!session?.user) {
      return NextResponse.json(
        { success: false, error: 'Unauthorized - Please sign in' },
        { status: 401 }
      )
    }

    // Parse request body
    const body: CreateIncidentRequest = await request.json()
    
    // Validate required fields
    if (!body.short_description?.trim()) {
      return NextResponse.json(
        { success: false, error: 'Short description is required' },
        { status: 400 }
      )
    }

    if (!body.description?.trim()) {
      return NextResponse.json(
        { success: false, error: 'Description is required' },
        { status: 400 }
      )
    }

    // Generate a unique incident number and sys_id (in real implementation, this would come from ServiceNow)
    const incidentNumber = `INC${Date.now().toString().slice(-7)}`
    const sysId = generateSysId()
    
    // Simulate ServiceNow API call (replace with actual ServiceNow API integration)
    const incidentData = {
      sys_id: sysId,
      number: incidentNumber,
      short_description: body.short_description.trim(),
      description: body.description.trim(),
      work_notes: body.work_notes?.trim() || '',
      state: '1', // New
      priority: '3', // Moderate
      created_at: new Date().toISOString(),
      created_by: session.user.email || session.user.name || 'Unknown'
    }

    // Here you would typically make an API call to ServiceNow
    // const serviceNowResponse = await createIncidentInServiceNow(incidentData)
    
    // For demo purposes, we'll simulate a successful creation
    const response: CreateIncidentResponse = {
      success: true,
      data: incidentData,
      message: `Incident ${incidentNumber} created successfully`
    }

    return NextResponse.json(response, { status: 201 })

  } catch (error) {
    console.error('Error creating incident:', error)
    
    return NextResponse.json(
      { 
        success: false, 
        error: 'Internal server error - Unable to create incident' 
      },
      { status: 500 }
    )
  }
}

// Generate a ServiceNow-style sys_id
function generateSysId(): string {
  const chars = '0123456789abcdef'
  let result = ''
  for (let i = 0; i < 32; i++) {
    if (i === 8 || i === 12 || i === 16 || i === 20) {
      result += '-'
    } else {
      result += chars[Math.floor(Math.random() * chars.length)]
    }
  }
  return result
}

// Example function for actual ServiceNow integration (implement based on your backend)
/*
async function createIncidentInServiceNow(incidentData: any) {
  const serviceNowEndpoint = process.env.SERVICENOW_INSTANCE_URL + '/api/now/table/incident'
  
  const response = await fetch(serviceNowEndpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Basic ${Buffer.from(
        `${process.env.SERVICENOW_USERNAME}:${process.env.SERVICENOW_PASSWORD}`
      ).toString('base64')}`
    },
    body: JSON.stringify({
      short_description: incidentData.short_description,
      description: incidentData.description,
      work_notes: incidentData.work_notes,
      caller_id: incidentData.created_by, // You'd need to map this to ServiceNow user
      priority: incidentData.priority,
      state: incidentData.state
    })
  })
  
  if (!response.ok) {
    throw new Error(`ServiceNow API error: ${response.statusText}`)
  }
  
  return await response.json()
}
*/