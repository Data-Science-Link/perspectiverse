import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import Observatory from './components/Observatory'
import Sidebar from './components/Sidebar'
import SiteChrome from './components/SiteChrome'
import SiteMenu from './components/SiteMenu'
import SitePage from './components/SitePage'
import WelcomeModal from './components/WelcomeModal'
import { CATEGORIES, categoryCounts, skyMaxVolume, skyTopics } from './lib/categories'
import { SITE_TAGLINE, isWelcomeHidden } from './lib/copy'
import { readSelectionFromURL, resetScroll, writeSelectionToURL } from './lib/navigation'
import { pageById } from './lib/pages'
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
  const [page, setPage] = useState(boot.page)
  const [menuOpen, setMenuOpen] = useState(false)
  const [welcomeOpen, setWelcomeOpen] = useState(false)
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
        if (!isWelcomeHidden() && !boot.page) setWelcomeOpen(true)
      })
      .catch((err) => setError(err.message))
  }, [boot.page])

  const visibleTopics = useMemo(
    () => (data ? skyTopics(data.topics, category) : []),
    [data, category],
  )
  const volumeMax = useMemo(() => skyMaxVolume(visibleTopics), [visibleTopics])

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
    setPage(next.page ?? null)
    writeSelectionToURL({ ...next, page: next.page ?? null }, mode)
  }

  const selectTopic = (topicId) => {
    commitSelection({ category, topicId, perspectiveId: null, page: null })
  }

  const selectPerspective = (perspectiveId) => {
    commitSelection({ category, topicId: selectedTopicId, perspectiveId, page: null })
  }

  const openPage = (pageId) => {
    commitSelection({ category, topicId: null, perspectiveId: null, page: pageId })
    setMenuOpen(false)
  }

  const stepBack = () => {
    if (page) {
      commitSelection({ category, topicId: null, perspectiveId: null, page: null })
      return
    }
    if (selectedPerspectiveId) {
      commitSelection({ category, topicId: selectedTopicId, perspectiveId: null, page: null })
      return
    }
    commitSelection({ category, topicId: null, perspectiveId: null, page: null })
  }

  const clearSelection = () => {
    commitSelection({ category, topicId: null, perspectiveId: null, page: null })
  }

  const changeCategory = (next) => {
    commitSelection({ category: next, topicId: null, perspectiveId: null, page: null })
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
      setPage(snap.page)
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
  }, [selectedTopicId, selectedPerspectiveId, page, menuOpen, welcomeOpen])

  useEffect(() => {
    if (!data) return
    if (!selectedTopicId) return
    if (selectedTopic) return
    writeSelectionToURL({ category, topicId: null, perspectiveId: null, page }, 'replace')
    setSelectedTopicId(null)
    setSelectedPerspectiveId(null)
  }, [data, selectedTopic, selectedTopicId, category, page])

  useEffect(() => {
    const meta = pageById(page)
    document.title = meta
      ? `${meta.title} | Perspectiverse`
      : 'Perspectiverse | Discourse Universe'
    return () => {
      document.title = 'Perspectiverse | Discourse Universe'
    }
  }, [page])

  if (error) {
    return (
      <div className="boot-screen">
        <p>Could not load this week&apos;s map.</p>
        <p className="boot-detail">{error}</p>
        <p className="boot-detail">Try refreshing the page.</p>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="boot-screen">
        <p>Loading this week&apos;s map…</p>
      </div>
    )
  }

  const sitePage = pageById(page)
  const drilled = Boolean(selectedTopic) || Boolean(sitePage)
  const showSky = !sitePage && !(isMobile && selectedTopic)
  const chromeTitle = sitePage?.title
    ?? selectedPerspective?.title
    ?? selectedTopic?.name
    ?? 'Perspectiverse'
  const chromeSubtitle = sitePage
    ? sitePage.subtitle
    : selectedPerspective
      ? selectedTopic.name
      : selectedTopic
        ? `${selectedTopic.body?.name} · ${selectedTopic.category}`
        : SITE_TAGLINE
  const backLabel = sitePage
    ? 'Back to the solar system'
    : selectedPerspective
      ? `Back to ${selectedTopic.name}`
      : 'Back to the solar system'

  return (
    <div
      ref={shellRef}
      className={`app-shell ${isMobile ? 'is-mobile' : ''} ${selectedTopic && !sitePage ? 'is-drilled' : ''} ${sitePage ? 'is-page' : ''}`}
    >
      <SiteChrome
        drilled={drilled}
        title={chromeTitle}
        subtitle={chromeSubtitle}
        tagline={!selectedTopic}
        backLabel={backLabel}
        onBack={stepBack}
        onOpenMenu={() => setMenuOpen(true)}
      />
      {sitePage && (
        <SitePage pageId={sitePage.id} data={data} onOpenPage={openPage} />
      )}
      {showSky && (
        <Observatory
          topics={visibleTopics}
          selectedTopicId={selectedTopicId}
          selectedPerspectiveId={selectedPerspectiveId}
          category={category}
          isMobile={isMobile}
          volumeMax={volumeMax}
          onSelectTopic={selectTopic}
          onSelectPerspective={selectPerspective}
          onClearSelection={clearSelection}
        />
      )}
      {!sitePage && (
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
      )}
      <SiteMenu
        open={menuOpen}
        topics={visibleTopics}
        categories={CATEGORIES}
        category={category}
        counts={categoryCounts(data.topics)}
        currentPage={page}
        onClose={() => setMenuOpen(false)}
        onCategory={changeCategory}
        onSelectTopic={selectTopic}
        onOpenPage={openPage}
        onShowWelcome={() => {
          setMenuOpen(false)
          setWelcomeOpen(true)
        }}
      />
      <WelcomeModal open={welcomeOpen} onClose={() => setWelcomeOpen(false)} />
    </div>
  )
}
