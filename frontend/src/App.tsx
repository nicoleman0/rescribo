import { useQuery } from '@tanstack/react-query'
import { getReadiness } from './api/health'
import './App.css'

export default function App() {
  const health = useQuery({
    queryKey: ['readiness'],
    queryFn: getReadiness,
    retry: false,
  })
  return (
    <main>
      <p className="eyebrow">Development workspace</p>
      <h1>Feedback inbox</h1>
      <p>
        Customer reports, engineering work, and the people waiting for an
        answer.
      </p>
      <section aria-labelledby="environment-heading">
        <h2 id="environment-heading">Environment</h2>
        <p role="status">
          {health.isPending
            ? 'Checking services…'
            : health.isError
              ? 'Services unavailable. Start the API, PostgreSQL, and Redis.'
              : 'API, PostgreSQL, and Redis are ready.'}
        </p>
        <button
          onClick={() => void health.refetch()}
          disabled={health.isFetching}
        >
          Check again
        </button>
      </section>
      <p className="note">
        Product workflows are not built yet. This page checks the development
        services.
      </p>
    </main>
  )
}
