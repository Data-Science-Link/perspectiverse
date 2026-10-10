const STOP = new Set(
  `a an the of to and or in on for with from that this is are was were be it its their they we you i not but as at by if so than then into over about just more most have has had will would can could should them there here what when where which who how your our out only some very much many also been being said says such other than ever even still back well make made want need going really right left something anything nothing everything people person think thought after before again around through under while whose don does did doing done now own same too way who new see two let put say she use its may day get him his her`.split(
    /\s+/,
  ),
)

function clean(text) {
  return String(text || '')
    .replace(/https?:\/\/\S+/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

const ABBR = /^(?:mr|mrs|ms|dr|st|jr|sr|prof|gen|sen|rep|gov|lt|col|sgt|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec|vs|etc|inc|ltd|co|am|pm)$/i

export function splitSentences(text) {
  const cleaned = clean(text)
  if (!cleaned) return []
  const found = []
  let start = 0
  for (let index = 0; index < cleaned.length; index += 1) {
    const mark = cleaned[index]
    if (!/[.!?]/.test(mark)) continue
    const next = cleaned[index + 1]
    if (next && !/\s/.test(next)) continue
    if (mark === '.') {
      const word = (cleaned.slice(start, index).match(/[A-Za-z]+$/) || [''])[0]
      const initial = word.length === 1 && word === word.toUpperCase()
      if (ABBR.test(word) || initial) continue
    }
    const piece = cleaned.slice(start, index + 1).trim()
    if (piece) found.push(piece)
    start = index + 1
    while (cleaned[start] === ' ') start += 1
    index = start - 1
  }
  let tail = cleaned.slice(start).trim()
  if (tail) {
    if (!/[.!?]$/.test(tail)) tail += '.'
    found.push(tail)
  }
  return found
}

function clipWords(text, maxWords = 32) {
  const words = clean(text).split(' ').filter(Boolean)
  if (!words.length) return ''
  const clipped = words.length > maxWords ? words.slice(0, maxWords).join(' ') : words.join(' ')
  return /[.!?]$/.test(clipped) ? clipped : `${clipped}.`
}

function tokens(text) {
  return (clean(text).toLowerCase().match(/[a-z][a-z']{3,}/g) || []).filter((word) => !STOP.has(word))
}

function substantialSentence(text) {
  for (const sentence of splitSentences(text)) {
    const words = clean(sentence).split(' ').filter(Boolean)
    if (words.length >= 6 && tokens(sentence).length >= 3) return sentence
  }
  return ''
}

function dedupeSentences(items) {
  const kept = []
  const seen = new Set()
  for (const item of items) {
    const key = clean(item).replace(/[.!?]+$/g, '').toLowerCase()
    if (!key || seen.has(key)) continue
    seen.add(key)
    kept.push(item)
  }
  return kept
}

function clauseParts(text) {
  return String(text || '')
    .split(/\s*;\s*/)
    .map((part) => part.trim())
    .filter(Boolean)
}

function completeBrief(parts) {
  const found = dedupeSentences(
    parts.flatMap((part) =>
      clauseParts(part).flatMap((clause) => splitSentences(clause).map((sentence) => clipWords(sentence, 32))),
    ),
  )
  return found.slice(0, 5).join(' ')
}

function lowerLeading(text) {
  const cleaned = clean(text).replace(/[.!?]+$/g, '')
  const match = cleaned.match(/^([A-Z][a-z]+)([\s\S]*)$/)
  if (!match) return cleaned
  return `${match[1].toLowerCase()}${match[2]}`
}

function quote(post, limit = 220) {
  const text = clean(post?.text || '')
  if (!text) return ''
  if (text.length <= limit) return text
  const window = text.slice(0, limit + 1)
  const cuts = [window.lastIndexOf('. '), window.lastIndexOf('! '), window.lastIndexOf('? ')]
  const cut = Math.max(...cuts)
  if (cut >= limit * 0.45) return window.slice(0, cut + 1).trim()
  const shortened = text.slice(0, limit).replace(/\s+\S*$/, '').replace(/[.,;:]+$/, '')
  return `${shortened}…`
}

function threeParagraphs(parts) {
  const cleaned = []
  const seen = new Set()
  for (const part of parts) {
    const text = clean(part)
    const key = text.replace(/[.!?]+$/g, '').toLowerCase()
    if (!text || text.length < 40 || seen.has(key)) continue
    seen.add(key)
    cleaned.push(text)
  }
  return cleaned.slice(0, 3).join('\n\n')
}

function perspectiveCopy(face, rivals) {
  const posts = [...(face.representative_posts || [])].sort((a, b) => (b.likes || 0) - (a.likes || 0))
  const postLines = []
  for (const post of posts) {
    const sentence = substantialSentence(post.text || '')
    if (!sentence) continue
    postLines.push(clipWords(sentence, 28))
    if (postLines.length >= 3) break
  }
  const claimParts = [face.summary, ...(face.arguments || [])]
  const brief = completeBrief(claimParts) || postLines[0] || face.title
  const claimBits = dedupeSentences(claimParts.flatMap((part) => clauseParts(part).flatMap((clause) => splitSentences(clause))))
  const first = claimBits.length
    ? `${face.title} argues that ${lowerLeading(claimBits[0])}. ${claimBits.slice(1, 4).join(' ')}`.replace(/\s+/g, ' ').trim()
    : brief
  const spoken = posts
    .slice(0, 3)
    .map((post) => {
      const line = quote(post)
      if (!line) return ''
      const author = clean(post.author || '')
      return `${author ? `@${author} ` : ''}writes, “${line}”`
    })
    .filter(Boolean)
  const second = spoken.length
    ? `The posts defend it in their own words. ${spoken.join(' ')}`
    : postLines.join(' ')
  const reasons = (face.arguments || []).map((item) => clipWords(item, 24)).filter(Boolean).join(' ')
  const third = rivals.length
    ? `Other views in this conversation are ${rivals.map((rival) => rival.title).join(', ')}. ${rivals
        .slice(0, 3)
        .map((rival) => `${rival.title} says ${clean(rival.summary).replace(/\.$/, '')}.`)
        .join(' ')}`
    : [reasons, postLines[0]].filter(Boolean).join(' ')
  return {
    brief,
    detail: threeParagraphs([first, second, third, postLines.join(' ')]),
  }
}

function planetCopy(topic, faces) {
  const viewLines = faces.map((face) => `${face.title} says ${clean(face.summary).replace(/\.$/, '')}.`)
  const faceSentences = faces.flatMap((face) => splitSentences(face.brief || face.summary || ''))
  const shared = completeBrief([`${topic.name} is the conversation these views share.`, ...viewLines])
  const brief = faces.length === 1 && faceSentences.length
    ? faces[0].brief || faceSentences.join(' ')
    : splitSentences(shared).length >= 3
      ? shared
      : completeBrief([shared, ...faceSentences])
  const defenses = faces.map((face) => {
    const claim = lowerLeading(face.summary || face.title || '')
    const extra = (face.arguments || []).slice(0, 2).map((item) => clipWords(item, 24)).join(' ')
    return `${face.title} argues that ${claim}. ${extra}`.trim()
  })
  const posts = faces.flatMap((face) => face.representative_posts || [])
  const spoken = posts
    .slice()
    .sort((a, b) => (b.likes || 0) - (a.likes || 0))
    .slice(0, 2)
    .map((post) => {
      const line = quote(post, 180)
      if (!line) return ''
      return `@${clean(post.author || 'someone')} writes, “${line}”`
    })
    .filter(Boolean)
  const split = faces.map((face) => {
    const claim = clean(face.summary).replace(/\.$/, '')
    const share = face.volume_percent == null ? '' : ` (${Number(face.volume_percent).toFixed(1).replace(/\.0$/, '')}%)`
    return `${face.title}${share} says ${claim}.`
  })
  const detail = threeParagraphs([
    defenses.join(' '),
    spoken.join(' ') || brief,
    split.join(' '),
    faceSentences.slice(0, 3).join(' '),
  ])
  return { brief, detail }
}

function stampIds(topicId, faces) {
  return faces.map((face, index) => ({
    ...face,
    id: `${topicId}${String.fromCharCode(65 + index)}`,
  }))
}

const FILLER = /that is the position in the posts about|is the claim these posts repeat|the posts gathered here are making that case|the same claim shows up again across the posts|these posts are making that case/i

function briefReady(text) {
  if (FILLER.test(text || '')) return false
  const count = splitSentences(text).length
  return count >= 3 && count <= 5
}

function detailReady(text) {
  const parts = String(text || '')
    .split(/\n\n+/)
    .map((part) => part.trim())
    .filter(Boolean)
  return parts.length === 3 && parts.every((part) => part.length >= 40)
}

export function presentTopic(topic) {
  let faces = (topic.perspectives || []).map((face) => ({
    ...face,
    representative_posts: [...(face.representative_posts || [])],
    arguments: face.arguments ? [...face.arguments] : undefined,
  }))
  if (faces.length > 6) faces = faces.slice(0, 6)
  faces = stampIds(topic.id, faces)

  const copied = faces.map((face) => {
    const rivals = faces.filter((other) => other.id !== face.id)
    if (briefReady(face.brief) && detailReady(face.detail)) return face
    return { ...face, ...perspectiveCopy(face, rivals) }
  })

  const unchanged = (topic.perspectives || []).length === copied.length
    && (topic.perspectives || []).every((face, index) => face.title === copied[index].title)
  const planet = planetCopy(topic, copied)
  const summary = splitSentences(unchanged && topic.brief ? topic.brief : planet.brief)[0]
    || topic.summary
    || topic.name
  return {
    ...topic,
    summary,
    brief: unchanged && briefReady(topic.brief) ? topic.brief : planet.brief,
    detail: unchanged && detailReady(topic.detail) ? topic.detail : planet.detail,
    perspectives: copied,
  }
}

function presentDigest(topics, previous) {
  const planets = [...topics]
    .sort((a, b) => (b.total_volume_percent || 0) - (a.total_volume_percent || 0))
    .map((topic) => {
      const faces = topic.perspectives || []
      const oneView = faces.length <= 1
      const argumentsList = []
      for (const face of faces) {
        const lines = (face.arguments || []).map((item) => clean(item)).filter(Boolean)
        if (faces.length > 1) {
          if (lines.length) lines.forEach((line) => argumentsList.push(`${face.title}: ${line}`))
          else if (face.summary) argumentsList.push(`${face.title}: ${clean(face.summary)}`)
        } else {
          argumentsList.push(...lines)
        }
      }
      const disagreement = oneView
        ? null
        : faces
            .map((face) => `${face.title} says ${clean(face.summary).replace(/\.$/, '')}.`)
            .join(' ')
      const opposingNote = oneView
        ? topic.opposing_note || 'No clear opposing view found in this sample'
        : null
      return {
        name: topic.name,
        category: topic.category,
        percent: topic.total_volume_percent,
        arguments: argumentsList.slice(0, 6),
        oneView,
        opposingNote,
        disagreement,
      }
    })
  const lead = planets.slice(0, 3).map((planet) => planet.name).filter(Boolean).join(', ')
  return {
    subject: previous?.subject && planets.length === (previous.planets || []).length
      ? previous.subject
      : lead
        ? `This week: ${lead}`
        : 'This week',
    planets,
  }
}

function allocateCounts(total, weights) {
  const count = weights.length
  const target = Math.max(0, Math.round(Number(total) || 0))
  if (!count || target <= 0) return weights.map(() => 0)
  const numeric = weights.map((value) => Math.max(0, Number(value) || 0))
  const sum = numeric.reduce((acc, value) => acc + value, 0)
  if (sum <= 0) {
    const even = Math.floor(target / count)
    const parts = Array.from({ length: count }, () => even)
    let leftover = target - even * count
    for (let index = 0; leftover > 0; index += 1, leftover -= 1) parts[index % count] += 1
    return parts
  }
  const raw = numeric.map((value) => (value / sum) * target)
  const floors = raw.map((value) => Math.floor(value + 1e-9))
  let remainder = target - floors.reduce((acc, value) => acc + value, 0)
  const order = raw
    .map((value, index) => ({ index, frac: value - floors[index] }))
    .sort((a, b) => b.frac - a.frac || a.index - b.index)
  const parts = floors.slice()
  for (let index = 0; index < remainder; index += 1) {
    parts[order[index % count].index] += 1
  }
  return parts
}

function withPostCounts(topic, totalPosts) {
  const explicit = Number(topic.post_count)
  const estimated = Math.round(((Number(totalPosts) || 0) * (Number(topic.total_volume_percent) || 0)) / 100)
  const planetCount = explicit > 0 ? Math.round(explicit) : Math.max(0, estimated)
  const faces = topic.perspectives || []
  const explicitFaces = faces.length > 0 && faces.every((face) => Number(face.post_count) > 0)
  const faceSum = explicitFaces
    ? faces.reduce((sum, face) => sum + Math.round(Number(face.post_count)), 0)
    : 0
  if (explicitFaces && faceSum === planetCount) {
    return {
      ...topic,
      post_count: planetCount,
      perspectives: faces.map((face) => ({ ...face, post_count: Math.round(Number(face.post_count)) })),
    }
  }
  const counts = allocateCounts(
    planetCount,
    faces.map((face) => Number(face.volume_percent) || Number(face.post_count) || 0),
  )
  return {
    ...topic,
    post_count: planetCount,
    perspectives: faces.map((face, index) => ({ ...face, post_count: counts[index] })),
  }
}

export function presentSnapshot(data) {
  const topics = (data?.topics || []).map((topic) => withPostCounts(presentTopic(topic), data?.total_posts))
  const rawSections = data?.sections ?? null
  const sections = rawSections
    ? Object.fromEntries(
        Object.entries(rawSections).map(([section, sectionTopics]) => [
          section,
          sectionTopics.map((topic) => withPostCounts(presentTopic(topic), data?.total_posts)),
        ]),
      )
    : null
  return {
    ...data,
    topics,
    sections,
    digest: presentDigest(topics, data?.digest),
  }
}
