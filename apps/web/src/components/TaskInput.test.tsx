import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import TaskInput from '../components/TaskInput'
import * as taskStoreModule from '../stores/taskStore'

const mockSubmitTask = vi.fn()

const createMockUseTaskStore = (stateOverrides: Record<string, unknown> = {}) => {
  const fullState = {
    loading: false,
    submitTask: mockSubmitTask,
    ...stateOverrides,
  }
  const mockStore = vi.fn((selector: (s: typeof fullState) => unknown) => {
    return selector ? selector(fullState) : fullState
  })
  return mockStore
}

vi.mock('../stores/taskStore', () => {
  const actual = vi.importActual<typeof taskStoreModule>('../stores/taskStore')
  return {
    ...actual,
    useTaskStore: vi.fn(),
  }
})

describe('TaskInput', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders input and submit button', () => {
    const mockStore = createMockUseTaskStore()
    vi.mocked(taskStoreModule.useTaskStore).mockImplementation(mockStore)

    render(<TaskInput />)

    expect(screen.getByPlaceholderText('请输入任务内容...')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '执行任务' })).toBeInTheDocument()
  })

  it('updates input value on change', () => {
    const mockStore = createMockUseTaskStore()
    vi.mocked(taskStoreModule.useTaskStore).mockImplementation(mockStore)

    render(<TaskInput />)

    const input = screen.getByPlaceholderText('请输入任务内容...')
    fireEvent.change(input, { target: { value: 'test task' } })

    expect((input as HTMLInputElement).value).toBe('test task')
  })

  it('submits task on form submit', async () => {
    const mockStore = createMockUseTaskStore()
    vi.mocked(taskStoreModule.useTaskStore).mockImplementation(mockStore)

    render(<TaskInput />)

    const input = screen.getByPlaceholderText('请输入任务内容...')
    fireEvent.change(input, { target: { value: 'open main.py' } })

    const button = screen.getByRole('button', { name: '执行任务' })
    fireEvent.click(button)

    expect(mockSubmitTask).toHaveBeenCalledWith('open main.py')
  })

  it('disables submit when input is empty', () => {
    const mockStore = createMockUseTaskStore()
    vi.mocked(taskStoreModule.useTaskStore).mockImplementation(mockStore)

    render(<TaskInput />)

    const button = screen.getByRole('button', { name: '执行任务' })
    expect(button).toBeDisabled()
  })

  it('enables submit when input has content', () => {
    const mockStore = createMockUseTaskStore()
    vi.mocked(taskStoreModule.useTaskStore).mockImplementation(mockStore)

    render(<TaskInput />)

    const input = screen.getByPlaceholderText('请输入任务内容...')
    fireEvent.change(input, { target: { value: 'some task' } })

    const button = screen.getByRole('button', { name: '执行任务' })
    expect(button).not.toBeDisabled()
  })

  it('shows loading state when task is executing', () => {
    const mockStore = createMockUseTaskStore({ loading: true })
    vi.mocked(taskStoreModule.useTaskStore).mockImplementation(mockStore)

    render(<TaskInput />)

    expect(screen.getByRole('button', { name: '执行中...' })).toBeInTheDocument()
    expect(screen.getByPlaceholderText('请输入任务内容...')).toBeDisabled()
  })
})
