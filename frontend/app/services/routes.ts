import { Service } from '@/types/'

export const services: Service[] = [
  {
    id: 'middleware',
    name: 'Middleware Integration',
    description: 'Unified integration layer for connecting legacy systems, APIs, and AI pipelines.',
    icon: 'ServerStackIcon',
    color: 'from-indigo-500 to-blue-600',
    endpoint: '/middleware',
    enabled: true,
    category: 'integration'
  },
  {
    id: 'eus',
    name: 'End User Services (EUS)',
    description: 'AI assistance for device management, access issues, and user support automation.',
    icon: 'UserGroupIcon',
    color: 'from-pink-500 to-rose-600',
    endpoint: '/eus',
    enabled: true,
    category: 'support'
  },
  {
    id: 'servicedesk',
    name: 'Service Desk Automation',
    description: 'Smart ticketing, classification, and resolution workflows using generative AI.',
    icon: 'WrenchScrewdriverIcon',
    color: 'from-blue-500 to-cyan-600',
    endpoint: '/servicedesk',
    enabled: true,
    category: 'operations'
  },
  {
    id: 'chatbot',
    name: 'Conversational AI Chatbot',
    description: 'Omnichannel chatbot for IT, HR, and customer queries with contextual memory.',
    icon: 'ChatBubbleLeftRightIcon',
    color: 'from-violet-500 to-purple-600',
    endpoint: '/chatbot',
    enabled: true,
    category: 'communication'
  },
  {
    id: 'rag',
    name: 'RAG Knowledge Engine',
    description: 'Retrieval-Augmented Generation for dynamic document insights and data reasoning.',
    icon: 'DocumentMagnifyingGlassIcon',
    color: 'from-teal-500 to-emerald-600',
    endpoint: '/rag',
    enabled: true,
    category: 'analysis'
  },
  {
    id: 'incident',
    name: 'Incident Management',
    description: 'AI-powered detection, triage, and resolution integrated with ServiceNow and Jira.',
    icon: 'ExclamationTriangleIcon',
    color: 'from-red-500 to-pink-600',
    endpoint: '/incidents',
    enabled: true,
    category: 'management'
  },
  {
    id: 'monitoring',
    name: 'Monitoring & Observability',
    description: 'Unified monitoring dashboards with anomaly detection and real-time metrics.',
    icon: 'ChartBarIcon',
    color: 'from-purple-500 to-violet-600',
    endpoint: '/monitoring',
    enabled: true,
    category: 'analytics'
  },
  {
    id: 'ml-insights',
    name: 'ML Insights',
    description: 'Machine learning models for predictive maintenance, risk scoring, and forecasting.',
    icon: 'CpuChipIcon',
    color: 'from-orange-500 to-amber-600',
    endpoint: '/ml',
    enabled: false,
    category: 'analysis'
  },
  {
    id: 'compliance',
    name: 'Compliance & Governance',
    description: 'Automated compliance validation and audit readiness with regulatory frameworks.',
    icon: 'ShieldCheckIcon',
    color: 'from-gray-600 to-slate-700',
    endpoint: '/compliance',
    enabled: false,
    category: 'governance'
  },
  {
    id: 'knowledgebase',
    name: 'Knowledge Base Automation',
    description: 'Auto-curated enterprise knowledge repository powered by LLM summarization.',
    icon: 'DocumentTextIcon',
    color: 'from-cyan-500 to-sky-600',
    endpoint: '/knowledge',
    enabled: true,
    category: 'documentation'
  },
  {
    id: 'integration-hub',
    name: 'Integration Hub',
    description: 'Central hub for workflow orchestration, API federation, and AI service mesh.',
    icon: 'Cog6ToothIcon',
    color: 'from-lime-500 to-green-600',
    endpoint: '/integration',
    enabled: true,
    category: 'integration'
  }
]
