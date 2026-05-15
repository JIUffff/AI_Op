import { useState } from 'react'
import { useTaskStore } from './stores/taskStore'

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
        placeholder="Enter a task..."
        style={{ width: '100%', padding: '0.5rem', fontSize: '1rem' }}
        disabled={loading}
      />
      <button
        type="submit"
        disabled={loading || !input.trim()}
        style={{ marginTop: '0.5rem', padding: '0.5rem 1rem' }}
      >
        {loading ? 'Running...' : 'Run Task'}
      </button>
    </form>
  )
}

export default TaskInput
