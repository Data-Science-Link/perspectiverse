import { tokenize } from './tokenize.js'

export const MIN_MATCH_SCORE = 0.08

const SHORT_KEEPERS = new Set(['ai', 'us', 'uk', 'eu', 'un'])
const ENGAGE_STOP = new Set([
  'more',
  'than',
  'very',
  'also',
  'some',
  'any',
  'really',
  'even',
  'still',
  'over',
  'going',
  'gonna',
  'thing',
  'things',
])
const WHY_CUES = ['because', 'need', 'needs', 'cannot', 'without', 'unless', 'if']
const WHY_RE = /\b(why|how come|what makes|what are they|what do (people|they))\b/i
const COUNTER_RE = /\b(missing|other side|push back|disagree|debate|wrong|overblown|actually)\b/i

export function detectIntent(query) {
  const text = String(query ?? '').trim()
  if (!text) return 'claim'
  if (WHY_RE.test(text)) return 'why'
  if (COUNTER_RE.test(text)) return 'counter'
  return 'claim'
}

export function expandTokens(tokens) {
  const out = new Set()
  for (const token of tokens) {
    if (!token) continue
    out.add(token)
    if (token.endsWith('s') && token.length >= 4) out.add(token.slice(0, -1))
    if (token.endsWith('ing') && token.length > 6) out.add(token.slice(0, -3))
    if (token.endsWith('ed') && token.length > 5) out.add(token.slice(0, -2))
  }
  return [...out]
}

function shortKeepersIn(text) {
  return (String(text ?? '').toLowerCase().match(/\b[a-z]{2}\b/g) ?? [])
    .filter((token) => SHORT_KEEPERS.has(token))
}

export function queryTokens(query) {
  const base = tokenize(query).filter((token) => !ENGAGE_STOP.has(token))
  return expandTokens([...base, ...shortKeepersIn(query)])
}

export function documentFrequencies(rows) {
  const df = new Map()
  for (const row of rows) {
    const tokens = new Set([...expandTokens(tokenize(row.text)), ...shortKeepersIn(row.text)])
    for (const token of tokens) df.set(token, (df.get(token) ?? 0) + 1)
  }
  return { df, n: rows.length }
}

export function tokenWeight(token, stats) {
  const df = stats?.df?.get(token) ?? 1
  const n = stats?.n ?? 8
  const idf = Math.log((n + 1) / df)
  const rarity = SHORT_KEEPERS.has(token) || token.length >= 6 ? 1.7 : 1
  return idf * rarity
}

export function scoreText(queryToks, text, stats = null) {
  const postToks = new Set([...expandTokens(tokenize(text)), ...shortKeepersIn(text)])
  if (!queryToks.length || !postToks.size) return 0
  const matched = queryToks.filter((token) => postToks.has(token))
  if (!matched.length) return 0
  const distinctive = matched.filter((token) => token.length >= 5 || SHORT_KEEPERS.has(token))
  const union = new Set([...queryToks, ...postToks]).size
  const jaccard = matched.length / union
  const coverage = matched.length / queryToks.length
  const weighted = matched.reduce((total, token) => total + tokenWeight(token, stats), 0)
  const bonus = distinctive.length ? 0.06 : 0
  return 0.38 * coverage + 0.18 * jaccard + 0.44 * Math.min(weighted / 4, 1) + bonus
}

export function collectPosts(topics, { topicId = null, perspectiveId = null } = {}) {
  const rows = []
  for (const topic of topics ?? []) {
    if (topicId != null && topic.id !== topicId) continue
    const faces = [...(topic.perspectives ?? [])].sort((left, right) => {
      const delta = (right.volume_percent ?? 0) - (left.volume_percent ?? 0)
      if (delta !== 0) return delta
      return String(left.id).localeCompare(String(right.id))
    })
    faces.forEach((face, rank) => {
      if (perspectiveId && face.id !== perspectiveId) return
      for (const post of face.representative_posts ?? []) {
        rows.push({
          author: post.author,
          text: post.text,
          likes: post.likes ?? 0,
          topicId: topic.id,
          topicName: topic.name,
          topicVolume: topic.total_volume_percent,
          bodyName: topic.body?.name,
          faceId: face.id,
          faceTitle: face.title,
          faceSummary: face.summary,
          faceVolume: face.volume_percent,
          faceRank: rank,
        })
      }
    })
  }
  return rows
}

function groupBy(rows, key) {
  const groups = new Map()
  for (const row of rows) {
    const id = row[key]
    if (!groups.has(id)) groups.set(id, [])
    groups.get(id).push(row)
  }
  return groups
}

function sumScores(rows) {
  return rows.reduce((total, row) => total + (row.score ?? 0), 0)
}

function uniquePosts(rows, limit) {
  const seen = new Set()
  const out = []
  for (const row of rows) {
    const stamp = `${row.author}::${row.text}`
    if (seen.has(stamp)) continue
    seen.add(stamp)
    out.push(row)
    if (out.length >= limit) break
  }
  return out
}

function faceRecord(rows) {
  const head = rows[0]
  return {
    id: head.faceId,
    title: head.faceTitle,
    summary: head.faceSummary,
    volume: head.faceVolume,
    rank: head.faceRank,
    score: sumScores(rows),
    hits: rows.filter((row) => row.score >= MIN_MATCH_SCORE).length,
  }
}

function topicRecord(rows, topics) {
  const head = rows[0]
  const topic = (topics ?? []).find((item) => item.id === head.topicId)
  const topicRank = (topics ?? []).findIndex((item) => item.id === head.topicId)
  return {
    id: head.topicId,
    name: head.topicName,
    volume: head.topicVolume,
    bodyName: head.bodyName ?? topic?.body?.name,
    rank: topicRank < 0 ? 99 : topicRank,
    score: sumScores(rows),
    hits: rows.filter((row) => row.score >= MIN_MATCH_SCORE).length,
  }
}

function classifyPlanet(hits, faces) {
  if (!hits.length) return 'absent'
  const ranked = [...faces].sort((left, right) => right.score - left.score)
  const close = ranked.filter((face) => face.score >= ranked[0].score * 0.72)
  if (close.length >= 3) return 'split'
  if (ranked[0].rank === 0) return 'majority'
  return 'minority'
}

function classifySky(topicHits) {
  if (!topicHits.length) return 'absent'
  const ranked = [...topicHits].sort((left, right) => right.score - left.score)
  if (ranked[0].rank === 0) return 'majority'
  return 'minority'
}

function followups(result) {
  const items = []
  if (result.loudUnmatchedFace) {
    items.push({
      id: 'why-loud',
      label: `Why “${result.loudUnmatchedFace.title}”?`,
      query: `Why do people talking about ${result.loudUnmatchedFace.title} think that way?`,
    })
  }
  if (result.bestFace && result.scope !== 'face') {
    items.push({
      id: 'open-landed',
      label: `Open “${result.bestFace.title}”`,
      query: result.query,
      action: 'open-face',
      topicId: result.bestTopic?.id,
      faceId: result.bestFace.id,
    })
  }
  if (result.scope === 'sky' && result.bestTopic) {
    items.push({
      id: 'open-planet',
      label: `Stay on ${result.bestTopic.name}`,
      query: result.query,
      action: 'open-topic',
      topicId: result.bestTopic.id,
    })
  }
  if (result.presence !== 'absent') {
    items.push({
      id: 'missing',
      label: 'What am I missing?',
      query: 'What am I missing? Show the other side of this conversation.',
    })
  }
  if (result.presence === 'absent' && result.sun) {
    items.push({
      id: 'ask-sun',
      label: `Ask the sun: ${result.sun.name}`,
      query: result.query,
      action: 'open-topic',
      topicId: result.sun.id,
    })
  }
  return items
}

export function engage(query, topics, options = {}) {
  const text = String(query ?? '').trim()
  const tokens = queryTokens(text)
  const intent = detectIntent(text)
  const scope = options.perspectiveId ? 'face' : options.topicId != null ? 'planet' : 'sky'
  const collected = collectPosts(topics, options)
  const stats = documentFrequencies(collected)
  const rows = collected.map((row) => ({
    ...row,
    score: tokens.length ? scoreText(tokens, row.text, stats) : 0,
    why: WHY_CUES.some((cue) => String(row.text).toLowerCase().includes(cue)),
  }))
  const scored = [...rows].sort((left, right) => {
    if (intent === 'why' && left.why !== right.why) return left.why ? -1 : 1
    return right.score - left.score || right.likes - left.likes
  })
  const hits = scored.filter((row) => row.score >= MIN_MATCH_SCORE)

  const scopedFaces = scope === 'sky'
    ? [...groupBy(hits, 'faceId').values()].map(faceRecord)
    : [...groupBy(scored, 'faceId').values()].map(faceRecord)
  const hitFaces = [...groupBy(hits, 'faceId').values()].map(faceRecord)
    .sort((left, right) => right.score - left.score)
  const hitTopics = [...groupBy(hits, 'topicId').values()].map((group) => topicRecord(group, topics))
    .sort((left, right) => right.score - left.score)

  const loudFace = scope === 'sky'
    ? null
    : [...scopedFaces].sort((left, right) => left.rank - right.rank || right.volume - left.volume)[0] ?? null
  const bestFace = hitFaces[0] ?? null
  const bestTopic = hitTopics[0] ?? null
  const sun = topics?.[0]
    ? {
        id: topics[0].id,
        name: topics[0].name,
        volume: topics[0].total_volume_percent,
        bodyName: topics[0].body?.name,
      }
    : null

  const presence = scope === 'sky'
    ? classifySky(hitTopics)
    : classifyPlanet(hits, hitFaces.length ? hitFaces : scopedFaces)

  const loudUnmatchedFace = loudFace && bestFace && loudFace.id !== bestFace.id ? loudFace : null

  const supporting = uniquePosts(
    (intent === 'why' ? [...hits].sort((left, right) => Number(right.why) - Number(left.why) || right.score - left.score) : hits),
    3,
  )
  const counterPool = intent === 'counter' || presence === 'minority' || presence === 'split'
    ? scored.filter((row) => !bestFace || row.faceId !== bestFace.id)
    : scored.filter((row) => bestFace && row.faceId !== bestFace.id && row.faceRank === 0)
  const counter = uniquePosts(
    counterPool.sort((left, right) => {
      if (loudUnmatchedFace) {
        const leftLoud = left.faceId === loudUnmatchedFace.id ? 1 : 0
        const rightLoud = right.faceId === loudUnmatchedFace.id ? 1 : 0
        if (leftLoud !== rightLoud) return rightLoud - leftLoud
      }
      return right.likes - left.likes
    }),
    3,
  )

  const result = {
    query: text,
    intent,
    scope,
    presence,
    tokenCount: tokens.length,
    postCount: scored.length,
    hitCount: hits.length,
    bestFace,
    bestTopic,
    loudFace,
    loudUnmatchedFace,
    sun,
    faces: hitFaces,
    topics: hitTopics,
    supporting,
    counter,
    followups: [],
  }
  result.followups = followups(result)
  return result
}

export function verdictCopy(result) {
  if (!result.query) {
    return {
      title: 'Type a take',
      body: 'A claim, a brand, or a question. The snapshot answers with other people’s words.',
    }
  }
  if (!result.tokenCount) {
    return {
      title: 'Need a few real words',
      body: 'Short glue words are stripped the same way the pipeline strips them. Try a noun or a claim.',
    }
  }
  if (result.presence === 'absent' && result.scope === 'sky') {
    return {
      title: 'Not a planet this week',
      body: result.sun
        ? `Your words did not land on a representative post. The sun is “${result.sun.name}.” That absence is the point of a week-shaped sky.`
        : 'Your words did not land on a representative post in this snapshot.',
    }
  }
  if (result.presence === 'absent') {
    return {
      title: 'Not on these posts',
      body: 'The representative posts in this scope do not overlap your frame. It may live under the cap, or it may not be here.',
    }
  }
  if (result.scope === 'sky') {
    if (result.presence === 'majority' && result.bestTopic) {
      return {
        title: 'You landed on the sun',
        body: `“${result.bestTopic.name}” is the largest topic in view. That is volume, not virtue.`,
      }
    }
    if (result.bestTopic && result.sun && result.bestTopic.id !== result.sun.id) {
      return {
        title: 'Not the sun',
        body: `Your words gather on “${result.bestTopic.name}” (${result.bestTopic.volume.toFixed(1)}% of the sky). The sun is “${result.sun.name}.”`,
      }
    }
    return {
      title: 'Your words are on this sky',
      body: 'Open a planet to see whether you are gold or a quieter spike.',
    }
  }
  if (result.presence === 'majority' && result.bestFace) {
    return {
      title: 'You are the loud face',
      body: `Your take lands on “${result.bestFace.title}” (${result.bestFace.volume.toFixed(1)}% of this planet). Gold is not the same as right.`,
    }
  }
  if (result.presence === 'split') {
    return {
      title: 'The cube does not agree with itself',
      body: 'Your words scatter across several faces. There is not a single story here — including yours.',
    }
  }
  if (result.bestFace && result.loudUnmatchedFace) {
    return {
      title: 'Minority spike',
      body: `Your take lands on “${result.bestFace.title}” (${result.bestFace.volume.toFixed(1)}%). Gold is “${result.loudUnmatchedFace.title}” (${result.loudUnmatchedFace.volume.toFixed(1)}%) and barely overlaps you.`,
    }
  }
  return {
    title: 'Your words are on this sky',
    body: 'Open a planet or a face to see whether you are gold or a quieter spike.',
  }
}
