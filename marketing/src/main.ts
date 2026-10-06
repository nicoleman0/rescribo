const surface = document.querySelector<HTMLElement>('#visual-surface')!
const visual = document.querySelector<HTMLElement>('#visual')!
const canvas = document.querySelector<HTMLCanvasElement>('#scene')!
const control = document.querySelector<HTMLButtonElement>('#motion-control')!
let dispose: (() => void) | undefined
let generation = 0

// Graphics are optional; HTML and the static illustration are already usable.
function initialize(): void {
  const current = ++generation
  void import('./scene')
    .then(({ mountScene }) => {
      if (current !== generation) return
      dispose = mountScene({ surface, visual, canvas, control })
    })
    .catch((error: unknown) => {
      console.warn(
        'Rescribo visual unavailable; retaining static illustration.',
        error,
      )
    })
}
window.addEventListener('pagehide', () => {
  generation++
  dispose?.()
  dispose = undefined
})
window.addEventListener('pageshow', (event) => {
  if (event.persisted) initialize()
})
initialize()
