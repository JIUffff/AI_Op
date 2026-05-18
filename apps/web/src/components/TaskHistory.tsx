import { useEffect, useState } from 'react'
import { useTaskStore, TaskRecord } from '../stores/taskStore'

export default function TaskHistory() {
  const taskHistory = useTaskStore((s) => s.taskHistory)
  const historyLoading = useTaskStore((s) => s.historyLoading)
  const loadTaskHistory = useTaskStore((s) => s.loadTaskHistory)
  const [selectedTask, setSelectedTask] = useState<TaskRecord | null>(null)

  useEffect(() => {
    loadTaskHistory()
  }, [loadTaskHistory])

  const handleRefresh = () => {
    loadTaskHistory()
    setSelectedTask(null)
  }

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-'
    return new Date(dateStr).toLocaleString()
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return '#10b981'
      case 'failed':
      case 'error':
        return '#ef4444'
      case 'running':
        return '#f59e0b'
      default:
        return '#6b7280'
    }
  }

  if (historyLoading) {
    return <div style={styles.loading}>正在加载任务历史...</div>
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h2 style={styles.heading}>任务历史</h2>
        <button onClick={handleRefresh} style={styles.refreshButton}>
          刷新
        </button>
      </div>

      {taskHistory.length === 0 ? (
        <div style={styles.empty}>暂无任务记录</div>
      ) : (
        <div style={styles.list}>
          {taskHistory.map((task) => (
            <div
              key={task.task_id}
              style={{
                ...styles.taskItem,
                borderLeftColor: getStatusColor(task.status),
              }}
              onClick={() => setSelectedTask(task)}
              role="button"
              tabIndex={0}
            >
              <div style={styles.taskHeader}>
                <span style={styles.taskId}>{task.task_id}</span>
                <span
                  style={{
                    ...styles.taskStatus,
                    backgroundColor: getStatusColor(task.status),
                  }}
                >
                  {task.status}
                </span>
              </div>
              <div style={styles.taskMeta}>
                <span>开始：{formatDate(task.started_at)}</span>
                <span>完成：{formatDate(task.finished_at)}</span>
              </div>
              <div style={styles.taskSteps}>
                {task.steps.length} 个步骤
              </div>
            </div>
          ))}
        </div>
      )}

      {selectedTask && (
        <div style={styles.detailPanel}>
          <div style={styles.detailHeader}>
            <h3 style={styles.detailTitle}>任务详情</h3>
            <button onClick={() => setSelectedTask(null)} style={styles.closeButton}>
              ×
            </button>
          </div>
          <div style={styles.detailContent}>
            <div style={styles.detailRow}>
              <strong>任务 ID：</strong>
              <span style={styles.mono}>{selectedTask.task_id}</span>
            </div>
            <div style={styles.detailRow}>
              <strong>状态：</strong>
              <span
                style={{
                  ...styles.statusBadge,
                  backgroundColor: getStatusColor(selectedTask.status),
                }}
              >
                {selectedTask.status}
              </span>
            </div>
            <div style={styles.detailRow}>
              <strong>开始时间：</strong>
              <span>{formatDate(selectedTask.started_at)}</span>
            </div>
            <div style={styles.detailRow}>
              <strong>完成时间：</strong>
              <span>{formatDate(selectedTask.finished_at)}</span>
            </div>
            <div style={styles.stepsSection}>
              <strong>步骤：</strong>
              <div style={styles.stepsList}>
                {selectedTask.steps.map((step, idx) => (
                  <div key={idx} style={styles.stepItem}>
                    <span style={styles.stepIndex}>{idx + 1}</span>
                    <span style={styles.stepContent}>{step}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    padding: '1rem',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '1rem',
  },
  heading: {
    fontSize: '1.25rem',
    fontWeight: 600,
    color: '#1f2937',
    margin: 0,
  },
  refreshButton: {
    padding: '0.5rem 1rem',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    backgroundColor: '#fff',
    cursor: 'pointer',
    fontSize: '0.875rem',
  },
  loading: {
    padding: '2rem',
    textAlign: 'center',
    color: '#6b7280',
  },
  empty: {
    padding: '2rem',
    textAlign: 'center',
    color: '#6b7280',
  },
  list: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.75rem',
  },
  taskItem: {
    padding: '1rem',
    border: '1px solid #e5e7eb',
    borderLeftWidth: '4px',
    borderRadius: '6px',
    cursor: 'pointer',
    backgroundColor: '#fff',
    transition: 'box-shadow 0.2s',
  },
  taskHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '0.5rem',
  },
  taskId: {
    fontFamily: 'monospace',
    fontSize: '0.875rem',
    fontWeight: 600,
    color: '#374151',
  },
  taskStatus: {
    padding: '0.25rem 0.5rem',
    borderRadius: '4px',
    color: '#fff',
    fontSize: '0.75rem',
    fontWeight: 500,
    textTransform: 'capitalize',
  },
  taskMeta: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: '0.75rem',
    color: '#6b7280',
    marginBottom: '0.5rem',
  },
  taskSteps: {
    fontSize: '0.75rem',
    color: '#9ca3af',
  },
  detailPanel: {
    position: 'fixed',
    right: 0,
    top: 0,
    width: '400px',
    height: '100vh',
    backgroundColor: '#fff',
    boxShadow: '-4px 0 12px rgba(0,0,0,0.1)',
    padding: '1.5rem',
    overflow: 'auto',
    zIndex: 1000,
  },
  detailHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '1rem',
    paddingBottom: '0.75rem',
    borderBottom: '1px solid #e5e7eb',
  },
  detailTitle: {
    fontSize: '1.125rem',
    fontWeight: 600,
    color: '#1f2937',
    margin: 0,
  },
  closeButton: {
    background: 'none',
    border: 'none',
    fontSize: '1.5rem',
    cursor: 'pointer',
    color: '#6b7280',
    padding: '0 0.5rem',
  },
  detailContent: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.75rem',
  },
  detailRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    fontSize: '0.875rem',
  },
  mono: {
    fontFamily: 'monospace',
    fontSize: '0.8rem',
  },
  statusBadge: {
    padding: '0.25rem 0.5rem',
    borderRadius: '4px',
    color: '#fff',
    fontSize: '0.75rem',
    fontWeight: 500,
    textTransform: 'capitalize',
  },
  stepsSection: {
    marginTop: '0.5rem',
  },
  stepsList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.5rem',
    marginTop: '0.5rem',
  },
  stepItem: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: '0.5rem',
  },
  stepIndex: {
    width: '20px',
    height: '20px',
    borderRadius: '50%',
    backgroundColor: '#e5e7eb',
    color: '#374151',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '0.65rem',
    fontWeight: 600,
    flexShrink: 0,
  },
  stepContent: {
    fontSize: '0.8rem',
    color: '#4b5563',
    fontFamily: 'monospace',
    wordBreak: 'break-all',
  },
}
