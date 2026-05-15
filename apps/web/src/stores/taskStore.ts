import { create } from 'zustand'

interface TaskState {
  taskId: string | null
  status: string | null
  steps: string[]
  loading: boolean
  submitTask: (input: string) => Promise<void>
}

export const useTaskStore = create<TaskState>((set) => ({
  taskId: null,
  status: null,
  steps: [],
  loading: false,
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
}))
