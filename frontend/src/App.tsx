import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from '@/components/layout/app-shell'
import { EmptyState } from '@/components/states/async-states'
import { DevelopmentStatusPage } from '@/pages/development-status-page'

const UiGalleryPage = import.meta.env.DEV
  ? lazy(() => import('@/dev/ui-gallery'))
  : undefined

const productRoutes = [
  {
    path: 'inbox',
    title: 'Inbox',
    description: 'Customer reports will appear here once intake is connected.',
  },
  {
    path: 'problems',
    title: 'Problems',
    description: 'Track recurring problems and their engineering work here.',
  },
  {
    path: 'follow-ups',
    title: 'Follow-ups',
    description: 'Approved customer follow-ups will be managed here.',
  },
  {
    path: 'settings',
    title: 'Settings',
    description:
      'Workspace connections and membership settings will live here.',
  },
] as const

function PlaceholderPage({
  title,
  description,
}: (typeof productRoutes)[number]) {
  return (
    <EmptyState
      title={`${title} is ready for its feature issue`}
      description={description}
    />
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/dev/status" element={<DevelopmentStatusPage />} />
      {UiGalleryPage ? (
        <Route
          path="/dev/ui"
          element={
            <AppShell>
              <Suspense fallback={<p>Loading gallery…</p>}>
                <UiGalleryPage />
              </Suspense>
            </AppShell>
          }
        />
      ) : null}
      <Route element={<AppShell />}>
        <Route path="/" element={<Navigate replace to="/inbox" />} />
        {productRoutes.map((route) => (
          <Route
            key={route.path}
            path={route.path}
            element={<PlaceholderPage {...route} />}
          />
        ))}
      </Route>
      <Route
        path="*"
        element={
          <main className="grid min-h-svh place-items-center p-6">
            <EmptyState
              title="Page not found"
              description="The page you requested does not exist."
            />
          </main>
        }
      />
    </Routes>
  )
}
