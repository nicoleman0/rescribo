import { useCallback, useContext } from 'react'
import {
  UNSAFE_NavigationContext,
  useSearchParams,
  type Location,
} from 'react-router-dom'

type SearchChange = (current: URLSearchParams) => URLSearchParams

/**
 * useSearchParams whose updates start from the URL as it is now. The router
 * re-renders in a transition after a navigation, so params from the last
 * render can miss a change made a moment earlier.
 */
export function useLiveSearchParams() {
  const [params, setParams] = useSearchParams()
  const { navigator } = useContext(UNSAFE_NavigationContext)
  const update = useCallback(
    (change: SearchChange) => {
      // Not window.location (stale under MemoryRouter) and not the function
      // form of setParams (it gets the render-time params). Browser and memory
      // history both have `location`; React Router's type does not.
      const { location } = navigator as { location?: Location }
      if (!location) {
        throw new Error('The router history has no location to read.')
      }
      setParams(change(new URLSearchParams(location.search)))
    },
    [navigator, setParams],
  )
  return [params, update] as const
}
