import { useLocation } from 'react-router-dom'

/** Expose the current router location to component tests. */
export function LocationProbe() {
  const location = useLocation()
  return (
    <output data-testid="location">{`${location.pathname}${location.search}`}</output>
  )
}
