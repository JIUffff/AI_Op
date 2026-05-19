import { vi } from 'vitest'
import type { AppState, SkillInfo, SkillDetail, TaskRecord, SkillExecuteResult } from '../stores/taskStore'

export const mockSkill: SkillInfo = {
  skill_id: 'vscode/run_file',
  display_name: '运行文件',
  version: '1.0',
  description: '在 VSCode 中打开并运行文件',
  category: 'editor',
  step_count: 3,
}

export const mockSkillDetail: SkillDetail = {
  ...mockSkill,
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

export const mockTaskRecord: TaskRecord = {
  task_id: 'task_001',
  status: 'success',
  steps: ['vscode/open_file', 'vscode/run_file'],
  started_at: '2026-05-18T10:00:00Z',
  finished_at: '2026-05-18T10:00:30Z',
}

export const mockExecuteResult: SkillExecuteResult = {
  success: true,
  result: { output: 'Hello World' },
  error: null,
  steps_executed: [
    { action: 'open_file', result: 'success' },
    { action: 'run_file', result: 'success' },
  ],
}

export const createMockStoreState = (overrides: Partial<AppState> = {}): AppState => ({
  taskId: null,
  status: null,
  steps: [],
  loading: false,
  skills: [],
  skillsLoading: false,
  selectedSkill: null,
  skillDetailLoading: false,
  skillExecuteResult: null,
  skillExecuting: false,
  taskHistory: [],
  historyLoading: false,
  submitTask: vi.fn(),
  loadSkills: vi.fn(),
  loadSkillDetail: vi.fn(),
  selectSkill: vi.fn(),
  executeSkill: vi.fn(),
  loadTaskHistory: vi.fn(),
  ...overrides,
})
