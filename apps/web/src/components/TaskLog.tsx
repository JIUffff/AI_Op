import { useTaskStore } from '../stores/taskStore'

const statusLabels: Record<string, string> = {
  pending: '等待中',
  running: '执行中',
  completed: '已完成',
  failed: '失败',
  error: '错误',
  paused: '已暂停',
  cancelled: '已取消',
}

function TaskLog() {
  const { steps, status, taskId } = useTaskStore()

  if (!steps.length) return null

  const statusText = status ? statusLabels[status.toLowerCase()] || status : null

  return (
    <div style={{ marginTop: '1rem' }}>
      <h3>任务：{taskId}</h3>
      <div style={{ background: '#f5f5f5', padding: '1rem', borderRadius: '4px' }}>
        {steps.map((step, i) => (
          <div key={i} style={{ fontFamily: 'monospace', fontSize: '0.9rem' }}>
            [{i + 1}] {step}
          </div>
        ))}
      </div>
      {statusText && (
        <p style={{ marginTop: '0.5rem', fontWeight: 'bold' }}>
          状态：{statusText}
        </p>
      )}
    </div>
  )
}

export default TaskLog
