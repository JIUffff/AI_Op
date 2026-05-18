import { create } from 'zustand'

export interface SkillStep {
  step_id: string
  action: string
  engine: string
  params: Record<string, unknown>
  timeout: number
  retry_count: number
  verify: string | null
}

export interface SkillDetail extends SkillInfo {
  steps: SkillStep[]
}

export interface SkillInfo {
  skill_id: string
  display_name: string
  version: string
  description: string
  category: string
  step_count: number
}

export interface TaskRecord {
  task_id: string
  status: string
  steps: string[]
  started_at: string | null
  finished_at: string | null
}

export interface SkillExecuteResult {
  success: boolean
  result: Record<string, unknown> | null
  error: Record<string, unknown> | null
  steps_executed: Array<Record<string, unknown>>
}

interface AppState {
  taskId: string | null
  status: string | null
  steps: string[]
  loading: boolean

  skills: SkillInfo[]
  skillsLoading: boolean
  selectedSkill: SkillDetail | null
  skillDetailLoading: boolean
  skillExecuteResult: SkillExecuteResult | null
  skillExecuting: boolean

  taskHistory: TaskRecord[]
  historyLoading: boolean

  submitTask: (input: string) => Promise<void>
  loadSkills: () => Promise<void>
  loadSkillDetail: (skillId: string) => Promise<void>
  selectSkill: (skill: SkillDetail | null) => void
  executeSkill: (skillId: string, params: Record<string, unknown>) => Promise<void>
  loadTaskHistory: () => Promise<void>
}

export const useTaskStore = create<AppState>((set) => ({
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

  submitTask: async (input: string) => {
    set({ loading: true, steps: [], status: null })
    try {
      const res = await fetch('/api/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_input: input }),
      })
      const data = await res.json()
      set({ taskId: data.task_id, status: data.status, steps: data.steps, loading: false })
    } catch (e) {
      set({ status: 'error', steps: ['Error: ' + (e as Error).message], loading: false })
    }
  },

  loadSkills: async () => {
    set({ skillsLoading: true })
    try {
      const res = await fetch('/api/skills')
      const data = await res.json()
      set({ skills: data, skillsLoading: false })
    } catch (e) {
      set({ skills: [], skillsLoading: false })
    }
  },

  loadSkillDetail: async (skillId: string) => {
    set({ skillDetailLoading: true, selectedSkill: null })
    try {
      const res = await fetch(`/api/skills/${skillId}`)
      const data = await res.json()
      set({ selectedSkill: data, skillDetailLoading: false })
    } catch (e) {
      set({ selectedSkill: null, skillDetailLoading: false })
    }
  },

  selectSkill: (skill: SkillDetail | null) => {
    set({ selectedSkill: skill, skillExecuteResult: null })
  },

  executeSkill: async (skillId: string, params: Record<string, unknown>) => {
    set({ skillExecuting: true, skillExecuteResult: null })
    try {
      const res = await fetch('/api/skills/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skill_id: skillId, params }),
      })
      const data = await res.json()
      set({ skillExecuteResult: data, skillExecuting: false })
    } catch (e) {
      set({
        skillExecuteResult: {
          success: false,
          result: null,
          error: { message: (e as Error).message },
          steps_executed: [],
        },
        skillExecuting: false,
      })
    }
  },

  loadTaskHistory: async () => {
    set({ historyLoading: true })
    try {
      const res = await fetch('/api/tasks')
      const data = await res.json()
      set({ taskHistory: data.tasks || [], historyLoading: false })
    } catch (e) {
      set({ taskHistory: [], historyLoading: false })
    }
  },
}))
