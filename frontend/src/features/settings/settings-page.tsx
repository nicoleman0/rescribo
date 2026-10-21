import { Outlet } from 'react-router-dom'
import { useWorkspace } from '@/components/auth/use-workspace'
import { SettingsNav } from './settings-nav'
import { SettingsContent } from './settings-sections'

export function SettingsPage() {
  const membership = useWorkspace()
  return <SettingsLayout key={membership.workspace.id} />
}

function SettingsLayout() {
  const { role } = useWorkspace()
  return (
    <SettingsContent>
      <div className="grid min-w-0 gap-6 md:grid-cols-[11rem_minmax(0,1fr)]">
        <SettingsNav role={role} />
        <div className="min-w-0">
          <Outlet />
        </div>
      </div>
    </SettingsContent>
  )
}
