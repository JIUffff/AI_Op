import { useState } from 'react'
import { useTaskStore, SkillDetail } from '../stores/taskStore'

interface SkillExecutorProps {
  skill: SkillDetail
  onBack: () => void
}

export default function SkillExecutor({ skill, onBack }: SkillExecutorProps) {
  const [params, setParams] = useState<Record<string, string>>({})
  const executeSkill = useTaskStore((s) => s.executeSkill)
  const skillExecuting = useTaskStore((s) => s.skillExecuting)
  const skillExecuteResult = useTaskStore((s) => s.skillExecuteResult)

  const handleParamChange = (key: string, value: string) => {
    setParams((prev) => ({ ...prev, [key]: value }))
  }

  const handleExecute = async () => {
    await executeSkill(skill.skill_id, params)
  }

  const handleBack = () => {
    onBack()
  }

  const extractParams = () => {
    const paramKeys = new Set<string>()
    const steps = skill.steps || []
    for (const step of steps) {
      const stepParams = step.params || {}
      for (const [, value] of Object.entries(stepParams)) {
        if (typeof value === 'string') {
          const matches = value.matchAll(/\{(\w+)\}/g)
          for (const match of matches) {
            paramKeys.add(match[1])
          }
        }
      }
    }
    return Array.from(paramKeys)
  }

  const requiredParams = extractParams()

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <button onClick={handleBack} style={styles.backButton}>
          ← 返回
        </button>
        <h2 style={styles.title}>{skill.display_name}</h2>
        <span style={styles.version}>v{skill.version}</span>
      </div>

      <div style={styles.section}>
        <h3 style={styles.sectionTitle}>参数</h3>
        {requiredParams.length === 0 ? (
          <p style={styles.noParams}>此技能无需额外参数</p>
        ) : (
          <div style={styles.paramGrid}>
            {requiredParams.map((key) => (
              <div key={key} style={styles.paramField}>
                <label style={styles.label}>{key}</label>
                <input
                  type="text"
                  value={params[key] || ''}
                  onChange={(e) => handleParamChange(key, e.target.value)}
                  style={styles.input}
                  placeholder={`请输入 ${key}`}
                />
              </div>
            ))}
          </div>
        )}
      </div>

      <div style={styles.actions}>
        <button
          onClick={handleExecute}
          disabled={skillExecuting}
          style={{
            ...styles.executeButton,
            opacity: skillExecuting ? 0.6 : 1,
            cursor: skillExecuting ? 'not-allowed' : 'pointer',
          }}
        >
          {skillExecuting ? '执行中...' : '执行技能'}
        </button>
      </div>

      {skillExecuteResult && (
        <div style={styles.result}>
          <h3 style={styles.sectionTitle}>执行结果</h3>
          <div
            style={{
              ...styles.resultBox,
              borderColor: skillExecuteResult.success ? '#10b981' : '#ef4444',
            }}
          >
            <div style={styles.resultStatus}>
              <span
                style={{
                  ...styles.statusDot,
                  backgroundColor: skillExecuteResult.success ? '#10b981' : '#ef4444',
                }}
              />
              {skillExecuteResult.success ? '执行成功' : '执行失败'}
            </div>

            {skillExecuteResult.result && (
              <div style={styles.resultDetail}>
                <strong>结果：</strong>
                <pre style={styles.pre}>{JSON.stringify(skillExecuteResult.result, null, 2)}</pre>
              </div>
            )}

            {skillExecuteResult.error && (
              <div style={styles.resultDetail}>
                <strong>错误：</strong>
                <pre style={styles.preError}>
                  {JSON.stringify(skillExecuteResult.error, null, 2)}
                </pre>
              </div>
            )}

            {skillExecuteResult.steps_executed.length > 0 && (
              <div style={styles.resultDetail}>
                <strong>已执行步骤：</strong>
                <div style={styles.stepsList}>
                  {skillExecuteResult.steps_executed.map((step, idx) => (
                    <div key={idx} style={styles.stepItem}>
                      <span style={styles.stepIndex}>{idx + 1}</span>
                      <span style={styles.stepAction}>{step.action || '未知操作'}</span>
                      {step.result !== undefined && (
                        <span style={styles.stepResult}>
                          {typeof step.result === 'string'
                            ? step.result
                            : JSON.stringify(step.result)}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
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
    alignItems: 'center',
    gap: '1rem',
    marginBottom: '1.5rem',
  },
  backButton: {
    padding: '0.5rem 1rem',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    backgroundColor: '#fff',
    cursor: 'pointer',
    fontSize: '0.875rem',
  },
  title: {
    fontSize: '1.25rem',
    fontWeight: 600,
    color: '#1f2937',
    margin: 0,
  },
  version: {
    fontSize: '0.75rem',
    color: '#9ca3af',
  },
  section: {
    marginBottom: '1.5rem',
  },
  sectionTitle: {
    fontSize: '1rem',
    fontWeight: 600,
    marginBottom: '0.75rem',
    color: '#374151',
  },
  noParams: {
    color: '#6b7280',
    fontStyle: 'italic',
  },
  paramGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
    gap: '1rem',
  },
  paramField: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.25rem',
  },
  label: {
    fontSize: '0.875rem',
    fontWeight: 500,
    color: '#374151',
    textTransform: 'capitalize',
  },
  input: {
    padding: '0.5rem 0.75rem',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    fontSize: '0.875rem',
    outline: 'none',
  },
  actions: {
    marginBottom: '1.5rem',
  },
  executeButton: {
    padding: '0.75rem 1.5rem',
    backgroundColor: '#3b82f6',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    fontWeight: 600,
    fontSize: '0.875rem',
  },
  result: {
    marginTop: '1rem',
  },
  resultBox: {
    border: '2px solid',
    borderRadius: '8px',
    padding: '1rem',
    backgroundColor: '#f9fafb',
  },
  resultStatus: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    fontSize: '1rem',
    fontWeight: 600,
    marginBottom: '1rem',
  },
  statusDot: {
    width: '10px',
    height: '10px',
    borderRadius: '50%',
    display: 'inline-block',
  },
  resultDetail: {
    marginBottom: '1rem',
  },
  pre: {
    backgroundColor: '#1f2937',
    color: '#e5e7eb',
    padding: '0.75rem',
    borderRadius: '6px',
    fontSize: '0.8rem',
    overflow: 'auto',
    maxHeight: '200px',
  },
  preError: {
    backgroundColor: '#fef2f2',
    color: '#dc2626',
    padding: '0.75rem',
    borderRadius: '6px',
    fontSize: '0.8rem',
    overflow: 'auto',
    maxHeight: '200px',
  },
  stepsList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.5rem',
  },
  stepItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.75rem',
    padding: '0.5rem 0.75rem',
    backgroundColor: '#fff',
    borderRadius: '4px',
    border: '1px solid #e5e7eb',
  },
  stepIndex: {
    width: '24px',
    height: '24px',
    borderRadius: '50%',
    backgroundColor: '#3b82f6',
    color: '#fff',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '0.75rem',
    fontWeight: 600,
  },
  stepAction: {
    fontSize: '0.875rem',
    fontWeight: 500,
    color: '#374151',
  },
  stepResult: {
    marginLeft: 'auto',
    fontSize: '0.75rem',
    color: '#6b7280',
    fontFamily: 'monospace',
  },
}
