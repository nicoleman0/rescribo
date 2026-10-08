import type { Connection } from '@/api/settings'
import { StatusBadge } from '@/components/status/status-badge'
import type { StatusTone } from '@/components/status/status-tone'

type ConnectionStatus = Connection['status']

const connectionStatus: Record<
  ConnectionStatus,
  { label: string; tone: StatusTone }
> = {
  active: { label: 'Connected', tone: 'success' },
  error: { label: 'Needs attention', tone: 'danger' },
  disconnected: { label: 'Disconnected', tone: 'neutral' },
}

const notConnected = { label: 'Not connected', tone: 'neutral' } as const

/** A provider that was never connected has no connection record. */
export function ConnectionStatusBadge({
  status,
}: {
  status: ConnectionStatus | undefined
}) {
  const { label, tone } = status ? connectionStatus[status] : notConnected
  return <StatusBadge tone={tone}>{label}</StatusBadge>
}
