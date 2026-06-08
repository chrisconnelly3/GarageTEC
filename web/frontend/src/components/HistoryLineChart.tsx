import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import { PinnedChartTooltip } from './ChartTooltip'
import { labelChangeTicks } from '../lib/format'

export interface HistoryDatum {
  idx: number
  date: string
  value: number
  swingId?: number
}

interface Props {
  data: HistoryDatum[]
  unit?: string
  decimals?: number
  /** Tour-pro reference value; renders a dashed benchmark line when present. */
  target?: number | null
  /** When set, the tap-to-pin tooltip shows an "Open swing" button. */
  onOpenSwing?: (id: number) => void
}

/** Shared trend chart for the History screen (body + ball). One point per shot,
 *  tap-to-pin tooltip (touch bay has no hover), one deduplicated date label per
 *  day, and a dashed tour-pro benchmark line. */
export function HistoryLineChart({ data, unit = '', decimals = 1, target, onOpenSwing }: Props) {
  const ticks = labelChangeTicks(data.map((d) => d.date))
  const firstTick = ticks[0]
  const lastTick = ticks[ticks.length - 1]

  // Anchor the first label to the start and the last to the end so edge labels
  // never spill past the chart's rounded container; middle labels stay centered.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const renderTick = ({ x, y, payload }: any) => {
    const anchor =
      payload.value === firstTick ? 'start' : payload.value === lastTick ? 'end' : 'middle'
    return (
      <text x={x} y={y} dy={14} textAnchor={anchor} fill="#8B978F" fontSize={12}>
        {data[payload.value]?.date ?? ''}
      </text>
    )
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ top: 20, right: 16, bottom: 4, left: -16 }}>
        <XAxis
          dataKey="idx"
          type="number"
          domain={[0, Math.max(0, data.length - 1)]}
          ticks={ticks}
          tick={renderTick}
          padding={{ left: 8, right: 8 }}
          stroke="#4A554E"
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          stroke="#4A554E"
          tick={{ fill: '#8B978F', fontSize: 12 }}
          tickLine={false}
          axisLine={false}
          // Keep the dashed tour benchmark in view even when it sits outside the
          // shot range (e.g. all swings well above the tour average).
          domain={
            target != null
              ? [(min: number) => Math.min(min, target), (max: number) => Math.max(max, target)]
              : ['auto', 'auto']
          }
        />
        <Tooltip
          // Touch bay: tap to pin a point's value (no hover exists).
          trigger="click"
          wrapperStyle={{ pointerEvents: 'auto', zIndex: 30 }}
          cursor={{ stroke: '#3A453E', strokeWidth: 2 }}
          content={(props) => (
            <PinnedChartTooltip {...props} unit={unit} decimals={decimals} onOpenSwing={onOpenSwing} />
          )}
        />
        {target != null && (
          <ReferenceLine y={target} stroke="#79BC30" strokeDasharray="6 6" strokeOpacity={0.6} />
        )}
        <Line
          type="monotone"
          dataKey="value"
          stroke="#79BC30"
          strokeWidth={4}
          dot={{ fill: '#0A0D0B', stroke: '#79BC30', strokeWidth: 2, r: 5 }}
          activeDot={{ r: 8, fill: '#79BC30', stroke: '#0A0D0B', strokeWidth: 3 }}
          style={{ filter: 'drop-shadow(0px 0px 8px rgba(121,188,48,0.25))' }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
