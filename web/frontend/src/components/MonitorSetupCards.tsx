// web/frontend/src/components/MonitorSetupCards.tsx
// Per-monitor setup guidance for the Connect screen. GarageTEC never asks the
// user which monitor they have — it detects that from the DeviceID on the
// wire — so both cards are always shown, side by side, and the user just
// reads the one that matches their hardware.
import { useState } from 'react'
import { Wifi, Smartphone, AlertTriangle, Copy } from 'lucide-react'
import type { SetupInfo } from '../lib/types'

export function MonitorSetupCards({ setupInfo }: { setupInfo: SetupInfo | null }) {
  const [copied, setCopied] = useState(false)

  const onCopyConnector = () => {
    if (!setupInfo) return
    navigator.clipboard
      .writeText(JSON.stringify(setupInfo.openflight_connector, null, 2))
      .then(() => {
        setCopied(true)
        setTimeout(() => setCopied(false), 1500)
      })
      .catch(() => {})
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
      {/* Garmin R50 */}
      <div className="bg-[#121714] border border-[#242C27] rounded-[24px] p-6 space-y-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 bg-[#1A211D] rounded-full flex items-center justify-center border border-[#242C27]">
            <Smartphone className="w-6 h-6 text-garage-green" />
          </div>
          <h3 className="text-lg font-semibold text-[#E7EEE9]">Garmin R50</h3>
        </div>
        <ol className="space-y-3 text-sm text-[#8B978F]">
          <li>
            <span className="text-[#E7EEE9] font-medium">1. On the R50 </span>
            — Tap &apos;Connect&apos;, then select &apos;GSPro&apos; mode.
          </li>
          <li>
            <span className="text-[#E7EEE9] font-medium">2. Join Wi-Fi </span>
            — Connect this PC to the R50&apos;s Wi-Fi network.
          </li>
          <li>
            <span className="text-[#E7EEE9] font-medium">3. Take a Swing </span>
            — Shots will appear automatically once linked.
          </li>
        </ol>
      </div>

      {/* OpenFlight */}
      <div className="bg-[#121714] border border-[#242C27] rounded-[24px] p-6 space-y-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 bg-[#1A211D] rounded-full flex items-center justify-center border border-[#242C27]">
            <Wifi className="w-6 h-6 text-garage-green" />
          </div>
          <h3 className="text-lg font-semibold text-[#E7EEE9]">OpenFlight</h3>
        </div>
        <p className="text-sm text-[#8B978F]">
          OpenFlight needs to be told where to send shots. This is a
          one-time copy-paste on the OpenFlight Pi — GarageTEC can&apos;t
          reach into the Pi&apos;s files for you, so you&apos;ll do this step
          by hand.
        </p>
        <ol className="space-y-3 text-sm text-[#8B978F]">
          <li>
            <span className="text-[#E7EEE9] font-medium">1. </span>
            On the OpenFlight Pi, open the file{' '}
            <code className="text-xs bg-[#0A0D0B] px-1.5 py-0.5 rounded text-[#E7EEE9]">
              config/sim.json
            </code>.
          </li>
          <li>
            <span className="text-[#E7EEE9] font-medium">2. </span>
            Paste in the block below.
            <div className="relative mt-2">
              <pre className="bg-[#0A0D0B] border border-[#242C27] rounded-xl p-4 text-xs font-mono text-[#E7EEE9] overflow-x-auto min-h-[44px]">
                {setupInfo
                  ? JSON.stringify(setupInfo.openflight_connector, null, 2)
                  : 'Loading…'}
              </pre>
              <button
                onClick={onCopyConnector}
                disabled={!setupInfo}
                className="absolute top-2 right-2 flex items-center gap-1 px-3 py-1.5 rounded-lg bg-[#242C27] text-[#E7EEE9] text-xs font-medium min-h-[32px] disabled:opacity-40"
              >
                <Copy className="w-3.5 h-3.5" />
                {copied ? 'Copied' : 'Copy'}
              </button>
            </div>
          </li>
          <li>
            <span className="text-[#E7EEE9] font-medium">3. </span>
            Start OpenFlight with the{' '}
            <code className="text-xs bg-[#0A0D0B] px-1.5 py-0.5 rounded text-[#E7EEE9]">
              --sim
            </code>{' '}
            flag:{' '}
            <code className="text-xs bg-[#0A0D0B] px-1.5 py-0.5 rounded text-[#E7EEE9]">
              scripts/start-kiosk.sh --sim
            </code>
          </li>
          <li>
            <span className="text-[#E7EEE9] font-medium">4. </span>
            Take a swing — the circle above turns green.
          </li>
        </ol>
        <p className="text-sm text-[#8B978F]">
          This PC is at{' '}
          <span className="text-garage-green font-mono font-semibold">
            {setupInfo?.lan_ip ?? '…'}
          </span>
          . Both machines must be on the same network, and Windows Firewall
          must allow inbound TCP on port{' '}
          <span className="font-mono">{setupInfo?.port ?? '…'}</span>.
        </p>
        <div className="flex items-start gap-2 rounded-xl border border-garage-amber/40 bg-garage-amber/5 p-3">
          <AlertTriangle className="w-4 h-4 text-garage-amber shrink-0 mt-0.5" />
          <p className="text-xs text-garage-amber">
            Keep{' '}
            <code className="bg-black/20 px-1 rounded">device_id</code>{' '}
            exactly{' '}
            <code className="bg-black/20 px-1 rounded">&quot;OpenFlight&quot;</code>.
            That&apos;s how GarageTEC recognizes OpenFlight and applies the
            right handling for values it estimates rather than measures.
          </p>
        </div>
      </div>
    </div>
  )
}
