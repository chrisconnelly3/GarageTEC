export function BallClubStrip() {
  const stats = [
    {
      label: 'Ball Speed',
      value: '162',
      unit: 'mph',
    },
    {
      label: 'Spin',
      value: '2450',
      unit: 'rpm',
    },
    {
      label: 'Launch',
      value: '12.4',
      unit: 'deg',
    },
    {
      label: 'Carry',
      value: '284',
      unit: 'yds',
    },
    {
      label: 'Club Speed',
      value: '112',
      unit: 'mph',
    },
    {
      label: 'Path',
      value: '2.1',
      unit: 'In-Out',
    },
    {
      label: 'Face',
      value: '1.5',
      unit: 'Open',
    },
    {
      label: 'AoA',
      value: '+2.4',
      unit: 'deg',
    },
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
