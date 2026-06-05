import {
  Activity,
  History,
  Users,
  RefreshCw,
  Settings,
  Video,
  Calendar,
} from 'lucide-react'
import { cn } from '../lib/utils'
interface SidebarProps {
  activeTab: string
  setActiveTab: (tab: string) => void
}
export function Sidebar({ activeTab, setActiveTab }: SidebarProps) {
  const navItems = [
    {
      id: 'live',
      label: 'Live',
      icon: Activity,
    },
    {
      id: 'review',
      label: 'Review',
      icon: Video,
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
    <div className="w-64 h-screen bg-[#0A0D0B] border-r border-[#242C27] flex flex-col pt-6 pb-8 px-4 flex-shrink-0">
      <div className="mb-10 px-1">
        <img
          src="/garagetec-logo.png"
          alt="GarageTEC"
          className="w-full max-w-[200px] object-contain"
        />
      </div>

      <nav className="flex-1 space-y-2">
        {navItems.map((item) => {
          const Icon = item.icon
          const isActive = activeTab === item.id
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={cn(
                'w-full flex items-center space-x-3 px-4 py-3.5 rounded-full transition-all duration-200 text-left min-h-[44px]',
                isActive
                  ? 'bg-garage-green/10 text-garage-green shadow-glow-primary-sm'
                  : 'text-[#8B978F] hover:bg-[#1A211D] hover:text-[#E7EEE9]',
              )}
            >
              <Icon className="w-5 h-5" strokeWidth={isActive ? 2.5 : 2} />
              <span className="font-medium text-[15px]">{item.label}</span>
            </button>
          )
        })}
      </nav>

      <div className="pt-4 border-t border-[#242C27]">
        <button
          onClick={() => setActiveTab('connect')}
          className={cn(
            'w-full flex items-center space-x-3 px-4 py-3.5 rounded-full transition-all duration-200 text-left min-h-[44px]',
            activeTab === 'connect'
              ? 'bg-garage-green/10 text-garage-green shadow-glow-primary-sm'
              : 'text-[#8B978F] hover:bg-[#1A211D] hover:text-[#E7EEE9]',
          )}
        >
          <Settings
            className="w-5 h-5"
            strokeWidth={activeTab === 'connect' ? 2.5 : 2}
          />
          <span className="font-medium text-[15px]">Connect / Settings</span>
        </button>
      </div>
    </div>
  )
}
