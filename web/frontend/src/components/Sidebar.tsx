import {
  Activity,
  History,
  Users,
  RefreshCw,
  Settings,
  Calendar,
} from 'lucide-react'
import { cn } from '../lib/utils'
interface SidebarProps {
  activeTab: string
  setActiveTab: (tab: string) => void
  r50Error?: boolean
}
export function Sidebar({ activeTab, setActiveTab, r50Error }: SidebarProps) {
  const navItems = [
    {
      id: 'swing',
      label: 'Swing',
      icon: Activity,
    },
    {
      id: 'history',
      label: 'History',
      icon: History,
    },
    {
      id: 'sessions',
      label: 'Sessions',
      icon: Calendar,
    },
    {
      id: 'players',
      label: 'Players',
      icon: Users,
    },
    {
      id: 'sync',
      label: 'Sync',
      icon: RefreshCw,
    },
  ]
  return (
    <div className="w-16 h-screen bg-[#0A0D0B] border-r border-[#242C27] flex flex-col pt-6 pb-8 px-2 flex-shrink-0">
      <nav className="flex-1 space-y-2">
        {navItems.map((item) => {
          const Icon = item.icon
          const isActive = activeTab === item.id
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              title={item.label}
              aria-label={item.label}
              aria-current={isActive ? 'page' : undefined}
              className={cn(
                'w-full flex items-center justify-center py-3.5 rounded-xl transition-all duration-200 min-h-[44px] relative focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-garage-green/60',
                isActive
                  ? 'bg-garage-green/10 text-garage-green'
                  : 'text-[#8B978F] hover:bg-[#1A211D] hover:text-[#E7EEE9]',
              )}
            >
              {isActive && (
                <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-garage-green rounded-full" />
              )}
              <Icon className="w-5 h-5" strokeWidth={isActive ? 2.5 : 2} />
            </button>
          )
        })}
      </nav>

      <div className="pt-4 border-t border-[#242C27]">
        <button
          onClick={() => setActiveTab('connect')}
          title="Connect / Settings"
          aria-label="Connect / Settings"
          aria-current={activeTab === 'connect' ? 'page' : undefined}
          className={cn(
            'w-full flex items-center justify-center py-3.5 rounded-xl transition-all duration-200 min-h-[44px] relative focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-garage-green/60',
            activeTab === 'connect'
              ? 'bg-garage-green/10 text-garage-green'
              : 'text-[#8B978F] hover:bg-[#1A211D] hover:text-[#E7EEE9]',
          )}
        >
          {activeTab === 'connect' && (
            <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-garage-green rounded-full" />
          )}
          <Settings
            className="w-5 h-5"
            strokeWidth={activeTab === 'connect' ? 2.5 : 2}
          />
          {r50Error && (
            <span className="absolute top-2 right-2 w-2.5 h-2.5 rounded-full bg-garage-red ring-2 ring-[#0A0D0B]"
              aria-label="R50 connection problem" />
          )}
        </button>
      </div>
    </div>
  )
}
