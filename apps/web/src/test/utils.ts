import { beforeEach } from 'vitest'
import { create } from 'zustand'
import type { AppState } from '../stores/taskStore'

export const createMockTaskStore = (overrides: Partial<AppState> = {}) => {
  const defaults: AppState = {
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
    submitTask: async () => {},
    loadSkills: async () => {},
    loadSkillDetail: async () => {},
    selectSkill: () => {},
    executeSkill: async () => {},
    loadTaskHistory: async () => {},
  }

  return create<AppState>(() => ({ ...defaults, ...overrides }))
}

beforeEach(() => {
  vi.clearAllMocks()
})
