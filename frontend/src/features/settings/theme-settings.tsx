import { touchTarget } from '@/components/layout/touch-target'
import { useThemePreference, type ThemePreference } from '@/lib/theme'
import { cn } from '@/lib/utils'

const options: { value: ThemePreference; label: string }[] = [
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
  { value: 'system', label: 'System' },
]

export function ThemeSettings() {
  const [preference, setPreference] = useThemePreference()
  return (
    <section className="grid gap-3" aria-labelledby="appearance-heading">
      <h2 id="appearance-heading" className="text-base font-semibold">
        Appearance
      </h2>
      <fieldset className="grid gap-2">
        <legend className="text-sm font-medium">Theme</legend>
        <div className="inline-flex w-fit gap-1 rounded-control bg-muted p-1">
          {options.map(({ value, label }) => (
            <label
              key={value}
              className={cn(
                'flex min-h-8 cursor-pointer items-center rounded-control px-3 text-sm text-muted-foreground transition-colors hover:text-foreground has-checked:bg-card has-checked:font-medium has-checked:text-foreground has-checked:shadow-elevation-1 has-focus-visible:ring-3 has-focus-visible:ring-ring/50',
                touchTarget,
              )}
            >
              <input
                type="radio"
                name="theme"
                value={value}
                checked={preference === value}
                onChange={() => setPreference(value)}
                className="sr-only"
              />
              {label}
            </label>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          Saved in this browser. System follows your device setting.
        </p>
      </fieldset>
    </section>
  )
}
