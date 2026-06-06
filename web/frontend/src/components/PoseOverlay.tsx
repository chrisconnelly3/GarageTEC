import { useEffect, useRef } from 'react'

// Per-frame pose skeleton served alongside the swing video. Coordinates are
// normalized (0..1) to the DISPLAYED (rotation-corrected) frame, with x spanning
// both side-by-side views. Each frame may carry 1-2 poses (one per view).
export interface PoseData {
  fps: number
  width: number
  height: number
  frames: { poses: number[][][] }[] // frames[i].poses[p] = [ [x,y,vis], ...33 ]
}

// BlazePose 33-landmark connections — torso, arms, legs (the golf exoskeleton).
const CONNECTIONS: [number, number][] = [
  [11, 12], [11, 13], [13, 15], [12, 14], [14, 16],
  [11, 23], [12, 24], [23, 24],
  [23, 25], [25, 27], [24, 26], [26, 28],
]
const JOINTS = [11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]
const VIS = 0.5
const LINE = '#79BC30'   // brand green
const JOINT = '#C6F66E'  // brighter green for joints

interface PoseOverlayProps {
  videoRef: React.RefObject<HTMLVideoElement | null>
  pose: PoseData | null
  enabled: boolean
}

export function PoseOverlay({ videoRef, pose, enabled }: PoseOverlayProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    const clear = () => {
      const c = canvasRef.current
      const ctx = c?.getContext('2d')
      if (c && ctx) ctx.clearRect(0, 0, c.width, c.height)
    }
    if (!enabled || !pose || !canvas) { clear(); return }

    let raf = 0
    const draw = () => {
      raf = requestAnimationFrame(draw)
      const video = videoRef.current
      if (!canvas || !video) return
      const boxW = canvas.clientWidth
      const boxH = canvas.clientHeight
      if (!boxW || !boxH) return
      const dpr = window.devicePixelRatio || 1
      if (canvas.width !== Math.round(boxW * dpr) || canvas.height !== Math.round(boxH * dpr)) {
        canvas.width = Math.round(boxW * dpr)
        canvas.height = Math.round(boxH * dpr)
      }
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, boxW, boxH)

      // object-contain: compute the letterboxed video rect inside the box.
      const va = pose.width / pose.height
      const ba = boxW / boxH
      let w: number, h: number, ox: number, oy: number
      if (ba > va) { h = boxH; w = h * va; ox = (boxW - w) / 2; oy = 0 }
      else { w = boxW; h = w / va; ox = 0; oy = (boxH - h) / 2 }

      const fi = Math.max(0, Math.min(pose.frames.length - 1,
        Math.round(video.currentTime * pose.fps)))
      const frame = pose.frames[fi]
      if (!frame) return

      const lineW = Math.max(2, w * 0.005)
      const dotR = Math.max(2.5, w * 0.007)
      for (const lms of frame.poses) {
        ctx.strokeStyle = LINE
        ctx.lineWidth = lineW
        ctx.lineCap = 'round'
        ctx.shadowColor = 'rgba(121,188,48,0.7)'
        ctx.shadowBlur = 6
        for (const [a, b] of CONNECTIONS) {
          const p = lms[a], q = lms[b]
          if (!p || !q || p[2] < VIS || q[2] < VIS) continue
          ctx.beginPath()
          ctx.moveTo(ox + p[0] * w, oy + p[1] * h)
          ctx.lineTo(ox + q[0] * w, oy + q[1] * h)
          ctx.stroke()
        }
        ctx.shadowBlur = 0
        ctx.fillStyle = JOINT
        for (const j of JOINTS) {
          const p = lms[j]
          if (!p || p[2] < VIS) continue
          ctx.beginPath()
          ctx.arc(ox + p[0] * w, oy + p[1] * h, dotR, 0, Math.PI * 2)
          ctx.fill()
        }
      }
    }
    raf = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(raf)
  }, [enabled, pose, videoRef])

  return <canvas ref={canvasRef} className="absolute inset-0 w-full h-full pointer-events-none z-10" />
}
