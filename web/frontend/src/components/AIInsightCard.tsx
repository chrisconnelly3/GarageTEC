import { cn } from '../lib/utils'
import { motion } from 'framer-motion'

interface AIInsightCardProps {
  headline: string
  summary?: string | null
  highlight?: boolean
}

/**
 * The coach read: a one-line headline verdict plus a short body that calls out
 * only the top two or three "worst offender" metrics. The per-metric numbers
 * live on the body/ball cards, so this card intentionally carries no bullet
 * list or drill chips — just the human read.
 */
export function AIInsightCard({ headline, summary, highlight }: AIInsightCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      className={cn(
        'bg-[#1A211D] border rounded-[18px] p-6 h-full flex flex-col relative overflow-hidden',
        highlight ? 'border-garage-green/50 shadow-glow-primary-sm' : 'border-[#242C27]',
      )}
    >
      <div className="flex items-center space-x-2 mb-4 flex-shrink-0">
        <div className="w-2 h-2 rounded-full bg-garage-green shadow-glow-primary-sm animate-pulse" />
        <span className="text-[11px] uppercase tracking-[0.15em] text-garage-green font-bold">
          AI Coach Read
        </span>
      </div>

      {/* Page never scrolls; this card scrolls internally when the read is long. */}
      <div className="flex-1 min-h-0 overflow-y-auto pr-1">
        <h3 className="text-lg font-semibold text-[#E7EEE9] leading-snug">
          {headline}
        </h3>

        {summary && (
          <p className="mt-3 text-sm text-[#C7D2CB] leading-relaxed">
            {summary}
          </p>
        )}
      </div>
    </motion.div>
  )
}
