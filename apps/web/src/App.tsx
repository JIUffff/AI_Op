import { TaskInput } from './components/TaskInput'
import { TaskLog } from './components/TaskLog'

function App() {
  return (
    <div style={{ padding: '1rem', maxWidth: '48rem', margin: '0 auto' }}>
      <h1>Local AI Skill OS</h1>
      <TaskInput />
      <TaskLog />
    </div>
  )
}

export default App
