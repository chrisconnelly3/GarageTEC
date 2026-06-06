import {
  CheckCircle2,
  AlertCircle,
  Target,
  Activity,
  ArrowRight,
  Zap,
} from 'lucide-react'
import { cn } from '../lib/utils'
import { motion } from 'framer-motion'
interface Insight {
  id: string
  type: 'mechanic' | 'power' | 'timing' | 'warning'
  text: string
  metric: string
  drill: string
  severity: 'good' | 'neutral' | 'bad'
}
interface AIInsightCardProps {
  headline: string
  summary?: string | null
  insights: Insight[]
  highlight?: boolean
}
export function AIInsightCard({
  headline,
  summary,
  insights,
  highlight,
}: AIInsightCardProps) {
  const getTypeConfig = (type: Insight['type']) => {
    switch (type) {
      case 'mechanic':
        return {
          icon: Target,
          color: 'text-garage-blue',
          bg: 'bg-garage-blue/10',
        }
      case 'power':
        return {
          icon: Zap,
          color: 'text-garage-amber',
          bg: 'bg-garage-amber/10',
        }
      case 'timing':
        return {
          icon: Activity,
          color: 'text-garage-magenta',
          bg: 'bg-garage-magenta/10',
        }
      case 'warning':
        return {
          icon: AlertCircle,
          color: 'text-garage-red',
          bg: 'bg-garage-red/10',
        }
    }
  }
  return (
    <motion.div
      initial={{
        opacity: 0,
        scale: 0.98,
      }}
      animate={{
        opacity: 1,
        scale: 1,
      }}
      className={cn(
        'bg-[#1A211D] border rounded-[18px] p-6 h-full flex flex-col relative overflow-hidden',
        highlight
          ? 'border-garage-green/50 shadow-glow-primary-sm'
          : 'border-[#242C27]',
      )}
    >
      <div className="flex items-center space-x-2 mb-4 flex-shrink-0">
        <div className="w-2 h-2 rounded-full bg-garage-green shadow-glow-primary-sm animate-pulse" />
        <span className="text-[11px] uppercase tracking-[0.15em] text-garage-green font-bold">
          AI Coach Read
        </span>
      </div>

      {/* Page never scrolls; this card scrolls internally when the note is long. */}
      <div className="flex-1 min-h-0 overflow-y-auto pr-1">
      <h3 className="text-xl font-semibold text-[#E7EEE9] leading-tight">
        {headline}
      </h3>

      {summary && (
        <p className="mt-3 text-sm text-[#C7D2CB] leading-relaxed">
          {summary}
        </p>
      )}

      <div className="space-y-4 mt-5">
        {insights.map((insight) => {
          const config = getTypeConfig(insight.type)
          const Icon = config.icon
          return (
            <div key={insight.id} className="flex items-start space-x-3 group">
              <div
                className={cn(
                  'p-1.5 rounded-lg mt-0.5',
                  config.bg,
                  config.color,
                )}
              >
                <Icon className="w-4 h-4" />
              </div>
              <div className="flex-1">
                <div className="flex items-center justify-between mb-1">
                  <p className="text-sm text-[#E7EEE9] font-medium">
                    {insight.text}
                  </p>
                  {insight.severity === 'good' && (
                    <CheckCircle2 className="w-4 h-4 text-garage-green" />
                  )}
                  {insight.severity === 'bad' && (
                    <div className="w-2 h-2 rounded-full bg-garage-red" />
                  )}
                </div>
                <div className="flex items-center space-x-2 text-xs">
                  <span className="text-[#8B978F] bg-[#121714] px-1.5 py-0.5 rounded font-mono">
                    {insight.metric}
                  </span>
                  <ArrowRight className="w-3 h-3 text-[#4A554E]" />
                  <span className="text-garage-green/80 group-hover:text-garage-green transition-colors cursor-pointer">
                    Drill: {insight.drill}
                  </span>
                </div>
              </div>
            </div>
          )
        })}
      </div>
      </div>
    </motion.div>
  )
}
