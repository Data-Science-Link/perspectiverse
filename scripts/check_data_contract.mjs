import { readFile } from 'node:fs/promises'

const payload = JSON.parse(await readFile(new URL('../dist/data.json', import.meta.url), 'utf8'))

function fail(message) {
  console.error(message)
  process.exit(1)
}

if (!Array.isArray(payload.topics) || payload.topics.length !== 10) {
  fail(`Expected 10 topics, found ${payload.topics?.length}`)
}

const categories = new Set([
  'Politics',
  'Sports',
  'Technology',
  'Economy',
  'Environment',
  'Health',
  'Education',
  'Media',
])

let topicVolume = 0
for (const topic of payload.topics) {
  if (!categories.has(topic.category)) fail(`Bad category on topic ${topic.id}`)
  const faceCount = topic.perspectives?.length
  if (!Array.isArray(topic.perspectives) || faceCount < 2 || faceCount > 6) {
    fail(`Topic ${topic.id} should have 2-6 faces, found ${faceCount}`)
  }
  topicVolume += Number(topic.total_volume_percent)
  let faceVolume = 0
  for (const face of topic.perspectives) {
    if (!face.title || !face.summary) fail(`Face ${face.id} missing title or summary`)
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
console.log('dist/data.json matches the observatory contract')
