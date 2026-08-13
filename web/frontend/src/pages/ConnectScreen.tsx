import { useEffect, useState } from 'react'
import { Wifi, Settings, CheckCircle2, Eye, EyeOff } from 'lucide-react'
import { cn } from '../lib/utils'
import { useApi } from '../lib/useApi'
import { getSettings, putSettings, restartCapture, getSetupInfo } from '../lib/api'
import type { CaptureStatus } from '../lib/types'
import { CalibrationCard } from '../components/CalibrationCard'
import { LiveCaptureCard } from '../components/LiveCaptureCard'
import { MonitorSetupCards } from '../components/MonitorSetupCards'

interface ConnectScreenProps {
  captureStatus: CaptureStatus | null
}

export function ConnectScreen({ captureStatus }: ConnectScreenProps) {
  const status: 'waiting' | 'connected' = captureStatus?.connected
    ? 'connected'
    : 'waiting'

  const { data: settings, reload: reloadSettings } = useApi(getSettings, [])
  const { data: setupInfo } = useApi(getSetupInfo, [])
  const [idleTimeout, setIdleTimeout] = useState('15')
  const [units, setUnits] = useState<'Yards' | 'Meters'>('Yards')
  const [port, setPort] = useState('921')
  const [saved, setSaved] = useState(false)

  // AI coach API key
  const [apiKeyInput, setApiKeyInput] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [keyStatus, setKeyStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const [keyError, setKeyError] = useState('')

  useEffect(() => {
    if (settings) {
      setIdleTimeout(String(settings.idle_minutes))
      setUnits(settings.units === 'meters' ? 'Meters' : 'Yards')
      setPort(String(settings.port))
    }
  }, [settings])

  const onSave = () => {
    const nextPort = parseInt(port || '921', 10) || 921
    putSettings({
      idle_minutes: parseInt(idleTimeout || '15', 10) || 15,
      units: units === 'Meters' ? 'meters' : 'yards',
      port: nextPort,
    })
      .then(() => {
        setSaved(true)
        setTimeout(() => setSaved(false), 2000)
        // A port change only binds on the next listener spawn, so restart it.
        if (settings && nextPort !== settings.port) {
          restartCapture().catch(() => {})
        }
      })
      .catch(() => {})
  }

  const onSaveKey = () => {
    if (!apiKeyInput) return
    setKeyStatus('saving')
    putSettings({ anthropic_api_key: apiKeyInput })
      .then(() => {
        setApiKeyInput('')
        setKeyStatus('saved')
        reloadSettings()
        setTimeout(() => setKeyStatus('idle'), 2500)
      })
      .catch((e) => {
        setKeyStatus('error')
        setKeyError(String(e?.message || e))
      })
  }

  const onRemoveKey = () => {
    putSettings({ anthropic_api_key: '' })
      .then(() => { reloadSettings(); setKeyStatus('idle') })
      .catch(() => {})
  }

  const connectedLabel = captureStatus?.openflight_host
    ? 'OpenFlight connected'
    : 'Launch monitor connected'

  return (
    <div className="h-full flex flex-col p-6 space-y-8 overflow-y-auto max-w-5xl mx-auto w-full">
      <div className="text-center space-y-2 mt-4">
        <h1 className="text-3xl font-semibold text-[#E7EEE9]">
          Connect your launch monitor
        </h1>
        <p className="text-[#8B978F]">
          GarageTEC works with either a Garmin R50 or an OpenFlight radar —
          it detects automatically which one is connected. Follow the setup
          card below for the monitor you own.
        </p>
      </div>

      {/* Large Status Indicator */}
      <div className="flex flex-col items-center py-8">
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
              {/* px-6 + balance keeps the longest label inside the circle. */}
              <span className="text-garage-amber font-medium text-sm text-center px-6 text-balance leading-tight">
                {captureStatus?.status === 'paused'
                  ? 'Launch monitor paused'
                  : 'Waiting for a launch monitor…'}
              </span>
            </>
          )}
          {status === 'connected' && (
            <>
              <CheckCircle2 className="w-12 h-12 text-garage-green mb-2" />
              <span className="text-garage-green font-bold text-lg">
                {connectedLabel}
              </span>
              <span className="text-garage-green/80 text-xs font-mono mt-1">
                {captureStatus?.shot_count ?? 0} shots
              </span>
            </>
          )}
        </div>
        {captureStatus?.last_error && (
          <p className="text-xs text-garage-red mt-4">
            {captureStatus.last_error}
          </p>
        )}
        {captureStatus?.openflight_host && (
          <div className="flex items-center gap-2 text-sm mt-4">
            <span className={cn('w-2 h-2 rounded-full',
              captureStatus.enrichment_status === 'connected'
                ? 'bg-garage-green' : 'bg-garage-amber')} />
            <span className="text-[#8B978F]">
              OpenFlight enrichment:{' '}
              <span className="text-[#E7EEE9]">
                {captureStatus.enrichment_status === 'connected'
                  ? `connected (${captureStatus.openflight_host})`
                  : 'not connected — measured/estimated detail unavailable'}
              </span>
            </span>
          </div>
        )}
      </div>

      {/* Per-monitor setup cards */}
      <MonitorSetupCards setupInfo={setupInfo} />

      {/* AI Coach */}
      <div className="bg-[#121714] border border-[#242C27] rounded-[24px] p-6 space-y-4">
        <h3 className="text-lg font-semibold text-[#E7EEE9]">AI Coach</h3>
        <p className="text-sm text-[#8B978F]">
          The AI coach is optional — capture, metrics, tour benchmarks, and
          trends all work without it. Turning it on needs your own personal
          Anthropic API key, and usage is billed to whoever owns that key.
        </p>

        {settings?.has_api_key ? (
          <div className="space-y-3">
            <p className="text-sm text-[#E7EEE9]">
              Key saved:{' '}
              <span className="font-mono text-[#8B978F]">{settings.api_key_hint}</span>
            </p>
            <button
              onClick={onRemoveKey}
              className="px-4 py-2 rounded-xl bg-[#1A211D] border border-[#242C27] text-[#E7EEE9] min-h-[44px] hover:brightness-110 transition"
            >
              Remove
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <label className="text-xs uppercase tracking-wider text-[#8B978F] font-semibold">
              Anthropic API key
            </label>
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="relative flex-1">
                <input
                  type={showKey ? 'text' : 'password'}
                  value={apiKeyInput}
                  onChange={(e) => setApiKeyInput(e.target.value)}
                  placeholder="sk-ant-…"
                  className="w-full bg-[#1A211D] border border-[#242C27] rounded-xl pl-4 pr-12 py-3 text-[#E7EEE9] focus:border-garage-green outline-none min-h-[44px] font-mono"
                />
                <button
                  onClick={() => setShowKey((s) => !s)}
                  aria-label={showKey ? 'Hide key' : 'Show key'}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-2 text-[#8B978F] hover:text-[#E7EEE9] min-h-[36px] min-w-[36px]"
                >
                  {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              <button
                onClick={onSaveKey}
                disabled={!apiKeyInput || keyStatus === 'saving'}
                className="bg-garage-green text-[#0A0D0B] font-semibold rounded-xl px-6 py-3 min-h-[44px] hover:brightness-110 transition disabled:opacity-40"
              >
                {keyStatus === 'saving' ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        )}

        {keyStatus === 'saved' && (
          <p className="text-sm text-garage-green">AI coach enabled</p>
        )}
        {keyStatus === 'error' && (
          <p className="text-sm text-garage-red">{keyError}</p>
        )}

        <div className="text-xs text-[#8B978F] space-y-1 pt-2 border-t border-[#242C27]">
          <p className="font-semibold text-[#8B978F]">How to get a key</p>
          <ol className="list-decimal list-inside space-y-0.5">
            <li>
              Go to{' '}
              <span className="font-mono text-[#E7EEE9] select-all">
                console.anthropic.com
              </span>
            </li>
            <li>Sign in</li>
            <li>Open &apos;API keys&apos;</li>
            <li>Click &apos;Create key&apos;</li>
            <li>Copy it, then paste it above</li>
          </ol>
        </div>
      </div>

      {/* Settings Card */}
      <div className="bg-[#121714] border border-[#242C27] rounded-[24px] p-6">
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
              value={idleTimeout}
              onChange={(e) => setIdleTimeout(e.target.value)}
              className="bg-[#1A211D] border border-[#242C27] rounded-xl px-4 py-3 text-[#E7EEE9] focus:border-garage-green outline-none min-h-[44px]"
            />
          </div>
          <div className="flex flex-col space-y-2">
            <label className="text-xs uppercase tracking-wider text-[#8B978F] font-semibold">
              Units
            </label>
            <div className="flex bg-[#1A211D] border border-[#242C27] rounded-xl p-1 min-h-[44px]">
              <button
                onClick={() => setUnits('Yards')}
                className={cn(
                  'flex-1 rounded-lg font-medium',
                  units === 'Yards'
                    ? 'bg-[#242C27] text-[#E7EEE9]'
                    : 'text-[#8B978F] hover:text-[#E7EEE9]',
                )}
              >
                Yards
              </button>
              <button
                onClick={() => setUnits('Meters')}
                className={cn(
                  'flex-1 rounded-lg font-medium',
                  units === 'Meters'
                    ? 'bg-[#242C27] text-[#E7EEE9]'
                    : 'text-[#8B978F] hover:text-[#E7EEE9]',
                )}
              >
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
              value={port}
              onChange={(e) => setPort(e.target.value)}
              className="bg-[#1A211D] border border-[#242C27] rounded-xl px-4 py-3 text-[#E7EEE9] focus:border-garage-green outline-none min-h-[44px] font-mono"
            />
          </div>
        </div>

        <div className="flex justify-end mt-6">
          <button
            onClick={onSave}
            className="bg-garage-green text-[#0A0D0B] font-semibold rounded-xl px-6 py-3 min-h-[44px] hover:brightness-110 transition"
          >
            {saved ? 'Saved ✓' : 'Save Settings'}
          </button>
        </div>
      </div>

      <CalibrationCard />
      <LiveCaptureCard />
    </div>
  )
}
