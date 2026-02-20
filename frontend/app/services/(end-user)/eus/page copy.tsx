'use client'

import Link from "next/link"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/hooks/use-auth"
import { WrenchScrewdriverIcon, CpuChipIcon, ChatBubbleLeftRightIcon, UserGroupIcon } from "@heroicons/react/24/outline"

interface Feature {
  id: string
  name: string
  description: string
  icon: string
  color: string
  endpoint: string
  enabled: boolean
}

const eusFeatures: Feature[] = [
  { id: "service-desk", name: "Service Desk", description: "Smart ticketing, classification, and automated resolution workflows using AI.", icon: "WrenchScrewdriverIcon", color: "from-blue-500 to-cyan-600", endpoint: "/services/eus/service-desk", enabled: true },
  { id: "vws-services", name: "VWS Services", description: "Virtual Workplace Services for remote monitoring, device management, and employee productivity support.", icon: "CpuChipIcon", color: "from-indigo-500 to-purple-600", endpoint: "/services/eus/vws-services", enabled: true },
  { id: "voice-support", name: "Voice Support", description: "AI-enabled voice assistant to help employees resolve issues hands-free.", icon: "ChatBubbleLeftRightIcon", color: "from-pink-500 to-rose-600", endpoint: "/services/eus/voice-support", enabled: true },
  { id: "tools-automation", name: "Tools & Automation", description: "End-user automation tools to simplify repetitive tasks, self-service scripts, and device provisioning.", icon: "UserGroupIcon", color: "from-green-500 to-teal-600", endpoint: "/services/eus/tools-automation", enabled: true },
]

const iconMap = { WrenchScrewdriverIcon, CpuChipIcon, ChatBubbleLeftRightIcon, UserGroupIcon }

export default function EndUserServicesPage() {
  const { isAuthenticated, isAdmin } = useAuth()
  const filteredFeatures = eusFeatures.filter(f => f.enabled || isAdmin)

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-12 sm:py-16 lg:py-24">
      <div className="grid max-w-2xl grid-cols-1 gap-4 sm:gap-6 lg:grid-cols-2 xl:grid-cols-2 mx-auto">
        {filteredFeatures.map(feature => {
          const IconComponent = iconMap[feature.icon as keyof typeof iconMap]
          return (
            <Card key={feature.id} className="group hover:shadow-lg transition-all duration-300 relative overflow-hidden">
              <div className={`absolute top-0 left-0 w-full h-1 bg-gradient-to-r ${feature.color}`} />
              <CardHeader className="pb-3 sm:pb-4">
                <div className="flex flex-col sm:flex-row sm:items-center sm:space-x-3">
                  <div className={`p-2 rounded-lg bg-gradient-to-r ${feature.color} bg-opacity-10 w-fit`}>
                    <IconComponent className="h-6 w-6 text-gray-700 dark:text-gray-300" />
                  </div>
                  <div className="flex flex-col sm:flex-row sm:items-center sm:space-x-2">
                    <CardTitle className="text-lg sm:text-xl">{feature.name}</CardTitle>
                    {!feature.enabled && <span className="text-xs bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200 px-2 py-1 rounded-full">Coming Soon</span>}
                  </div>
                </div>
              </CardHeader>
              <CardContent className="pb-6">
                <CardDescription className="text-sm sm:text-base mb-6">{feature.description}</CardDescription>
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
                  {isAuthenticated && feature.enabled ? (
                    <Button asChild variant="outline" size="sm" className="w-full sm:w-auto">
                      <Link href={feature.endpoint}>Launch</Link>
                    </Button>
                  ) : (
                    <Button variant="outline" size="sm" disabled={!feature.enabled} className="w-full sm:w-auto">
                      {!isAuthenticated ? <Link href="/auth/signin">Sign In</Link> : "Coming Soon"}
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
