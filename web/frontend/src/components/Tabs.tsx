import React from 'react'
import { cn } from '../lib/utils'

// Lightweight Tabs primitive (MagicPatterns shipped this file empty).
// Provided for completeness; not currently consumed by any ported screen
// (the app uses local tab state in App.tsx rather than this component).
interface TabsProps {
  tabs: { id: string; label: string }[]
  activeTab: string
  onChange: (id: string) => void
  className?: string
}
export function Tabs({ tabs, activeTab, onChange, className }: TabsProps) {
  return (
    <div
      className={cn(
        'flex bg-[#121714] border border-[#242C27] rounded-full p-1',
        className,
      )}
    >
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={cn(
            'px-5 py-2 rounded-full text-sm font-medium transition-all min-h-[44px]',
            activeTab === tab.id
              ? 'bg-[#242C27] text-[#E7EEE9]'
              : 'text-[#8B978F] hover:text-[#E7EEE9]',
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}
