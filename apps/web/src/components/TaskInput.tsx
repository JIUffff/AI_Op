import { useState } from 'react'
import { useTaskStore } from '../stores/taskStore'

function TaskInput() {
  const [input, setInput] = useState('')
  const { submitTask, loading } = useTaskStore()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || loading) return
    await submitTask(input)
  }

  return (
    <form onSubmit={handleSubmit} style={{ marginBottom: '1rem' }}>
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="请输入任务内容..."
        style={{ width: '100%', padding: '0.5rem', fontSize: '1rem' }}
        disabled={loading}
      />
      <button
        type="submit"
        disabled={loading || !input.trim()}
        style={{ marginTop: '0.5rem', padding: '0.5rem 1rem' }}
      >
        {loading ? '执行中...' : '执行任务'}
      </button>
    </form>
  )
}

export default TaskInput
