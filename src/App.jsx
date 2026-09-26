import { useEffect, useMemo, useState } from 'react'
import Observatory from './components/Observatory'
import Sidebar from './components/Sidebar'

export default function App() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [selectedTopicId, setSelectedTopicId] = useState(null)
  const [selectedPerspectiveId, setSelectedPerspectiveId] = useState(null)

  useEffect(() => {
    const url = `${import.meta.env.BASE_URL}data.json`
    fetch(url)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Could not load ${url}`)
        }
        return response.json()
      })
      .then((payload) => {
        const topics = [...(payload.topics ?? [])].sort(
          (a, b) => b.total_volume_percent - a.total_volume_percent,
        )
        setData({ ...payload, topics })
      })
      .catch((err) => setError(err.message))
  }, [])

  const selectedTopic = useMemo(
    () => data?.topics.find((topic) => topic.id === selectedTopicId) ?? null,
    [data, selectedTopicId],
  )
  const selectedPerspective = useMemo(
    () => selectedTopic?.perspectives.find((face) => face.id === selectedPerspectiveId) ?? null,
    [selectedTopic, selectedPerspectiveId],
  )

  const selectTopic = (topicId) => {
    setSelectedTopicId(topicId)
    setSelectedPerspectiveId(null)
  }

  const selectPerspective = (perspectiveId) => {
    setSelectedPerspectiveId(perspectiveId)
  }

  const clearSelection = () => {
    setSelectedTopicId(null)
    setSelectedPerspectiveId(null)
  }

  if (error) {
    return (
      <div className="boot-screen">
        <p>The observatory could not load its sky.</p>
        <p className="boot-detail">{error}</p>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="boot-screen">
        <p>Charting this week&apos;s discourse…</p>
      </div>
    )
  }

  return (
    <div className="app-shell">
      <Observatory
        topics={data.topics}
        selectedTopicId={selectedTopicId}
        selectedPerspectiveId={selectedPerspectiveId}
        onSelectTopic={selectTopic}
        onSelectPerspective={selectPerspective}
        onClearSelection={clearSelection}
      />
      <Sidebar
        data={data}
        selectedTopic={selectedTopic}
        selectedPerspective={selectedPerspective}
        onSelectTopic={selectTopic}
        onSelectPerspective={selectPerspective}
        onClearSelection={clearSelection}
      />
    </div>
  )
}
