import { useTaskStore } from '../stores/taskStore'

function TaskLog() {
  const { steps, status, taskId } = useTaskStore()

  if (!steps.length) return null

  return (
    <div style={{ marginTop: '1rem' }}>
      <h3>Task: {taskId}</h3>
      <div style={{ background: '#f5f5f5', padding: '1rem', borderRadius: '4px' }}>
        {steps.map((step, i) => (
          <div key={i} style={{ fontFamily: 'monospace', fontSize: '0.9rem' }}>
            [{i + 1}] {step}
          </div>
        ))}
      </div>
      {status && (
        <p style={{ marginTop: '0.5rem', fontWeight: 'bold' }}>
          Status: {status}
        </p>
      )}
    </div>
  )
}

export default TaskLog
