import { useEffect } from 'react'
import { useTaskStore, SkillInfo } from '../stores/taskStore'

interface SkillListProps {
  onSelectSkill: (skillId: string) => void
}

export default function SkillList({ onSelectSkill }: SkillListProps) {
  const skills = useTaskStore((s) => s.skills)
  const skillsLoading = useTaskStore((s) => s.skillsLoading)
  const loadSkills = useTaskStore((s) => s.loadSkills)

  useEffect(() => {
    loadSkills()
  }, [loadSkills])

  if (skillsLoading) {
    return <div style={styles.loading}>正在加载技能列表...</div>
  }

  if (skills.length === 0) {
    return <div style={styles.empty}>暂无可用技能</div>
  }

  const categoryColors: Record<string, string> = {
    editor: '#3b82f6',
    browser: '#10b981',
    file: '#f59e0b',
    default: '#6b7280',
  }

  return (
    <div style={styles.container}>
      <h2 style={styles.heading}>可用技能</h2>
      <div style={styles.grid}>
        {skills.map((skill: SkillInfo) => {
          const color = categoryColors[skill.category.toLowerCase()] || categoryColors.default
          return (
            <div
              key={skill.skill_id}
              style={styles.card}
              onClick={() => onSelectSkill(skill.skill_id)}
              role="button"
              tabIndex={0}
            >
              <div style={styles.cardHeader}>
                <span style={{ ...styles.badge, backgroundColor: color }}>
                  {skill.category}
                </span>
                <span style={styles.version}>v{skill.version}</span>
              </div>
              <h3 style={styles.title}>{skill.display_name}</h3>
              <p style={styles.description}>{skill.description}</p>
              <div style={styles.footer}>
                <span style={styles.steps}>{skill.step_count} 个步骤</span>
                <span style={styles.id}>{skill.skill_id}</span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    padding: '1rem',
  },
  heading: {
    fontSize: '1.25rem',
    fontWeight: 600,
    marginBottom: '1rem',
    color: '#1f2937',
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
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
    gap: '1rem',
  },
  card: {
    border: '1px solid #e5e7eb',
    borderRadius: '8px',
    padding: '1rem',
    cursor: 'pointer',
    transition: 'box-shadow 0.2s, border-color 0.2s',
    backgroundColor: '#fff',
  },
  cardHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '0.75rem',
  },
  badge: {
    display: 'inline-block',
    padding: '0.25rem 0.5rem',
    borderRadius: '4px',
    color: '#fff',
    fontSize: '0.75rem',
    fontWeight: 500,
    textTransform: 'capitalize',
  },
  version: {
    fontSize: '0.75rem',
    color: '#9ca3af',
  },
  title: {
    fontSize: '1rem',
    fontWeight: 600,
    marginBottom: '0.5rem',
    color: '#111827',
  },
  description: {
    fontSize: '0.875rem',
    color: '#6b7280',
    marginBottom: '0.75rem',
    lineHeight: 1.4,
  },
  footer: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    fontSize: '0.75rem',
    color: '#9ca3af',
    borderTop: '1px solid #f3f4f6',
    paddingTop: '0.5rem',
  },
  steps: {
    fontWeight: 500,
  },
  id: {
    fontFamily: 'monospace',
  },
}
