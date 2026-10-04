import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { presentSnapshot, presentTopic, splitSentences } from '../src/lib/present.js'

function paragraphs(text) {
  return String(text || '')
    .split(/\n\n+/)
    .map((part) => part.trim())
    .filter(Boolean)
}

function assertReading(subject, label) {
  const sentences = splitSentences(subject.brief)
  assert.ok(sentences.length >= 3 && sentences.length <= 5, `${label} brief has ${sentences.length} sentences`)
  const parts = paragraphs(subject.detail)
  assert.equal(parts.length, 3, `${label} detail has ${parts.length} paragraphs`)
  assert.ok(parts.every((part) => part.length >= 40), `${label} detail paragraph is too short`)
}

const payload = JSON.parse(await readFile(new URL('../public/data.json', import.meta.url), 'utf8'))
const presented = presentSnapshot(payload)

assert.equal(presented.topics.length, payload.topics.length)
for (const topic of presented.topics) {
  assert.ok(topic.perspectives.length >= 2 && topic.perspectives.length <= 6, `${topic.name} has ${topic.perspectives.length} perspectives`)
  const titles = new Set(topic.perspectives.map((face) => face.title.toLowerCase()))
  assert.equal(titles.size, topic.perspectives.length, `${topic.name} perspectives are not distinct`)
  const share = topic.perspectives.reduce((sum, face) => sum + face.volume_percent, 0)
  assert.ok(Math.abs(share - 100) < 0.2, `${topic.name} perspectives sum to ${share}`)
  assert.ok(topic.perspectives.length > 1, `${topic.name} is still a single 100% bar`)
  assert.ok(!topic.perspectives.every((face) => face.volume_percent >= 99), `${topic.name} bars are all 100%`)
  assertReading(topic, topic.name)
  assert.ok(topic.post_count > 0, `${topic.name} is missing a post count`)
  const counted = topic.perspectives.reduce((sum, face) => sum + face.post_count, 0)
  assert.equal(counted, topic.post_count, `${topic.name} perspective counts sum to ${counted}`)
  for (const face of topic.perspectives) {
    assertReading(face, `${topic.name} / ${face.title}`)
    assert.ok(face.representative_posts?.length, `${face.title} has no posts`)
    assert.ok(face.post_count > 0, `${face.title} is missing a post count`)
  }
}
const postCounts = presented.topics.map((topic) => topic.post_count)
assert.ok(new Set(postCounts).size > 1, 'every planet was given the same post count')
assert.ok(postCounts.every((count) => count !== payload.total_posts), 'a planet is showing the week total')

const again = presentTopic(presented.topics[0])
assert.equal(again.perspectives.length, presented.topics[0].perspectives.length)
assert.deepEqual(again.perspectives.map((face) => face.title), presented.topics[0].perspectives.map((face) => face.title))

const single = presentTopic({
  id: 9,
  name: 'Sample Planet',
  category: 'Politics',
  total_volume_percent: 10,
  summary: '',
  perspectives: [
    {
      id: '9A',
      title: 'One Claim',
      summary: 'The posts share one claim.',
      volume_percent: 100,
      arguments: ['The first reason is concrete.', 'The second reason disagrees with the easy version.'],
      representative_posts: [
        { author: 'ada', text: 'Voting rights need a public defense before November arrives.', likes: 4 },
        { author: 'bea', text: 'Courts should stay out of the ballot rules this cycle.', likes: 3 },
        { author: 'cy', text: 'Voting rights need a public defense before November arrives.', likes: 2 },
        { author: 'dee', text: 'Courts should stay out of the ballot rules this cycle entirely.', likes: 1 },
      ],
    },
  ],
})
assert.ok(single.perspectives.length >= 2 && single.perspectives.length <= 6)
assertReading(single, 'sample')

console.log('presented planets have 2-6 perspectives and both summary lengths')
