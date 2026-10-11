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
  assert.ok(sentences.length >= 1 && sentences.length <= 5, `${label} brief has ${sentences.length} sentences`)
  const parts = paragraphs(subject.detail)
  assert.equal(parts.length, 3, `${label} detail has ${parts.length} paragraphs`)
  assert.ok(parts.every((part) => part.length >= 40), `${label} detail paragraph is too short`)
}

const payload = JSON.parse(await readFile(new URL('../public/data.json', import.meta.url), 'utf8'))
const presented = presentSnapshot(payload)

const FILLER = /that is the position in the posts about|is the claim these posts repeat|the posts gathered here are making that case|these posts are making that case/i

function assertHonest(subject, label) {
  const blob = `${subject.title || ''} ${subject.name || ''} ${subject.brief || ''} ${subject.detail || ''}`
  assert.equal(FILLER.test(blob), false, `${label} uses stock filler`)
  const words = String(subject.title || subject.name || '').toLowerCase().split(/\s+/).filter(Boolean)
  for (let index = 1; index < words.length; index += 1) {
    assert.notEqual(words[index], words[index - 1], `${label} repeats a word in the title`)
  }
}

assert.equal(presented.topics.length, payload.topics.length)
for (const topic of presented.topics) {
  const source = payload.topics.find((item) => item.id === topic.id)
  const sourceFaces = source?.perspectives?.length || 0
  assert.ok(topic.perspectives.length >= 1 && topic.perspectives.length <= 6, `${topic.name} has ${topic.perspectives.length} perspectives`)
  if (sourceFaces >= 1) {
    assert.equal(topic.perspectives.length, Math.min(sourceFaces, 6), `${topic.name} changed the published perspectives`)
  }
  const titles = new Set(topic.perspectives.map((face) => face.title.toLowerCase()))
  assert.equal(titles.size, topic.perspectives.length, `${topic.name} perspectives are not distinct`)
  const share = topic.perspectives.reduce((sum, face) => sum + face.volume_percent, 0)
  assert.ok(Math.abs(share - 100) < 0.2, `${topic.name} perspectives sum to ${share}`)
  if (topic.perspectives.length > 1) {
    assert.ok(!topic.perspectives.every((face) => face.volume_percent >= 99), `${topic.name} bars are all 100%`)
  }
  assertHonest(topic, topic.name)
  assertReading(topic, topic.name)
  assert.ok(topic.post_count > 0, `${topic.name} is missing a post count`)
  const counted = topic.perspectives.reduce((sum, face) => sum + face.post_count, 0)
  assert.equal(counted, topic.post_count, `${topic.name} perspective counts sum to ${counted}`)
  for (const face of topic.perspectives) {
    assertHonest(face, `${topic.name} / ${face.title}`)
    assertReading(face, `${topic.name} / ${face.title}`)
    assert.ok((face.representative_posts || []).length >= 2, `${face.title} is a one-post perspective`)
    assert.ok(face.post_count > 0, `${face.title} is missing a post count`)
    assert.equal(/\?$/.test(face.title), false, `${face.title} is a question fragment`)
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
assert.equal(single.perspectives.length, 1)
assert.equal(single.perspectives[0].title, 'One Claim')
assert.equal(single.perspectives[0].volume_percent, 100)
assertReading(single, 'sample')
assert.equal(FILLER.test(`${single.brief} ${single.detail}`), false)
assert.equal(/hope many|at what fucking|pike pike/i.test(single.perspectives[0].title), false)

const uniform = presentTopic({
  id: 4,
  name: 'Artists Reject AI',
  category: 'Technology',
  total_volume_percent: 15,
  summary: 'AI harms artists and creatives',
  perspectives: [
    {
      id: '4A',
      title: 'Artists Reject AI',
      summary: 'AI harms artists and creatives',
      volume_percent: 100,
      arguments: [
        'Artists push back against generative AI.',
        'AI-generated content is detrimental to small artists.',
      ],
      representative_posts: [
        { author: 'ada', text: 'Artists reject generative systems because they copy living painters without consent.', likes: 4 },
        { author: 'bea', text: 'Artists reject generative systems because they copy working painters without consent.', likes: 2 },
        { author: 'cy', text: 'Artists reject generative systems because they copy studio painters without consent.', likes: 1 },
        { author: 'dee', text: 'I hope many people will fill out this survey about the weather tomorrow.', likes: 0 },
      ],
    },
  ],
})
assert.equal(uniform.perspectives.length, 1)
assert.equal(uniform.perspectives[0].title, 'Artists Reject AI')
assert.equal(uniform.perspectives[0].volume_percent, 100)
assert.equal(FILLER.test(`${uniform.brief} ${uniform.perspectives[0].brief}`), false)
assert.equal(/hope many people will fill/i.test(uniform.perspectives[0].title), false)
assertReading(uniform, 'uniform planet')
assertReading(uniform.perspectives[0], 'uniform face')

const counted = presentSnapshot({
  total_posts: 2805,
  topics: [
    {
      id: 8,
      name: 'Counted Planet',
      category: 'Politics',
      total_volume_percent: 15,
      post_count: 37,
      summary: 'The posts share one claim.',
      perspectives: [
        {
          id: '8A',
          title: 'Counted View',
          summary: 'The posts share one claim about the counted planet.',
          volume_percent: 100,
          post_count: 37,
          arguments: ['The first reason is concrete and long enough.', 'The second reason is also a real claim.'],
          representative_posts: [
            { author: 'ada', text: 'The counted planet is about one claim that the posts actually share.', likes: 4 },
            { author: 'bea', text: 'The counted planet is about one claim that these other posts share too.', likes: 1 },
          ],
        },
      ],
    },
  ],
})
assert.equal(counted.topics[0].post_count, 37)
assert.equal(counted.topics[0].perspectives[0].post_count, 37)

const oneViewDigest = presentSnapshot({
  total_posts: 500,
  topics: [
    {
      id: 99,
      name: 'Gaza Genocide',
      category: 'World',
      total_volume_percent: 12,
      opposing_note: 'No clear opposing view found in this sample',
      summary: 'Zionism is a racist ideology',
      perspectives: [
        {
          id: '99A',
          title: 'Gaza Genocide',
          summary: 'Zionism is a racist ideology',
          volume_percent: 100,
          arguments: [
            'The first reason is concrete and long enough for readers.',
            'The second reason is also a real claim in the posts.',
          ],
          representative_posts: [
            { author: 'ada', text: 'Zionism is a racist ideology and the posts keep saying so.', likes: 4 },
            { author: 'bea', text: 'Zionism is a racist ideology repeated across these posts.', likes: 2 },
          ],
        },
      ],
    },
  ],
})
const digestPlanet = oneViewDigest.digest.planets[0]
assert.equal(digestPlanet.oneView, true)
assert.equal(digestPlanet.disagreement, null)
assert.match(digestPlanet.opposingNote, /opposing view/i)

console.log('presented planets keep real perspectives and skip stock filler')
