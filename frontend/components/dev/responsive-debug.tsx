'use client'

/**
 * Responsive Debug Component
 * Shows current breakpoint during development
 * Remove or hide in production
 */
export function ResponsiveDebug() {
  if (process.env.NODE_ENV === 'production') {
    return null
  }

  return (
    <div className="fixed bottom-4 left-4 z-50 bg-black/80 text-white text-xs px-2 py-1 rounded font-mono">
      <span className="sm:hidden">XS</span>
      <span className="hidden sm:block md:hidden">SM</span>
      <span className="hidden md:block lg:hidden">MD</span>
      <span className="hidden lg:block xl:hidden">LG</span>
      <span className="hidden xl:block 2xl:hidden">XL</span>
      <span className="hidden 2xl:block">2XL</span>
    </div>
  )
}