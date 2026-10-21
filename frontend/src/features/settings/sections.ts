export const settingsSections = [
  { slug: 'appearance', label: 'Appearance', ownerOnly: false },
  { slug: 'members', label: 'Members', ownerOnly: true },
  { slug: 'connections', label: 'Connections', ownerOnly: false },
  { slug: 'slack-account', label: 'Slack account', ownerOnly: false },
  { slug: 'workspace', label: 'Workspace', ownerOnly: true },
] as const

export function sectionsForRole(role: 'owner' | 'member') {
  return settingsSections.filter(
    (section) => !section.ownerOnly || role === 'owner',
  )
}
