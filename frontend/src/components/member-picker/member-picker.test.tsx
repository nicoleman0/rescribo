import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import { MemberPicker, type MembersSource } from './member-picker'
import { stubPickerDom } from './test-support'

const ada = { id: 'm-1', display_name: 'Ada Lovelace', has_slack_link: true }
const grace = { id: 'm-2', display_name: 'Grace Hopper', has_slack_link: false }

beforeEach(stubPickerDom)

function setup(
  props: Partial<Parameters<typeof MemberPicker>[0]> = {},
  members: Partial<MembersSource> = {},
) {
  const onChoose = vi.fn(() => Promise.resolve())
  render(
    <MemberPicker
      label="Owner"
      value=""
      current={null}
      members={{
        data: [ada, grace],
        isPending: false,
        isError: false,
        isFetching: false,
        refetch: vi.fn(),
        ...members,
      }}
      emptyLabel="No owner"
      pending={false}
      onChoose={onChoose}
      {...props}
    />,
  )
  return { onChoose, trigger: screen.getByRole('combobox', { name: /^Owner/ }) }
}

test('filters members by name as the member types', async () => {
  const { trigger } = setup()
  await userEvent.click(trigger)
  await userEvent.type(
    screen.getByRole('combobox', { name: 'Search Owner' }),
    'grac',
  )
  expect(screen.getByRole('option', { name: /Grace Hopper/ })).toBeVisible()
  expect(screen.queryByRole('option', { name: 'Ada Lovelace' })).toBeNull()
})

test('a choice saves, closes the picker, and returns focus to the trigger', async () => {
  const { onChoose, trigger } = setup()
  await userEvent.click(trigger)
  await userEvent.click(screen.getByRole('option', { name: 'Ada Lovelace' }))
  expect(onChoose).toHaveBeenCalledWith('m-1')
  await waitFor(() => expect(screen.queryByRole('listbox')).toBeNull())
  expect(trigger).toHaveFocus()
})

test('a rejected save keeps the picker open', async () => {
  const onChoose = vi.fn(() => Promise.reject(new Error('no')))
  const { trigger } = setup({ onChoose })
  await userEvent.click(trigger)
  await userEvent.click(screen.getByRole('option', { name: 'Ada Lovelace' }))
  expect(onChoose).toHaveBeenCalledTimes(1)
  expect(screen.getByRole('listbox')).toBeInTheDocument()
})

test('Escape closes without saving and focuses the trigger', async () => {
  const onClose = vi.fn()
  const { onChoose, trigger } = setup({ onClose })
  await userEvent.click(trigger)
  await userEvent.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('listbox')).toBeNull())
  expect(onChoose).not.toHaveBeenCalled()
  expect(onClose).toHaveBeenCalled()
  expect(trigger).toHaveFocus()
})

test('keyboard alone chooses a member', async () => {
  const { onChoose, trigger } = setup()
  trigger.focus()
  await userEvent.keyboard('{Enter}')
  await userEvent.keyboard('ada{Enter}')
  expect(onChoose).toHaveBeenCalledWith('m-1')
})

test('blocks choices while a save is pending and keeps the picker open', async () => {
  const { onChoose, trigger } = setup({ pending: true })
  await userEvent.click(trigger)
  await userEvent.click(screen.getByRole('option', { name: 'Ada Lovelace' }))
  expect(onChoose).not.toHaveBeenCalled()
  await userEvent.keyboard('{Escape}')
  expect(screen.getByRole('listbox')).toBeInTheDocument()
})

test('lists a current member who is not in the directory', async () => {
  const gone = { id: 'm-9', display_name: 'Lin Gone' }
  const { trigger } = setup({ value: 'm-9', current: gone })
  expect(trigger).toHaveAccessibleName('Owner: Lin Gone')
  await userEvent.click(trigger)
  expect(screen.getByRole('option', { name: 'Lin Gone' })).toBeInTheDocument()
})

test('an unavailable member cannot be chosen', async () => {
  const { onChoose, trigger } = setup({
    isUnavailable: (member) => !member.has_slack_link,
    unavailableLabel: 'no Slack link',
  })
  await userEvent.click(trigger)
  const option = screen.getByRole('option', {
    name: 'Grace Hopper (no Slack link)',
  })
  expect(option).toHaveAttribute('aria-disabled', 'true')
  await userEvent.click(option)
  expect(onChoose).not.toHaveBeenCalled()
})

test('a members failure shows a retry inside the picker', async () => {
  const refetch = vi.fn()
  const { trigger } = setup({}, { data: undefined, isError: true, refetch })
  await userEvent.click(trigger)
  await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
  expect(refetch).toHaveBeenCalled()
})
