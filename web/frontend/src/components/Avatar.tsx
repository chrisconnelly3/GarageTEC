import React from 'react'
import { cn } from '../lib/utils'

// Lightweight Avatar primitive (MagicPatterns shipped this file empty).
// Pure React + Tailwind — no Radix dependency. Mirrors the shadcn Avatar API
// (Avatar / AvatarImage / AvatarFallback) used by Topbar / Sessions / Players.

interface AvatarContextValue {
  imageLoaded: boolean
  setImageLoaded: (loaded: boolean) => void
  hasImageSrc: boolean
  setHasImageSrc: (has: boolean) => void
}

const AvatarContext = React.createContext<AvatarContextValue | null>(null)

export function Avatar({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  const [imageLoaded, setImageLoaded] = React.useState(false)
  const [hasImageSrc, setHasImageSrc] = React.useState(false)
  return (
    <AvatarContext.Provider
      value={{ imageLoaded, setImageLoaded, hasImageSrc, setHasImageSrc }}
    >
      <div
        className={cn(
          'relative flex shrink-0 overflow-hidden rounded-full',
          className,
        )}
        {...props}
      >
        {children}
      </div>
    </AvatarContext.Provider>
  )
}

export function AvatarImage({
  className,
  src,
  alt = '',
  ...props
}: React.ImgHTMLAttributes<HTMLImageElement>) {
  const ctx = React.useContext(AvatarContext)
  React.useEffect(() => {
    ctx?.setHasImageSrc(Boolean(src))
    if (!src) ctx?.setImageLoaded(false)
  }, [src])
  if (!src) return null
  return (
    <img
      src={src}
      alt={alt}
      onLoad={() => ctx?.setImageLoaded(true)}
      onError={() => ctx?.setImageLoaded(false)}
      className={cn('aspect-square h-full w-full object-cover', className)}
      {...props}
    />
  )
}

export function AvatarFallback({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLSpanElement>) {
  const ctx = React.useContext(AvatarContext)
  // Show fallback when there is no image source or the image failed to load.
  const show = !ctx?.hasImageSrc || !ctx?.imageLoaded
  if (!show) return null
  return (
    <span
      className={cn(
        'flex h-full w-full items-center justify-center rounded-full bg-[#242C27] font-medium text-[#E7EEE9]',
        className,
      )}
      {...props}
    >
      {children}
    </span>
  )
}
