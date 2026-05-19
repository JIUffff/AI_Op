import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import SkillExecutor from '../components/SkillExecutor'
import * as taskStoreModule from '../stores/taskStore'

const mockSkillDetail = {
  skill_id: 'vscode/run_file',
  display_name: '运行文件',
  version: '1.0',
  description: '在 VSCode 中打开并运行文件',
  category: 'editor',
  step_count: 2,
  steps: [
    {
      step_id: 'step_1',
      action: 'open_file',
      engine: 'vscode',
      params: { file_path: '{file_path}' },
      timeout: 30,
      retry_count: 1,
      verify: null,
    },
    {
      step_id: 'step_2',
      action: 'run_file',
      engine: 'vscode',
      params: {},
      timeout: 60,
      retry_count: 1,
      verify: null,
    },
  ],
}

const mockSkillNoParams = {
  ...mockSkillDetail,
  skill_id: 'file/scan',
  steps: [
    {
      step_id: 'step_1',
      action: 'scan',
      engine: 'file_engine',
      params: {},
      timeout: 30,
      retry_count: 1,
      verify: null,
    },
  ],
}

const mockExecuteSkill = vi.fn()
const mockOnBack = vi.fn()

const createMockUseTaskStore = (stateOverrides: Record<string, unknown> = {}) => {
  const fullState = {
    skillExecuting: false,
    skillExecuteResult: null,
    executeSkill: mockExecuteSkill,
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

describe('SkillExecutor', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders skill title and version', () => {
    const mockStore = createMockUseTaskStore()
    vi.mocked(taskStoreModule.useTaskStore).mockImplementation(mockStore)

    render(<SkillExecutor skill={mockSkillDetail} onBack={mockOnBack} />)

    expect(screen.getByText('运行文件')).toBeInTheDocument()
    expect(screen.getByText('v1.0')).toBeInTheDocument()
  })

  it('renders parameter inputs for template variables', () => {
    const mockStore = createMockUseTaskStore()
    vi.mocked(taskStoreModule.useTaskStore).mockImplementation(mockStore)

    render(<SkillExecutor skill={mockSkillDetail} onBack={mockOnBack} />)

    expect(screen.getByPlaceholderText('请输入 file_path')).toBeInTheDocument()
    expect(screen.getByText('file_path')).toBeInTheDocument()
  })

  it('shows no params message when skill has no parameters', () => {
    const mockStore = createMockUseTaskStore()
    vi.mocked(taskStoreModule.useTaskStore).mockImplementation(mockStore)

    render(<SkillExecutor skill={mockSkillNoParams} onBack={mockOnBack} />)

    expect(screen.getByText('此技能无需额外参数')).toBeInTheDocument()
  })

  it('calls executeSkill with skill_id and params on execute', async () => {
    const mockStore = createMockUseTaskStore()
    vi.mocked(taskStoreModule.useTaskStore).mockImplementation(mockStore)

    render(<SkillExecutor skill={mockSkillDetail} onBack={mockOnBack} />)

    const input = screen.getByPlaceholderText('请输入 file_path')
    fireEvent.change(input, { target: { value: '/path/to/main.py' } })

    const button = screen.getByRole('button', { name: '执行技能' })
    fireEvent.click(button)

    await waitFor(() => {
      expect(mockExecuteSkill).toHaveBeenCalledWith('vscode/run_file', {
        file_path: '/path/to/main.py',
      })
    })
  })

  it('calls onBack when back button is clicked', () => {
    const mockStore = createMockUseTaskStore()
    vi.mocked(taskStoreModule.useTaskStore).mockImplementation(mockStore)

    render(<SkillExecutor skill={mockSkillDetail} onBack={mockOnBack} />)

    const backButton = screen.getByRole('button', { name: '← 返回' })
    fireEvent.click(backButton)

    expect(mockOnBack).toHaveBeenCalled()
  })

  it('shows executing state when skill is executing', () => {
    const mockStore = createMockUseTaskStore({ skillExecuting: true })
    vi.mocked(taskStoreModule.useTaskStore).mockImplementation(mockStore)

    render(<SkillExecutor skill={mockSkillDetail} onBack={mockOnBack} />)

    const button = screen.getByRole('button', { name: '执行中...' })
    expect(button).toBeDisabled()
    expect(button).toHaveStyle('cursor: not-allowed')
  })

  it('displays successful execution result', () => {
    const executeResult = {
      success: true,
      result: { output: 'Hello World' },
      error: null,
      steps_executed: [
        { action: 'open_file', result: 'success' },
        { action: 'run_file', result: 'success' },
      ],
    }

    const mockStore = createMockUseTaskStore({ skillExecuteResult: executeResult })
    vi.mocked(taskStoreModule.useTaskStore).mockImplementation(mockStore)

    render(<SkillExecutor skill={mockSkillDetail} onBack={mockOnBack} />)

    expect(screen.getByText('执行成功')).toBeInTheDocument()
    expect(screen.getByText('结果：')).toBeInTheDocument()
    expect(screen.getByText('已执行步骤：')).toBeInTheDocument()
    expect(screen.getByText('open_file')).toBeInTheDocument()
    expect(screen.getByText('run_file')).toBeInTheDocument()
  })

  it('displays failed execution result', () => {
    const executeResult = {
      success: false,
      result: null,
      error: { message: 'File not found' },
      steps_executed: [],
    }

    const mockStore = createMockUseTaskStore({ skillExecuteResult: executeResult })
    vi.mocked(taskStoreModule.useTaskStore).mockImplementation(mockStore)

    render(<SkillExecutor skill={mockSkillDetail} onBack={mockOnBack} />)

    expect(screen.getByText('执行失败')).toBeInTheDocument()
    expect(screen.getByText('错误：')).toBeInTheDocument()
    expect(screen.getByText(/File not found/)).toBeInTheDocument()
  })
})
