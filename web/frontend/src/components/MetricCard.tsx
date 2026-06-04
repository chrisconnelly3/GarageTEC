import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react'
import { cn } from '../lib/utils'
import { motion } from 'framer-motion'
interface MetricCardProps {
  name: string
  value: string | number
  unit: string
  delta: number // positive is up, negative is down
  deltaGood: 'up' | 'down' | 'neutral' // which direction is good
  idealRange: [number, number]
  currentNum: number
  isEstimated?: boolean
  highlight?: boolean
}
export function MetricCard({
  name,
  value,
  unit,
  delta,
  deltaGood,
  idealRange,
  currentNum,
  isEstimated,
  highlight,
}: MetricCardProps) {
  const isGood =
    deltaGood === 'up' ? delta > 0 : deltaGood === 'down' ? delta < 0 : true
  const isNeutral = delta === 0
  // Calculate position on ideal bar (0 to 100%)
  const min = idealRange[0] - Math.abs(idealRange[0] * 0.5)
  const max = idealRange[1] + Math.abs(idealRange[1] * 0.5)
  const range = max - min
  const position = Math.max(
    0,
    Math.min(100, ((currentNum - min) / range) * 100),
  )
  const idealStart = Math.max(0, ((idealRange[0] - min) / range) * 100)
  const idealWidth = Math.min(
    100,
    ((idealRange[1] - idealRange[0]) / range) * 100,
  )
  return (
    <motion.div
      initial={{
        opacity: 0,
        y: 10,
      }}
      animate={{
        opacity: 1,
        y: 0,
      }}
      className={cn(
        'bg-[#121714] border rounded-[18px] p-5 flex flex-col justify-between relative overflow-hidden transition-all duration-500',
        highlight
          ? 'border-garage-green shadow-glow-primary-sm'
          : 'border-[#242C27]',
      )}
    >
      {highlight && (
        <div className="absolute top-0 left-0 w-full h-full bg-garage-green/5 pointer-events-none" />
      )}

      <div className="flex justify-between items-start mb-2">
        <div className="flex items-center space-x-2">
          <span className="text-[10px] uppercase tracking-[0.1em] text-[#8B978F] font-semibold">
            {name}
          </span>
          {isEstimated && (
            <span className="text-[9px] bg-[#1A211D] text-[#8B978F] px-1.5 py-0.5 rounded uppercase tracking-wider">
              ~est.
            </span>
          )}
        </div>

        {!isNeutral && (
          <div
            className={cn(
              'flex items-center text-xs font-medium px-1.5 py-0.5 rounded',
              isGood
                ? 'text-garage-green bg-garage-green/10'
                : 'text-garage-red bg-garage-red/10',
            )}
          >
            {delta > 0 ? (
              <ArrowUpRight className="w-3 h-3 mr-0.5" />
            ) : (
              <ArrowDownRight className="w-3 h-3 mr-0.5" />
            )}
            {Math.abs(delta)}
          </div>
        )}
        {isNeutral && (
          <div className="flex items-center text-xs font-medium px-1.5 py-0.5 rounded text-[#8B978F] bg-[#1A211D]">
            <Minus className="w-3 h-3 mr-0.5" />0
          </div>
        )}
      </div>

      <div className="flex items-baseline space-x-1 mb-4">
        <span className="text-3xl font-bold tracking-tight font-mono text-[#E7EEE9]">
          {value}
        </span>
        <span className="text-sm text-[#8B978F] font-medium">{unit}</span>
      </div>

      <div className="mt-auto">
        <div className="flex justify-between text-[10px] text-[#8B978F] mb-1.5">
          <span>vs ideal</span>
        </div>
        <div className="h-1.5 w-full bg-[#1A211D] rounded-full relative overflow-hidden">
          {/* Ideal Range Indicator */}
          <div
            className="absolute h-full bg-[#242C27] rounded-full"
            style={{
              left: `${idealStart}%`,
              width: `${idealWidth}%`,
            }}
          />
          {/* Current Value Marker */}
          <div
            className={cn(
              'absolute h-full w-1.5 rounded-full shadow-[0_0_8px_rgba(132,206,57,0.8)]',
              highlight ? 'bg-garage-green' : 'bg-[#E7EEE9]',
            )}
            style={{
              left: `calc(${position}% - 3px)`,
            }}
          />
        </div>
      </div>
    </motion.div>
  )
}
