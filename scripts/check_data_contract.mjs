import { readFile } from 'node:fs/promises'

const payload = JSON.parse(await readFile(new URL('../dist/data.json', import.meta.url), 'utf8'))

function fail(message) {
  console.error(message)
  process.exit(1)
}

const SYSTEM_SIZE = 10
const categories = new Set([
  'World',
  'Politics',
  'Business',
  'Technology',
  'Sports',
  'Culture',
  'Health',
  'Environment',
  'Education',
  'Other',
  'Geopolitics',
  'AI',
  'Economy',
  'Media',
  'Entertainment',
  'Religion',
])
const demoCategories = [
  'Politics',
  'Sports',
  'Technology',
  'Economy',
  'Environment',
  'Health',
  'Education',
  'Media',
  'Entertainment',
  'Religion',
]

const minimumTopics = payload.mode === 'live' ? 1 : SYSTEM_SIZE
if (!Array.isArray(payload.topics) || payload.topics.length < minimumTopics) {
  fail(`Expected at least ${minimumTopics} topics, found ${payload.topics?.length}`)
}

const categoryCounts = Object.fromEntries([...categories].map((name) => [name, 0]))
let topicVolume = 0
for (const topic of payload.topics) {
  if (!categories.has(topic.category)) fail(`Bad category on topic ${topic.id}`)
  categoryCounts[topic.category] += 1
  const faceCount = topic.perspectives?.length
  if (!Array.isArray(topic.perspectives) || faceCount < 2 || faceCount > 6) {
    fail(`Topic ${topic.id} should have 2-6 faces, found ${faceCount}`)
  }
  topicVolume += Number(topic.total_volume_percent)
  let faceVolume = 0
  for (const face of topic.perspectives) {
    if (!face.title || !face.summary) fail(`Face ${face.id} missing title or summary`)
    if (payload.mode === 'demo') {
      if (!Array.isArray(face.arguments) || face.arguments.length < 2) {
        fail(`Demo face ${face.id} missing core arguments`)
      }
    }
    if (!face.representative_posts?.length) fail(`Face ${face.id} missing posts`)
    for (const post of face.representative_posts) {
      if (typeof post.likes !== 'number') fail(`Face ${face.id} post missing likes`)
    }
    faceVolume += Number(face.volume_percent)
  }
  if (Math.abs(faceVolume - 100) > 0.15) fail(`Topic ${topic.id} faces sum to ${faceVolume}`)
}

if (Math.abs(topicVolume - 100) > 0.15) fail(`Topics sum to ${topicVolume}`)
if (payload.mode !== 'demo' && payload.mode !== 'live') fail('mode missing')
if (payload.mode === 'demo') {
  const short = demoCategories.filter((name) => categoryCounts[name] < SYSTEM_SIZE)
  if (short.length) fail(`Demo catalog missing a full solar system for: ${short.join(', ')}`)
}
console.log('dist/data.json matches the observatory contract')
