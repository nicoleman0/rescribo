import { useSyncExternalStore } from 'react'
import { Toaster as Sonner, type ToasterProps } from 'sonner'
import { resolveTheme, useThemePreference } from '@/lib/theme'

// The phone navigation is 4rem tall and fixed to the bottom edge.
const phoneQuery = '(max-width: 767px)'
const subscribe = (listener: () => void) => {
  const media = window.matchMedia(phoneQuery)
  media.addEventListener('change', listener)
  return () => media.removeEventListener('change', listener)
}
const isPhone = () => window.matchMedia(phoneQuery).matches

function Toaster(props: ToasterProps) {
  const [preference] = useThemePreference()
  const phone = useSyncExternalStore(subscribe, isPhone)
  return (
    <Sonner
      theme={resolveTheme(preference)}
      position={phone ? 'bottom-center' : 'bottom-right'}
      offset={phone ? { bottom: '5rem' } : undefined}
      mobileOffset={{ bottom: '5rem' }}
      className="toaster group"
      toastOptions={{
        classNames: {
          toast:
            '!rounded-control !border-border !bg-popover !text-popover-foreground !shadow-elevation-3',
        },
      }}
      {...props}
    />
  )
}

export { Toaster }
