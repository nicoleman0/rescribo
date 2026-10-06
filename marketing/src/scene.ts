import * as THREE from 'three'
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js'
import { mountScrollMotion } from './scroll-motion'

type SceneElements = {
  surface: HTMLElement
  visual: HTMLElement
  canvas: HTMLCanvasElement
  control: HTMLButtonElement
}

export function mountScene({
  surface,
  visual,
  canvas,
  control,
}: SceneElements): () => void {
  const renderer = new THREE.WebGLRenderer({
    canvas,
    alpha: true,
    antialias: true,
    powerPreference: 'low-power',
  })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5))
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  const scene = new THREE.Scene()
  const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 100)
  camera.position.set(0, 0, 10.8)
  const environment = new RoomEnvironment()
  const generator = new THREE.PMREMGenerator(renderer)
  const environmentMap = generator.fromScene(environment)
  scene.environment = environmentMap.texture
  environment.dispose()
  generator.dispose()
  scene.add(new THREE.AmbientLight(0xffffff, 1.2))
  const light = new THREE.DirectionalLight(0xffffff, 3)
  light.position.set(-3, 5, 5)
  scene.add(light)

  const sculpture = new THREE.Group()
  scene.add(sculpture)
  const ribbonMaterial = new THREE.MeshStandardMaterial({
    color: 0x7750b4,
    metalness: 0.52,
    roughness: 0.22,
    side: THREE.DoubleSide,
  })
  const paperMaterial = new THREE.MeshStandardMaterial({
    color: 0xfaf5e9,
    roughness: 0.65,
  })
  const inkMaterial = new THREE.MeshStandardMaterial({
    color: 0x877392,
    roughness: 0.7,
  })

  // A continuous strip joins the three report forms without loading a model.
  const segments = 240
  const positions: number[] = []
  const indices: number[] = []
  for (let index = 0; index <= segments; index++) {
    const angle = (index / segments) * Math.PI * 2
    const radius = 1.65 + 0.42 * Math.cos(3 * angle)
    const center = new THREE.Vector3(
      radius * Math.cos(angle),
      radius * Math.sin(angle),
      0.7 * Math.sin(3 * angle),
    )
    const outward = new THREE.Vector3(
      Math.cos(angle),
      Math.sin(angle),
      0.2 * Math.cos(3 * angle),
    ).normalize()
    for (const side of [-1, 1]) {
      const edge = center.clone().addScaledVector(outward, side * 0.33)
      positions.push(edge.x, edge.y, edge.z)
    }
    if (index < segments) {
      const start = index * 2
      indices.push(start, start + 1, start + 2, start + 1, start + 3, start + 2)
    }
  }
  const ribbonGeometry = new THREE.BufferGeometry()
  ribbonGeometry.setAttribute(
    'position',
    new THREE.Float32BufferAttribute(positions, 3),
  )
  ribbonGeometry.setIndex(indices)
  ribbonGeometry.computeVertexNormals()
  const ribbon = new THREE.Mesh(ribbonGeometry, ribbonMaterial)
  sculpture.add(ribbon)

  const paperGeometry = new THREE.BoxGeometry(0.94, 1.25, 0.065)
  const lineGeometry = new THREE.BoxGeometry(0.56, 0.024, 0.018)
  const dotGeometry = new THREE.CircleGeometry(0.07, 24)
  const cards: THREE.Group[] = []
  for (let index = 0; index < 3; index++) {
    const angle = (index * Math.PI * 2) / 3 + 0.2
    const card = new THREE.Group()
    card.add(new THREE.Mesh(paperGeometry, paperMaterial))
    const dot = new THREE.Mesh(dotGeometry, ribbonMaterial)
    dot.position.set(-0.29, 0.37, 0.045)
    card.add(dot)
    for (let row = 0; row < 4; row++) {
      const line = new THREE.Mesh(lineGeometry, inkMaterial)
      line.position.set(0, 0.1 - row * 0.16, 0.045)
      if (row === 3) {
        line.scale.x = 0.65
        line.position.x = -0.098
      }
      card.add(line)
    }
    card.position.set(1.6 * Math.cos(angle), 1.6 * Math.sin(angle), 0.9)
    card.rotation.set(-0.12, index === 1 ? -0.3 : 0.25, angle * 0.14 - 0.2)
    cards.push(card)
    sculpture.add(card)
  }
  sculpture.rotation.set(-0.2, -0.28, -0.3)

  const preference = window.matchMedia('(prefers-reduced-motion: reduce)')
  let paused = false
  let visible = false
  let disposed = false
  let failed = false
  let frame = 0
  let lastTime = 0
  let elapsed = 0
  let scrollTarget = 0
  let scrollProgress = 0
  const scrollMotion = mountScrollMotion((progress) => {
    scrollTarget = progress
  })
  const pointer = new THREE.Vector2()
  function moving(): boolean {
    return (
      !paused &&
      !preference.matches &&
      visible &&
      !document.hidden &&
      !disposed &&
      !failed
    )
  }
  function render(): void {
    renderer.render(scene, camera)
  }
  function updateControl(): void {
    control.hidden = failed
    control.disabled = preference.matches
    control.textContent = preference.matches
      ? 'Reduced motion'
      : paused
        ? 'Resume motion'
        : 'Pause motion'
    control.setAttribute('aria-pressed', String(paused || preference.matches))
  }
  function animate(time: number): void {
    frame = 0
    if (!moving()) {
      reconcile()
      return
    }
    elapsed += lastTime ? Math.min((time - lastTime) / 1000, 0.05) : 0
    lastTime = time
    scrollProgress += (scrollTarget - scrollProgress) * 0.08
    sculpture.rotation.y +=
      (-0.28 +
        scrollProgress * 1.4 +
        pointer.x * 0.16 +
        Math.sin(elapsed * 0.3) * 0.12 -
        sculpture.rotation.y) *
      0.04
    sculpture.rotation.x +=
      (-0.2 + scrollProgress * 0.45 - pointer.y * 0.12 - sculpture.rotation.x) *
      0.04
    sculpture.rotation.z = -0.3 - scrollProgress * 0.35
    sculpture.position.y =
      Math.sin(elapsed * 0.7) * 0.07 + scrollProgress * 0.25
    camera.position.z = 10.8 + scrollProgress * 1.5
    for (let index = 0; index < cards.length; index++) {
      const angle = (index * Math.PI * 2) / 3 + 0.2
      const radius = 1.6 + scrollProgress * 0.55
      cards[index].position.x = radius * Math.cos(angle)
      cards[index].position.y = radius * Math.sin(angle)
      cards[index].position.z =
        0.9 + scrollProgress * 0.4 + Math.sin(elapsed * 0.6 + index * 2) * 0.08
    }
    try {
      render()
    } catch (error) {
      fallback(error)
      return
    }
    frame = requestAnimationFrame(animate)
  }
  function reconcile(): void {
    if (frame) cancelAnimationFrame(frame)
    frame = 0
    lastTime = 0
    visual.dataset.motion = moving() ? 'running' : 'stopped'
    scrollMotion.setEnabled(
      !paused &&
        !preference.matches &&
        !document.hidden &&
        !failed &&
        !disposed,
    )
    updateControl()
    if (moving()) frame = requestAnimationFrame(animate)
  }
  function resize(): void {
    if (disposed || failed) return
    const width = surface.clientWidth
    const height = surface.clientHeight
    if (!width || !height) return
    camera.aspect = width / height
    camera.updateProjectionMatrix()
    renderer.setSize(width, height, false)
    try {
      render()
    } catch (error) {
      fallback(error)
    }
  }
  function move(event: PointerEvent): void {
    if (!moving() || event.pointerType === 'touch') return
    const bounds = surface.getBoundingClientRect()
    pointer.set(
      ((event.clientX - bounds.left) / bounds.width) * 2 - 1,
      ((event.clientY - bounds.top) / bounds.height) * 2 - 1,
    )
  }
  function leave(): void {
    pointer.set(0, 0)
  }
  function toggle(): void {
    paused = !paused
    reconcile()
  }
  function mediaChanged(): void {
    pointer.set(0, 0)
    reconcile()
  }
  function contextLost(event: Event): void {
    event.preventDefault()
    fallback('WebGL context lost')
  }
  function fallback(error: unknown): void {
    if (failed || disposed) return
    failed = true
    visual.dataset.renderer = 'static'
    console.warn(
      'Rescribo visual unavailable; retaining static illustration.',
      error,
    )
    reconcile()
    dispose()
  }
  const resizeObserver = new ResizeObserver(resize)
  const intersectionObserver = new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting
    reconcile()
  })
  function dispose(): void {
    if (disposed) return
    disposed = true
    scrollMotion.dispose()
    if (frame) cancelAnimationFrame(frame)
    frame = 0
    visual.dataset.motion = 'stopped'
    visual.dataset.renderer = 'static'
    control.hidden = true
    resizeObserver.disconnect()
    intersectionObserver.disconnect()
    surface.removeEventListener('pointermove', move)
    surface.removeEventListener('pointerleave', leave)
    control.removeEventListener('click', toggle)
    preference.removeEventListener('change', mediaChanged)
    document.removeEventListener('visibilitychange', reconcile)
    canvas.removeEventListener('webglcontextlost', contextLost)
    ribbonGeometry.dispose()
    paperGeometry.dispose()
    lineGeometry.dispose()
    dotGeometry.dispose()
    ribbonMaterial.dispose()
    paperMaterial.dispose()
    inkMaterial.dispose()
    environmentMap.dispose()
    renderer.dispose()
  }
  surface.addEventListener('pointermove', move)
  surface.addEventListener('pointerleave', leave)
  control.addEventListener('click', toggle)
  preference.addEventListener('change', mediaChanged)
  document.addEventListener('visibilitychange', reconcile)
  canvas.addEventListener('webglcontextlost', contextLost)
  resizeObserver.observe(surface)
  intersectionObserver.observe(surface)
  try {
    resize()
    if (!failed) {
      visual.dataset.renderer = 'webgl'
      reconcile()
    }
  } catch (error) {
    fallback(error)
  }
  return dispose
}
