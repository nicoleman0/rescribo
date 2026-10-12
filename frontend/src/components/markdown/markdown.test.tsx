import { render, screen, within } from '@testing-library/react'
import { expect, test } from 'vitest'
import { Markdown, MarkdownErrorBoundary } from './markdown'

test('shows the plain text fallback while the renderer loads', () => {
  render(<Markdown>{'# Private body'}</Markdown>)
  expect(screen.getByText('# Private body')).toHaveClass('whitespace-pre-wrap')
  expect(screen.queryByRole('heading', { name: 'Private body' })).toBeNull()
})

test('keeps plain text visible and reports a renderer load failure', () => {
  function FailedChunk(): never {
    throw new Error('chunk failed')
  }
  render(
    <MarkdownErrorBoundary
      fallback={
        <>
          <p>Private body</p>
          <p>Formatted preview could not load.</p>
        </>
      }
    >
      <FailedChunk />
    </MarkdownErrorBoundary>,
  )
  expect(screen.getByText('Private body')).toBeInTheDocument()
  expect(
    screen.getByText('Formatted preview could not load.'),
  ).toBeInTheDocument()
})

test('renders headings, lists, and single newlines', async () => {
  const { container } = render(
    <Markdown>{'# Title\nFirst line\nSecond line\n\n- One\n- Two'}</Markdown>,
  )
  expect(
    await screen.findByRole('heading', { name: 'Title', level: 1 }),
  ).toBeInTheDocument()
  expect(
    within(screen.getByRole('list')).getAllByRole('listitem'),
  ).toHaveLength(2)
  expect(container.querySelector('p br')).toBeInTheDocument()
  expect(container.querySelector('[node]')).toBeNull()
})

test('allows only web and mail links and turns images into links', async () => {
  render(
    <Markdown>
      {
        '[web](https://example.com) [mail](mailto:a@example.com) [js](javascript:alert(1)) [data](data:text/plain,x) [irc](irc://host) [relative](/settings) ![chart](https://example.com/chart.png) ![](https://example.com/empty.png)'
      }
    </Markdown>,
  )
  const web = await screen.findByRole('link', { name: 'web' })
  expect(web).toHaveAttribute('target', '_blank')
  expect(web).toHaveAttribute('rel', 'noopener noreferrer')
  expect(screen.getByRole('link', { name: 'mail' })).toHaveAttribute(
    'href',
    'mailto:a@example.com',
  )
  expect(screen.getByRole('link', { name: 'chart' })).toHaveAttribute(
    'href',
    'https://example.com/chart.png',
  )
  expect(
    screen.getByRole('link', { name: 'https://example.com/empty.png' }),
  ).toBeInTheDocument()
  expect(screen.queryByRole('img')).not.toBeInTheDocument()
  for (const text of ['js', 'data', 'irc', 'relative'])
    expect(screen.getByText(text, { selector: 'span' })).toBeInTheDocument()
})

test('shows raw HTML literally without creating elements', async () => {
  const { container } = render(
    <Markdown>
      {
        '<details><summary>More</summary>Hidden</details>\n<script>alert(1)</script>\n<img onerror="alert(1)">\n<!-- private -->'
      }
    </Markdown>,
  )
  await screen.findByText(/<details>/)
  expect(container).toHaveTextContent(
    '<details><summary>More</summary>Hidden</details>',
  )
  expect(container).toHaveTextContent('<script>alert(1)</script>')
  expect(container).toHaveTextContent('<img onerror="alert(1)">')
  expect(container).toHaveTextContent('<!-- private -->')
  expect(container.querySelector('details, script, img')).toBeNull()
})

test('offsets headings and styles markdown structures', async () => {
  const { container } = render(
    <Markdown headingOffset={4}>
      {
        '# First\n\n### Third\n\n| A | B |\n| - | - |\n| x | y |\n\n- [x] done\n- [ ] todo\n\n~~x~~'
      }
    </Markdown>,
  )
  expect(
    await screen.findByRole('heading', { name: 'First', level: 5 }),
  ).toBeInTheDocument()
  expect(
    screen.getByRole('heading', { name: 'Third', level: 6 }),
  ).toBeInTheDocument()
  expect(
    container.querySelector('div.overflow-x-auto table'),
  ).toBeInTheDocument()
  const checkboxes = screen.getAllByRole('checkbox')
  expect(checkboxes).toHaveLength(2)
  expect(checkboxes[0]).toBeDisabled()
  expect(checkboxes[0]).toHaveAccessibleName('Done')
  expect(checkboxes[1]).toHaveAccessibleName('Not done')
  expect(container.querySelector('del')).toHaveTextContent('x')
})
