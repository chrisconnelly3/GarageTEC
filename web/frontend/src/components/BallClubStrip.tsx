import type { Shot } from '../lib/types'

interface BallClubStripProps {
  shot?: Shot | null
}

const fmt = (v: number | null | undefined, digits = 1, prefixSign = false) => {
  if (v == null) return '--'
  const rounded = digits === 0 ? Math.round(v) : Number(v.toFixed(digits))
  return prefixSign && rounded > 0 ? `+${rounded}` : `${rounded}`
}

export function BallClubStrip({ shot = null }: BallClubStripProps) {
  const stats = [
    { label: 'Ball Speed', value: fmt(shot?.ball_speed), unit: 'mph' },
    { label: 'Spin', value: fmt(shot?.total_spin, 0), unit: 'rpm' },
    { label: 'Launch', value: fmt(shot?.vla), unit: 'deg' },
    { label: 'Carry', value: fmt(shot?.carry), unit: 'yds' },
    { label: 'Club Speed', value: fmt(shot?.club_speed), unit: 'mph' },
    { label: 'Path', value: fmt(shot?.club_path), unit: 'In-Out' },
    { label: 'Face', value: fmt(shot?.face_to_target), unit: 'Open' },
    { label: 'AoA', value: fmt(shot?.attack_angle, 1, true), unit: 'deg' },
  ]
  return (
    <div className="w-full bg-[#121714] border border-[#242C27] rounded-[18px] py-3 px-6 flex items-center justify-between overflow-x-auto no-scrollbar">
      {stats.map((stat, i) => (
        <div
          key={i}
          className="flex flex-col items-center px-4 first:pl-0 last:pr-0 border-r border-[#242C27] last:border-0 min-w-[80px]"
        >
          <span className="text-[9px] uppercase tracking-wider text-[#8B978F] mb-1">
            {stat.label}
          </span>
          <div className="flex items-baseline space-x-1">
            <span className="text-sm font-mono font-semibold text-[#E7EEE9]">
              {stat.value}
            </span>
            <span className="text-[10px] text-[#4A554E]">{stat.unit}</span>
          </div>
        </div>
      ))}
    </div>
  )
}
