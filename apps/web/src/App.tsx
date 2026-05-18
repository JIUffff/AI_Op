import { useState } from 'react'
import TaskInput from './components/TaskInput'
import TaskLog from './components/TaskLog'
import SkillList from './components/SkillList'
import SkillExecutor from './components/SkillExecutor'
import TaskHistory from './components/TaskHistory'
import { useTaskStore, SkillDetail } from './stores/taskStore'

type Tab = 'tasks' | 'skills' | 'history'

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('tasks')
  const selectedSkill = useTaskStore((s) => s.selectedSkill)
  const skillDetailLoading = useTaskStore((s) => s.skillDetailLoading)
  const loadSkillDetail = useTaskStore((s) => s.loadSkillDetail)
  const selectSkill = useTaskStore((s) => s.selectSkill)

  const handleSelectSkill = async (skillId: string) => {
    await loadSkillDetail(skillId)
  }

  const handleBackFromExecutor = () => {
    selectSkill(null)
  }

  const tabs: Array<{ key: Tab; label: string }> = [
    { key: 'tasks', label: '任务' },
    { key: 'skills', label: '技能' },
    { key: 'history', label: '历史' },
  ]

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h1 style={styles.title}>本地 AI 技能操作系统</h1>
        <nav style={styles.nav}>
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              style={{
                ...styles.tab,
                ...(activeTab === tab.key ? styles.tabActive : {}),
              }}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </header>

      <main style={styles.main}>
        {activeTab === 'tasks' && (
          <>
            <TaskInput />
            <TaskLog />
          </>
        )}

        {activeTab === 'skills' && !selectedSkill && (
          <SkillList onSelectSkill={handleSelectSkill} />
        )}

        {activeTab === 'skills' && skillDetailLoading && (
          <div style={{ padding: '2rem', textAlign: 'center', color: '#6b7280' }}>正在加载技能详情...</div>
        )}

        {activeTab === 'skills' && selectedSkill && (
          <SkillExecutor skill={selectedSkill} onBack={handleBackFromExecutor} />
        )}

        {activeTab === 'history' && <TaskHistory />}
      </main>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    maxWidth: '64rem',
    margin: '0 auto',
    padding: '0 1rem',
    minHeight: '100vh',
    backgroundColor: '#f9fafb',
  },
  header: {
    display: 'flex',
    flexDirection: 'column',
    gap: '1rem',
    paddingTop: '1.5rem',
    paddingBottom: '1rem',
    borderBottom: '1px solid #e5e7eb',
    marginBottom: '1.5rem',
  },
  title: {
    fontSize: '1.5rem',
    fontWeight: 700,
    color: '#111827',
    margin: 0,
  },
  nav: {
    display: 'flex',
    gap: '0.5rem',
  },
  tab: {
    padding: '0.5rem 1rem',
    border: 'none',
    borderRadius: '6px',
    backgroundColor: 'transparent',
    color: '#6b7280',
    fontSize: '0.875rem',
    fontWeight: 500,
    cursor: 'pointer',
    transition: 'background-color 0.2s, color 0.2s',
  },
  tabActive: {
    backgroundColor: '#3b82f6',
    color: '#fff',
  },
  main: {
    paddingBottom: '2rem',
  },
}

export default App
