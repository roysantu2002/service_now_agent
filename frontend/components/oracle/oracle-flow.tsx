"use client"

import { useInView } from "@/hooks/use-in-view"
import { useEffect, useRef, useState } from "react"

const stepColors = {
  1: { bg: "from-cyan-500/10 to-cyan-500/5", border: "border-cyan-500", dot: "bg-cyan-500", text: "text-cyan-400" },
  2: { bg: "from-blue-500/10 to-blue-500/5", border: "border-blue-500", dot: "bg-blue-500", text: "text-blue-400" },
  3: {
    bg: "from-purple-500/10 to-purple-500/5",
    border: "border-purple-500",
    dot: "bg-purple-500",
    text: "text-purple-400",
  },
}

const steps = [
  {
    number: "1",
    title: "Awareness",
    description:
      "AI continuously monitors tickets, logs, and alerts to detect patterns, sentiment, urgency, and intent—so you know exactly what needs attention first.",
    icon: "👁️",
  },
  {
    number: "2",
    title: "Reasoning",
    description:
      "Evaluate root causes, cluster similar issues, recommend resolutions, and learn from every outcome to refine future predictions.",
    icon: "🧠",
  },
  {
    number: "3",
    title: "Collaboration",
    description:
      "AI co-pilots with your team—drafting responses, triggering workflows, and auto-resolving eligible tasks while humans stay in control.",
    icon: "🤝",
  },
]

type VerticalTimelineStepProps = {
  step: (typeof steps)[0]
  index: number
  isVisible: boolean
  registerCircleRef: (el: HTMLDivElement | null) => void
}

function VerticalTimelineStep({
  step,
  index,
  isVisible,
  registerCircleRef,
}: VerticalTimelineStepProps) {
  const isLeft = index % 2 === 0
  const colors = stepColors[step.number as unknown as keyof typeof stepColors]

  return (
    <div className="flex items-stretch gap-8 mb-8 lg:mb-12">
      {/* Left content (even steps) */}
      <div
        className={`flex-1 ${isLeft ? "flex flex-col justify-center" : "hidden lg:flex lg:flex-col lg:justify-center"}`}
      >
        {isLeft && (
          <div
            className={`rounded-xl p-6 sm:p-8 border-2 transition-all duration-700 transform ${
              isVisible ? "opacity-100 translate-x-0" : "opacity-0 -translate-x-8"
            } ${colors.border} bg-gradient-to-br ${colors.bg}`}
            style={{ transitionDelay: `${index * 100}ms` }}
          >
            <div className="flex items-start gap-3 mb-4">
              <div className="text-2xl">{step.icon}</div>
              <div className="flex-1">
                <h3 className={`text-lg sm:text-xl font-bold mb-1 ${colors.text}`}>{step.title}</h3>
                <p className={`text-xs sm:text-sm font-medium text-muted-foreground`}>Step {step.number}</p>
              </div>
            </div>
            <p className="text-sm leading-relaxed text-muted-foreground">{step.description}</p>
          </div>
        )}
      </div>

      {/* Center timeline (circle + horizontal connector; vertical line is drawn globally) */}
      <div className="hidden lg:flex lg:flex-col lg:items-center lg:w-20">
        <div
          className={`relative transition-all duration-500 transform ${
            isVisible ? "scale-100 opacity-100" : "scale-75 opacity-0"
          }`}
          style={{ transitionDelay: `${index * 100}ms` }}
        >
          {/* Circle with ref so we can measure its position */}
          <div
            ref={registerCircleRef}
            className={`w-14 h-14 rounded-full flex items-center justify-center font-bold text-lg border-4 ${colors.dot} text-background border-current shadow-lg`}
          >
            {step.number}
          </div>

          {/* Horizontal connector from circle to card */}
          <div
            className={`absolute top-1/2 -translate-y-1/2 h-0.5 w-10 ${colors.dot} ${
              isLeft ? "right-full" : "left-full"
            }`}
          />
        </div>
      </div>

      {/* Right content (odd steps) */}
      <div
        className={`flex-1 ${!isLeft ? "flex flex-col justify-center" : "hidden lg:flex lg:flex-col lg:justify-center"}`}
      >
        {!isLeft && (
          <div
            className={`rounded-xl p-6 sm:p-8 border-2 transition-all duration-700 transform ${
              isVisible ? "opacity-100 translate-x-0" : "opacity-0 translate-x-8"
            } ${colors.border} bg-gradient-to-br ${colors.bg}`}
            style={{ transitionDelay: `${index * 100}ms` }}
          >
            <div className="flex items-start gap-3 mb-4">
              <div className="text-2xl">{step.icon}</div>
              <div className="flex-1">
                <h3 className={`text-lg sm:text-xl font-bold mb-1 ${colors.text}`}>{step.title}</h3>
                <p className={`text-xs sm:text-sm font-medium text-muted-foreground`}>Step {step.number}</p>
              </div>
            </div>
            <p className="text-sm leading-relaxed text-muted-foreground">{step.description}</p>
          </div>
        )}
      </div>
    </div>
  )
}

export function OracleFlow() {
  const headerRef = useRef<HTMLDivElement | null>(null)
  const timelineRef = useRef<HTMLDivElement | null>(null)
  const circleRefs = useRef<(HTMLDivElement | null)[]>([])
  const [lineBounds, setLineBounds] = useState<{ top: number; height: number } | null>(null)

  const isVisible = useInView(headerRef, { once: true, rootMargin: "-100px" })

  useEffect(() => {
    if (!timelineRef.current) return
    if (!circleRefs.current.length) return

    const updateLine = () => {
      const container = timelineRef.current
      if (!container) return

      const containerRect = container.getBoundingClientRect()
      const validCircles = circleRefs.current.filter((el): el is HTMLDivElement => !!el)

      if (validCircles.length === 0) return

      const firstRect = validCircles[0].getBoundingClientRect()
      const lastRect = validCircles[validCircles.length - 1].getBoundingClientRect()

      const top = firstRect.top + firstRect.height / 2 - containerRect.top
      const bottom = lastRect.top + lastRect.height / 2 - containerRect.top

      setLineBounds({
        top,
        height: bottom - top,
      })
    }

    updateLine()
    window.addEventListener("resize", updateLine)

    return () => window.removeEventListener("resize", updateLine)
  }, [isVisible])

  return (
    <section id="framework" className="py-24 px-4 sm:px-6 lg:px-8 bg-card/30">
      <div className="max-w-6xl mx-auto">
        {/* Section header */}
        <div className="text-center mb-16" ref={headerRef}>
          <h2 className="text-4xl sm:text-5xl font-bold mb-4 text-balance">The ARC Framework</h2>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Watch how every request flows through three intelligent phases—Awareness, Reasoning, and Collaboration—
            aligning AI and humans around what truly matters.
          </p>
        </div>

        {/* Desktop: Vertical timeline with alternating left-right layout */}
        <div ref={timelineRef} className="relative hidden lg:block">
          {/* Vertical line from center of step 1 circle to center of step 3 circle */}
          {lineBounds && (
            <div
              className="absolute left-1/2 w-1 bg-muted-foreground/30 -translate-x-1/2 rounded-full"
              style={{ top: lineBounds.top, height: lineBounds.height }}
            />
          )}

          {steps.map((step, index) => (
            <VerticalTimelineStep
              key={step.number}
              step={step}
              index={index}
              isVisible={isVisible}
              registerCircleRef={(el) => {
                circleRefs.current[index] = el
              }}
            />
          ))}
        </div>

        {/* Mobile/Tablet: Vertical stack */}
        <div className="lg:hidden space-y-6">
          {steps.map((step, index) => {
            const colors = stepColors[step.number as unknown as keyof typeof stepColors]

            return (
              <div
                key={step.number}
                className={`rounded-xl p-6 border-2 transition-all duration-700 transform ${
                  isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
                } ${colors.border} bg-gradient-to-br ${colors.bg}`}
                style={{ transitionDelay: `${index * 100}ms` }}
              >
                <div className="flex items-start gap-3 mb-4">
                  <div className="text-xl">{step.icon}</div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <div
                        className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm border-2 ${colors.dot} text-background`}
                      >
                        {step.number}
                      </div>
                      <h3 className={`text-lg font-bold ${colors.text}`}>{step.title}</h3>
                    </div>
                  </div>
                </div>
                <p className="text-sm text-muted-foreground">{step.description}</p>
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
