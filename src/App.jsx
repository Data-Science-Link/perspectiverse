import { useEffect, useMemo, useState } from 'react'
import Observatory from './components/Observatory'
import Sidebar from './components/Sidebar'
import { CATEGORIES, filterTopics } from './lib/categories'

function initialCategory() {
  const requested = new URLSearchParams(window.location.search).get('category')
  if (!requested || requested === 'all') return 'all'
  return requested
}

export default function App() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [category, setCategory] = useState(initialCategory)
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

  const visibleTopics = useMemo(
    () => (data ? filterTopics(data.topics, category) : []),
    [data, category],
  )

  const selectedTopic = useMemo(
    () => visibleTopics.find((topic) => topic.id === selectedTopicId) ?? null,
    [visibleTopics, selectedTopicId],
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

  const changeCategory = (next) => {
    setCategory(next)
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
        topics={visibleTopics}
        selectedTopicId={selectedTopicId}
        selectedPerspectiveId={selectedPerspectiveId}
        category={category}
        onSelectTopic={selectTopic}
        onSelectPerspective={selectPerspective}
        onClearSelection={clearSelection}
      />
      <Sidebar
        data={data}
        topics={visibleTopics}
        categories={CATEGORIES}
        category={category}
        selectedTopic={selectedTopic}
        selectedPerspective={selectedPerspective}
        onSelectTopic={selectTopic}
        onSelectPerspective={selectPerspective}
        onClearSelection={clearSelection}
        onCategory={changeCategory}
      />
    </div>
  )
}
