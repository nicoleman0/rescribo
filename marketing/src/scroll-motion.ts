import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'

gsap.registerPlugin(ScrollTrigger)

export function mountScrollMotion(onProgress: (progress: number) => void) {
  let context: gsap.Context | undefined
  let enabled = false
  let disposed = false
  const triggers: ScrollTrigger[] = []

  function initialize(): void {
    context = gsap.context(() => {
      triggers.push(
        ScrollTrigger.create({
          trigger: '.hero',
          start: 'top top',
          end: 'bottom top',
          onUpdate: (trigger) => onProgress(trigger.progress),
        }),
      )
      for (const row of document.querySelectorAll('.steps li')) {
        const animation = gsap.fromTo(
          row,
          { y: 32 },
          {
            y: 0,
            ease: 'none',
            scrollTrigger: {
              trigger: row,
              start: 'top 95%',
              end: 'top 60%',
              scrub: 0.4,
            },
          },
        )
        triggers.push(animation.scrollTrigger!)
      }
      const heading = gsap.fromTo(
        '.about h2',
        { y: 40 },
        {
          y: 0,
          ease: 'none',
          scrollTrigger: {
            trigger: '.about',
            start: 'top 95%',
            end: 'top 40%',
            scrub: 0.5,
          },
        },
      )
      triggers.push(heading.scrollTrigger!)
    })
  }

  return {
    setEnabled(value: boolean): void {
      if (disposed || value === enabled) return
      enabled = value
      if (!context && enabled) initialize()
      for (const trigger of triggers) {
        if (enabled) trigger.enable(false, true)
        else {
          trigger.getTween()?.pause()
          trigger.animation?.pause()
          trigger.disable(false, false)
        }
      }
    },
    dispose(): void {
      disposed = true
      context?.revert()
    },
  }
}
