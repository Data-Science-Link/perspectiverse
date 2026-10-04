import { allocatePercents } from './layout.js'

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

export function splitSentences(text) {
  const cleaned = clean(text)
  if (!cleaned) return []
  const parts = cleaned.split(/(?<=[.!?])\s+/)
  const found = []
  for (const part of parts) {
    let piece = part.trim()
    if (!piece) continue
    if (!/[.!?]$/.test(piece)) piece += '.'
    found.push(piece)
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

function tokenSet(text) {
  return new Set(tokens(text))
}

function jaccard(left, right) {
  let inter = 0
  for (const token of left) {
    if (right.has(token)) inter += 1
  }
  const union = left.size + right.size - inter
  return union ? inter / union : 1
}

function unionSet(sets) {
  const bag = new Set()
  for (const set of sets) {
    for (const token of set) bag.add(token)
  }
  return bag
}

function titleCase(words) {
  const small = new Set(['of', 'the', 'a', 'an', 'and', 'or', 'to', 'in', 'on', 'for'])
  return words
    .filter(Boolean)
    .map((word, index) => {
      const lower = word.toLowerCase()
      if (index > 0 && small.has(lower)) return lower
      return lower.charAt(0).toUpperCase() + lower.slice(1)
    })
    .join(' ')
}

function firstSentence(text) {
  return splitSentences(text)[0] || clipWords(text, 24)
}

function clusterIndexes(sets, k) {
  const count = sets.length
  const size = Math.min(k, count)
  if (size < 1) return []
  const seeds = [0]
  while (seeds.length < size) {
    let best = -1
    let bestDistance = -1
    for (let index = 0; index < count; index += 1) {
      if (seeds.includes(index)) continue
      let nearest = 1
      for (const seed of seeds) nearest = Math.min(nearest, jaccard(sets[index], sets[seed]))
      const distance = 1 - nearest
      if (distance > bestDistance || (distance === bestDistance && (best < 0 || index < best))) {
        bestDistance = distance
        best = index
      }
    }
    if (best < 0) break
    seeds.push(best)
  }
  let groups = seeds.map((index) => [index])
  for (let iter = 0; iter < 8; iter += 1) {
    const centroids = groups.map((group) => unionSet(group.map((index) => sets[index])))
    const next = centroids.map(() => [])
    for (let index = 0; index < count; index += 1) {
      let winner = 0
      let score = -1
      for (let group = 0; group < centroids.length; group += 1) {
        const similarity = jaccard(sets[index], centroids[group])
        if (similarity > score || (similarity === score && group < winner)) {
          score = similarity
          winner = group
        }
      }
      next[winner].push(index)
    }
    for (let group = 0; group < next.length; group += 1) {
      if (next[group].length) continue
      let donor = 0
      for (let other = 1; other < next.length; other += 1) {
        if (next[other].length > next[donor].length) donor = other
      }
      if (next[donor].length < 2) break
      next[group].push(next[donor].pop())
    }
    const same = next.every((group, index) => group.join(',') === groups[index].join(','))
    groups = next
    if (same) break
  }
  return groups.filter((group) => group.length)
}

function chooseGroups(posts) {
  const count = posts.length
  if (count < 2) return [posts.map((_, index) => index)]
  const sets = posts.map((post) => tokenSet(post.text || post.clean_text || ''))
  const upper = Math.min(6, count)
  const base = unionSet(sets)
  let previous = 0
  let best = null
  for (let k = 2; k <= upper; k += 1) {
    const groups = clusterIndexes(sets, k)
    if (groups.length < 2) continue
    const sizes = groups.map((group) => group.length)
    const minSize = Math.min(...sizes)
    const share = minSize / count
    const centroids = groups.map((group) => unionSet(group.map((index) => sets[index])))
    let far = true
    for (let left = 0; left < centroids.length; left += 1) {
      for (let right = left + 1; right < centroids.length; right += 1) {
        if (jaccard(centroids[left], centroids[right]) >= 0.55) far = false
      }
    }
    const separated = centroids.reduce((sum, centroid) => sum + (1 - jaccard(centroid, base)), 0) / centroids.length
    const gain = separated - previous
    const balanced = minSize >= 2 && share >= 0.18
    if (balanced && far && (best == null || gain >= 0.08)) {
      best = groups
      previous = separated
      continue
    }
    if (best) break
    if (k === 2 && groups.length >= 2 && far && separated >= 0.05) best = groups
  }
  if (best) return best
  const pair = clusterIndexes(sets, 2)
  if (pair.length >= 2) return pair
  const half = Math.max(1, Math.ceil(count / 2))
  return [posts.map((_, index) => index).slice(0, half), posts.map((_, index) => index).slice(half)]
}

function sharedTokens(posts) {
  const counts = new Map()
  for (const post of posts) {
    for (const token of new Set(tokens(post.text || ''))) {
      counts.set(token, (counts.get(token) || 0) + 1)
    }
  }
  const floor = Math.max(2, Math.ceil(posts.length * 0.5))
  const shared = new Set()
  for (const [token, count] of counts) {
    if (count >= floor) shared.add(token)
  }
  return shared
}

const LEAD_IN = /^(i mean[, ]+|yeah[, ]+|yes[, ]+|so |and |but |well |obviously |absolutely |there is |there are |there's |this is |it is |it's |story after story right now about |i |we |they |he |she )/i

function substantialSentence(text) {
  for (const sentence of splitSentences(text)) {
    const words = clean(sentence).split(' ').filter(Boolean)
    if (words.length >= 6 && tokens(sentence).length >= 3) return sentence
  }
  return ''
}

function properPhrase(sentence) {
  const words = clean(sentence).split(' ').filter(Boolean)
  let best = []
  let current = []
  const keep = () => {
    const trimmed = [...current]
    while (trimmed.length && /^(of|the|a|and|for)$/i.test(trimmed[trimmed.length - 1])) trimmed.pop()
    if (trimmed.length > best.length) best = trimmed
    current = []
  }
  for (const word of words) {
    const bare = word.replace(/[^A-Za-z0-9']/g, '')
    const bridge = /^(of|the|a|and|for)$/i.test(bare)
    const named = bare.length > 1 && bare[0] === bare[0].toUpperCase() && bare !== bare.toUpperCase()
    if (named) current.push(bare)
    else if (current.length && bridge && current.length < 4) current.push(bare.toLowerCase())
    else keep()
  }
  keep()
  if (best.length < 2) return ''
  return best.slice(0, 4).join(' ')
}

function claimTitle(sentence) {
  const named = properPhrase(sentence)
  if (named && named.split(' ').length >= 2) return named
  let text = clean(sentence).replace(/[“”"]/g, '')
  for (let pass = 0; pass < 3; pass += 1) {
    const next = text.replace(LEAD_IN, '')
    if (next === text) break
    text = next.trim()
  }
  const clause = text.split(/[,:;]/)[0].replace(/[.!?]+$/g, '')
  const words = clause.split(' ').filter(Boolean).slice(0, 5)
  while (words.length > 3 && STOP.has(words[words.length - 1].toLowerCase().replace(/[^a-z']/g, ''))) {
    words.pop()
  }
  return titleCase(words)
}

function titleFor(groupPosts, allPosts, used) {
  const ranked = [...groupPosts].sort((a, b) => (b.likes || 0) - (a.likes || 0))
  let sentence = ''
  for (const post of ranked) {
    sentence = substantialSentence(post.text || '')
    if (sentence) break
  }
  if (!sentence) sentence = firstSentence(ranked[0]?.text || '')
  let title = claimTitle(sentence)
  if (!title || title.split(' ').length < 2) {
    const shared = sharedTokens(allPosts)
    const words = tokens(sentence).filter((word) => !shared.has(word)).slice(0, 3)
    title = titleCase(words.length >= 2 ? words : tokens(sentence).slice(0, 3))
  }
  if (!title) title = 'Other View'
  const base = title
  let guard = 2
  while (used.has(title.toLowerCase()) && guard < 6) {
    title = `${base} ${guard}`
    guard += 1
  }
  used.add(title.toLowerCase())
  return title
}

function summaryFor(groupPosts, fallback) {
  const ranked = [...groupPosts].sort((a, b) => (b.likes || 0) - (a.likes || 0))
  for (const post of ranked) {
    const sentence = substantialSentence(post.text || '')
    if (sentence) return clipWords(sentence, 28)
  }
  return clipWords(fallback || firstSentence(ranked[0]?.text || '') || 'These posts share a claim.', 28)
}

function diversifyFace(face) {
  const posts = [...(face?.representative_posts || [])]
  if (posts.length < 2) return null
  const groups = chooseGroups(posts)
  if (groups.length < 2) return null
  const used = new Set()
  const allPosts = posts
  const made = groups
    .map((indexes) => indexes.map((index) => posts[index]))
    .sort((a, b) => b.length - a.length)
    .slice(0, 6)
    .map((groupPosts, groupIndex) => {
      const title = groupIndex === 0 && face?.title ? face.title : titleFor(groupPosts, allPosts, used)
      if (groupIndex === 0 && face?.title) used.add(String(face.title).toLowerCase())
      const summary = groupIndex === 0 && face?.summary
        ? clipWords(face.summary, 28)
        : summaryFor(groupPosts, face?.summary)
      const groupTokens = unionSet(groupPosts.map((post) => tokenSet(post.text || '')))
      const argumentsKept = (face?.arguments || []).filter((argument) => {
        const argumentTokens = tokenSet(argument)
        let overlap = 0
        for (const token of argumentTokens) if (groupTokens.has(token)) overlap += 1
        return overlap >= 1
      })
      const perspective = {
        id: '',
        title,
        summary: summary || title,
        representative_posts: [...groupPosts].sort((a, b) => (b.likes || 0) - (a.likes || 0)),
      }
      if (argumentsKept.length >= 2) perspective.arguments = argumentsKept.slice(0, 6)
      return perspective
    })
  return made.length >= 2 ? made : null
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

function completeBrief(parts, title) {
  const found = dedupeSentences(parts.flatMap((part) => splitSentences(part).map((sentence) => clipWords(sentence, 32))))
  const fillers = title
    ? [
        `That is the position in the posts about ${title}.`,
        `${title} is the claim these posts repeat.`,
      ]
    : ['The posts gathered here are making that case.', 'The same claim shows up again across the posts.']
  for (const filler of fillers) {
    if (found.length >= 3) break
    if (!found.some((item) => item.toLowerCase() === filler.toLowerCase())) found.push(filler)
  }
  return found.slice(0, 5).join(' ')
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

function threeParagraphs(parts, fallback) {
  const cleaned = parts.map((part) => clean(part)).filter(Boolean)
  while (cleaned.length < 3) cleaned.push(fallback || 'These posts are making that case.')
  return cleaned.slice(0, 3).join('\n\n')
}

function perspectiveCopy(face, rivals) {
  const posts = face.representative_posts || []
  const postLines = posts.slice(0, 4).map((post) => firstSentence(post.text || '')).filter(Boolean)
  const brief = completeBrief(
    [face.summary, ...(face.arguments || []), ...postLines],
    face.title,
  )
  const claimBits = dedupeSentences([face.summary, ...(face.arguments || [])].flatMap((part) => splitSentences(part)))
  const first = claimBits.length
    ? `${face.title} argues that ${claimBits[0].replace(/^[A-Z]/, (letter) => letter.toLowerCase())} ${claimBits.slice(1, 4).join(' ')}`.replace(/\s+/g, ' ').trim()
    : brief
  const spoken = posts
    .slice()
    .sort((a, b) => (b.likes || 0) - (a.likes || 0))
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
    : `The posts gathered under ${face.title} are the defense of that claim.`
  const third = rivals.length
    ? `Other views in this conversation are ${rivals.map((rival) => rival.title).join(', ')}. ${rivals
        .slice(0, 3)
        .map((rival) => `${rival.title} says ${clean(rival.summary).replace(/\.$/, '')}.`)
        .join(' ')}`
    : `Inside ${face.title}, the posts are arguing one position rather than a stack of unrelated claims.`
  return {
    brief,
    detail: threeParagraphs([first, second, third], brief),
  }
}

function planetCopy(topic, faces) {
  const viewLines = faces.map((face) => `${face.title} says ${clean(face.summary).replace(/\.$/, '')}.`)
  const brief = completeBrief(
    [`${topic.name} is the conversation these views share.`, ...viewLines],
    topic.name,
  )
  const defenses = faces.map((face) => {
    const claim = clean(face.summary).replace(/\.$/, '')
    const extra = (face.arguments || []).slice(0, 2).map((item) => clipWords(item, 24)).join(' ')
    return `${face.title} argues that ${claim.charAt(0).toLowerCase()}${claim.slice(1)}. ${extra}`.trim()
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
  const detail = threeParagraphs(
    [defenses.join(' '), spoken.join(' ') || brief, split.join(' ')],
    brief,
  )
  return { brief, detail }
}

function stampIds(topicId, faces) {
  return faces.map((face, index) => ({
    ...face,
    id: `${topicId}${String.fromCharCode(65 + index)}`,
  }))
}

function withVolumes(faces) {
  const weights = faces.map((face) => (face.representative_posts || []).length || face.volume_percent || 1)
  const shares = allocatePercents(weights)
  return faces.map((face, index) => ({ ...face, volume_percent: shares[index] }))
}

function briefReady(text) {
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
  let revolume = false
  if (faces.length < 2 || faces.length > 6) {
    const source = faces.length === 1 ? faces[0] : {
      summary: topic.summary,
      title: topic.name,
      arguments: [],
      representative_posts: faces.flatMap((face) => face.representative_posts || []),
    }
    const split = diversifyFace(source)
    if (split && split.length >= 2) {
      faces = split
      revolume = true
    }
  }
  if (faces.length > 6) faces = faces.slice(0, 6)
  if (revolume) faces = withVolumes(faces)
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
      const disagreement = faces
        .map((face) => `${face.title} says ${clean(face.summary).replace(/\.$/, '')}.`)
        .join(' ')
      return {
        name: topic.name,
        category: topic.category,
        percent: topic.total_volume_percent,
        arguments: argumentsList.slice(0, 6),
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
  return {
    ...data,
    topics,
    digest: presentDigest(topics, data?.digest),
  }
}
