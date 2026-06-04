import { useEffect, useState } from 'react'
import { Wifi, Smartphone, Settings, CheckCircle2 } from 'lucide-react'
import { cn } from '../lib/utils'
export function ConnectScreen() {
  const [status, setStatus] = useState<'waiting' | 'connected'>('waiting')
  // Simulate connection after a few seconds
  useEffect(() => {
    const timer = setTimeout(() => setStatus('connected'), 4000)
    return () => clearTimeout(timer)
  }, [])
  return (
    <div className="h-full flex flex-col p-6 space-y-8 overflow-y-auto max-w-5xl mx-auto w-full">
      <div className="text-center space-y-2 mt-4">
        <h1 className="text-3xl font-semibold text-[#E7EEE9]">
          Connect your R50
        </h1>
        <p className="text-[#8B978F]">
          Follow these steps to link your Garmin launch monitor.
        </p>
      </div>

      {/* Large Status Indicator */}
      <div className="flex justify-center py-8">
        <div
          className={cn(
            'relative w-48 h-48 rounded-full flex flex-col items-center justify-center border-4 transition-all duration-1000',
            status === 'connected'
              ? 'border-garage-green bg-garage-green/5 shadow-glow-primary'
              : 'border-garage-amber bg-garage-amber/5',
          )}
        >
          {status === 'waiting' && (
            <>
              <div className="absolute inset-0 rounded-full border-4 border-garage-amber animate-ping opacity-20" />
              <Wifi className="w-12 h-12 text-garage-amber mb-2 animate-pulse" />
              <span className="text-garage-amber font-medium text-sm">
                Waiting for R50...
              </span>
            </>
          )}
          {status === 'connected' && (
            <>
              <CheckCircle2 className="w-12 h-12 text-garage-green mb-2" />
              <span className="text-garage-green font-bold text-lg">
                Connected
              </span>
              <span className="text-garage-green/80 text-xs font-mono mt-1">
                Garmin-R50-8A2F
              </span>
            </>
          )}
        </div>
      </div>

      {/* 3-Step Wizard */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {[
          {
            step: 1,
            icon: Smartphone,
            title: 'On the R50',
            desc: "Tap 'Connect', then select 'GSPro' mode.",
          },
          {
            step: 2,
            icon: Wifi,
            title: 'Join Wi-Fi',
            desc: "Connect this PC to the R50's Wi-Fi network.",
          },
          {
            step: 3,
            icon: CheckCircle2,
            title: 'Take a Swing',
            desc: 'Shots will appear automatically once linked.',
          },
        ].map((s) => (
          <div
            key={s.step}
            className="bg-[#121714] border border-[#242C27] rounded-[24px] p-6 relative overflow-hidden"
          >
            <div className="text-[100px] font-bold text-[#1A211D] absolute -top-6 -right-4 leading-none select-none pointer-events-none">
              {s.step}
            </div>
            <div className="relative z-10">
              <div className="w-12 h-12 bg-[#1A211D] rounded-full flex items-center justify-center mb-4 border border-[#242C27]">
                <s.icon className="w-6 h-6 text-garage-green" />
              </div>
              <h3 className="text-lg font-semibold text-[#E7EEE9] mb-2">
                Step {s.step}: {s.title}
              </h3>
              <p className="text-[#8B978F] text-sm leading-relaxed">{s.desc}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Settings Card */}
      <div className="bg-[#121714] border border-[#242C27] rounded-[24px] p-6 mt-auto">
        <div className="flex items-center space-x-2 mb-6">
          <Settings className="w-5 h-5 text-[#8B978F]" />
          <h3 className="text-lg font-semibold text-[#E7EEE9]">
            Connection Settings
          </h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="flex flex-col space-y-2">
            <label className="text-xs uppercase tracking-wider text-[#8B978F] font-semibold">
              Idle Timeout (min)
            </label>
            <input
              type="number"
              defaultValue={15}
              className="bg-[#1A211D] border border-[#242C27] rounded-xl px-4 py-3 text-[#E7EEE9] focus:border-garage-green outline-none min-h-[44px]"
            />
          </div>
          <div className="flex flex-col space-y-2">
            <label className="text-xs uppercase tracking-wider text-[#8B978F] font-semibold">
              Units
            </label>
            <div className="flex bg-[#1A211D] border border-[#242C27] rounded-xl p-1 min-h-[44px]">
              <button className="flex-1 rounded-lg bg-[#242C27] text-[#E7EEE9] font-medium">
                Yards
              </button>
              <button className="flex-1 rounded-lg text-[#8B978F] hover:text-[#E7EEE9] font-medium">
                Meters
              </button>
            </div>
          </div>
          <div className="flex flex-col space-y-2">
            <label className="text-xs uppercase tracking-wider text-[#8B978F] font-semibold">
              Advanced: Port
            </label>
            <input
              type="text"
              defaultValue="921"
              className="bg-[#1A211D] border border-[#242C27] rounded-xl px-4 py-3 text-[#E7EEE9] focus:border-garage-green outline-none min-h-[44px] font-mono"
            />
          </div>
        </div>
      </div>
    </div>
  )
}
