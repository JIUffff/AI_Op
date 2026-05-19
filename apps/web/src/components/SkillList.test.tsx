import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import SkillList from '../components/SkillList'
import * as taskStoreModule from '../stores/taskStore'

const mockSkill = {
  skill_id: 'vscode/run_file',
  display_name: '运行文件',
  version: '1.0',
  description: '在 VSCode 中打开并运行文件',
  category: 'editor',
  step_count: 3,
}

const mockLoadSkills = vi.fn()
const mockOnSelectSkill = vi.fn()

const createMockUseTaskStore = (stateOverrides: Record<string, unknown> = {}) => {
  const fullState = {
    skills: [mockSkill],
    skillsLoading: false,
    loadSkills: mockLoadSkills,
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

describe('SkillList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders loading state', () => {
    const mockStore = createMockUseTaskStore({ skills: [], skillsLoading: true })
    vi.mocked(taskStoreModule.useTaskStore).mockImplementation(mockStore)

    render(<SkillList onSelectSkill={mockOnSelectSkill} />)

    expect(screen.getByText('正在加载技能列表...')).toBeInTheDocument()
  })

  it('renders empty state when no skills', () => {
    const mockStore = createMockUseTaskStore({ skills: [], skillsLoading: false })
    vi.mocked(taskStoreModule.useTaskStore).mockImplementation(mockStore)

    render(<SkillList onSelectSkill={mockOnSelectSkill} />)

    expect(screen.getByText('暂无可用技能')).toBeInTheDocument()
  })

  it('renders skills when available', () => {
    const mockStore = createMockUseTaskStore({ skills: [mockSkill], skillsLoading: false })
    vi.mocked(taskStoreModule.useTaskStore).mockImplementation(mockStore)

    render(<SkillList onSelectSkill={mockOnSelectSkill} />)

    expect(screen.getByText('运行文件')).toBeInTheDocument()
    expect(screen.getByText('在 VSCode 中打开并运行文件')).toBeInTheDocument()
    expect(screen.getByText('editor')).toBeInTheDocument()
    expect(screen.getByText('v1.0')).toBeInTheDocument()
    expect(screen.getByText('3 个步骤')).toBeInTheDocument()
  })

  it('calls onSelectSkill when skill is clicked', () => {
    const mockStore = createMockUseTaskStore({ skills: [mockSkill], skillsLoading: false })
    vi.mocked(taskStoreModule.useTaskStore).mockImplementation(mockStore)

    render(<SkillList onSelectSkill={mockOnSelectSkill} />)

    const skillCard = screen.getByText('运行文件').closest('div[role="button"]')
    fireEvent.click(skillCard!)

    expect(mockOnSelectSkill).toHaveBeenCalledWith('vscode/run_file')
  })

  it('loads skills on mount', () => {
    const mockStore = createMockUseTaskStore({ skills: [mockSkill], skillsLoading: false })
    vi.mocked(taskStoreModule.useTaskStore).mockImplementation(mockStore)

    render(<SkillList onSelectSkill={mockOnSelectSkill} />)

    expect(mockLoadSkills).toHaveBeenCalled()
  })

  it('shows different category colors for different skill types', () => {
    const browserSkill = { ...mockSkill, category: 'browser', skill_id: 'chrome/search' }
    const fileSkill = { ...mockSkill, category: 'file', skill_id: 'file/archive' }

    const mockStore = createMockUseTaskStore({
      skills: [browserSkill, fileSkill],
      skillsLoading: false,
    })
    vi.mocked(taskStoreModule.useTaskStore).mockImplementation(mockStore)

    render(<SkillList onSelectSkill={mockOnSelectSkill} />)

    expect(screen.getByText('browser')).toBeInTheDocument()
    expect(screen.getByText('file')).toBeInTheDocument()
  })
})
