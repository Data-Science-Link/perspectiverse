import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import Observatory from './components/Observatory'
import Sidebar from './components/Sidebar'
import SiteChrome from './components/SiteChrome'
import SiteMenu from './components/SiteMenu'
import { CATEGORIES, categoryCounts, filterTopics } from './lib/categories'
import { decorateVisibleTopics } from './lib/planets'
import { readSelectionFromURL, resetScroll, writeSelectionToURL } from './lib/navigation'
import { useIsMobile } from './lib/useMediaQuery'

function initialSelection() {
  return readSelectionFromURL()
}

export default function App() {
  const boot = useMemo(initialSelection, [])
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [category, setCategory] = useState(boot.category)
  const [selectedTopicId, setSelectedTopicId] = useState(boot.topicId)
  const [selectedPerspectiveId, setSelectedPerspectiveId] = useState(boot.perspectiveId)
  const [menuOpen, setMenuOpen] = useState(false)
  const isMobile = useIsMobile()
  const shellRef = useRef(null)

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
    () => (data ? decorateVisibleTopics(data.topics, filterTopics(data.topics, category)) : []),
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

  const commitSelection = (next, mode = 'push') => {
    setCategory(next.category)
    setSelectedTopicId(next.topicId)
    setSelectedPerspectiveId(next.perspectiveId)
    writeSelectionToURL(next, mode)
  }

  const selectTopic = (topicId) => {
    commitSelection({ category, topicId, perspectiveId: null })
  }

  const selectPerspective = (perspectiveId) => {
    commitSelection({ category, topicId: selectedTopicId, perspectiveId })
  }

  const stepBack = () => {
    if (selectedPerspectiveId) {
      commitSelection({ category, topicId: selectedTopicId, perspectiveId: null })
      return
    }
    commitSelection({ category, topicId: null, perspectiveId: null })
  }

  const clearSelection = () => {
    commitSelection({ category, topicId: null, perspectiveId: null })
  }

  const changeCategory = (next) => {
    commitSelection({ category: next, topicId: null, perspectiveId: null })
  }

  useEffect(() => {
    const previous = window.history.scrollRestoration
    if ('scrollRestoration' in window.history) {
      window.history.scrollRestoration = 'manual'
    }
    const onPop = () => {
      const snap = readSelectionFromURL()
      setCategory(snap.category)
      setSelectedTopicId(snap.topicId)
      setSelectedPerspectiveId(snap.perspectiveId)
    }
    window.addEventListener('popstate', onPop)
    return () => {
      window.removeEventListener('popstate', onPop)
      if ('scrollRestoration' in window.history) {
        window.history.scrollRestoration = previous
      }
    }
  }, [])

  useLayoutEffect(() => {
    resetScroll(shellRef.current)
  }, [selectedTopicId, selectedPerspectiveId, menuOpen])

  useEffect(() => {
    if (!data) return
    if (!selectedTopicId) return
    if (selectedTopic) return
    writeSelectionToURL({ category, topicId: null, perspectiveId: null }, 'replace')
    setSelectedTopicId(null)
    setSelectedPerspectiveId(null)
  }, [data, selectedTopic, selectedTopicId, category])

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

  const drilled = Boolean(selectedTopic)
  const chromeTitle = selectedPerspective?.title
    ?? selectedTopic?.name
    ?? 'Perspectiverse'
  const chromeSubtitle = selectedPerspective
    ? selectedTopic.name
    : selectedTopic
      ? `${selectedTopic.body?.name} · ${selectedTopic.category}`
      : isMobile
        ? 'Tap a cube to begin'
        : 'Discourse Universe'

  return (
    <div
      ref={shellRef}
      className={`app-shell ${isMobile ? 'is-mobile' : ''} ${drilled ? 'is-drilled' : ''}`}
    >
      <SiteChrome
        drilled={drilled}
        title={chromeTitle}
        subtitle={isMobile && !drilled ? 'Tap a cube to begin' : chromeSubtitle}
        backLabel={selectedPerspective ? `Back to ${selectedTopic.name}` : 'Back to the sky'}
        onBack={stepBack}
        onOpenMenu={() => setMenuOpen(true)}
      />
      <Observatory
        topics={visibleTopics}
        selectedTopicId={selectedTopicId}
        selectedPerspectiveId={selectedPerspectiveId}
        category={category}
        isMobile={isMobile}
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
        isMobile={isMobile}
        onSelectTopic={selectTopic}
        onSelectPerspective={selectPerspective}
        onClearSelection={clearSelection}
        onCategory={changeCategory}
      />
      <SiteMenu
        open={menuOpen}
        data={data}
        topics={visibleTopics}
        categories={CATEGORIES}
        category={category}
        counts={categoryCounts(data.topics)}
        onClose={() => setMenuOpen(false)}
        onCategory={changeCategory}
        onSelectTopic={selectTopic}
      />
    </div>
  )
}
