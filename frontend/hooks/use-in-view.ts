"use client"

import type React from "react"

import { useEffect, useState } from "react"

export function useInView(ref: React.RefObject<HTMLElement>, options?: IntersectionObserverInit & { once?: boolean }) {
  const [isVisible, setIsVisible] = useState(false)
  const { once = false } = options || {}
  const observerOptions = options || {}

  useEffect(() => {
    if (!ref.current) return

    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        setIsVisible(true)
        if (once) {
          observer.unobserve(entry.target)
        }
      } else if (!once) {
        setIsVisible(false)
      }
    }, observerOptions)

    observer.observe(ref.current)

    return () => observer.disconnect()
  }, [ref, once])

  return isVisible
}
