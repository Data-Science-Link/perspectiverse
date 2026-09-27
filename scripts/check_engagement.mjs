import assert from 'node:assert/strict'
import { STOPWORDS, tokenize } from '../src/lib/tokenize.js'
import { detectIntent, engage, queryTokens, scoreText, verdictCopy } from '../src/lib/engagement.js'

assert.ok(STOPWORDS.has('the'))
assert.ok(STOPWORDS.has('people'))
assert.deepEqual(tokenize('The people today just have jobs'), ['jobs'])
assert.deepEqual(tokenize('AI replaced junior writers'), ['replaced', 'junior', 'writers'])
assert.ok(queryTokens('AI created jobs').includes('ai'))
assert.ok(queryTokens('layoffs and writers').includes('layoff'))
assert.equal(detectIntent('Why do people think that?'), 'why')
assert.equal(detectIntent('What am I missing?'), 'counter')
assert.equal(detectIntent('AI will create more jobs'), 'claim')
assert.ok(scoreText(queryTokens('junior writers'), 'Junior writers were replaced') > 0.2)

const topics = [
  {
    id: 1,
    name: 'AI Futures',
    total_volume_percent: 40,
    body: { name: 'Sun' },
    perspectives: [
      {
        id: '1A',
        title: 'Job Displacement',
        summary: 'Layoffs.',
        volume_percent: 50,
        representative_posts: [
          { author: 'maya', text: 'Agencies replaced junior writers with an LLM payroll strategy.', likes: 10 },
          { author: 'union', text: 'If your job is summarize the meeting, automating you was easy.', likes: 8 },
        ],
      },
      {
        id: '1B',
        title: 'Acceleration Optimism',
        summary: 'Faster models.',
        volume_percent: 30,
        representative_posts: [
          { author: 'build', text: 'Open weights are the printing press and the panic is a literacy panic.', likes: 6 },
        ],
      },
      {
        id: '1C',
        title: 'Safety Alignment',
        summary: 'Evals.',
        volume_percent: 20,
        representative_posts: [
          { author: 'eval', text: 'Capability demos dropped. The public eval suite did not.', likes: 5 },
        ],
      },
    ],
  },
  {
    id: 2,
    name: 'Housing Costs',
    total_volume_percent: 25,
    body: { name: 'Mercury' },
    perspectives: [
      {
        id: '2A',
        title: 'Rent Burden',
        summary: 'Wages vs rent.',
        volume_percent: 100,
        representative_posts: [
          { author: 'lease', text: 'Rent ate another raise this month. Housing is the whole conversation.', likes: 12 },
        ],
      },
    ],
  },
]

const jobs = engage('junior writers replaced by an LLM', topics, { topicId: 1 })
assert.equal(jobs.presence, 'majority')
assert.equal(jobs.bestFace.title, 'Job Displacement')
assert.ok(jobs.supporting.length >= 1)
assert.match(verdictCopy(jobs).title, /loud face/i)

const press = engage('open weights printing press literacy panic', topics, { topicId: 1 })
assert.equal(press.presence, 'minority')
assert.equal(press.bestFace.title, 'Acceleration Optimism')
assert.equal(press.loudUnmatchedFace.title, 'Job Displacement')
assert.match(verdictCopy(press).title, /minority/i)

const nike = engage('Nike sneakers', topics)
assert.equal(nike.presence, 'absent')
assert.equal(nike.scope, 'sky')
assert.match(verdictCopy(nike).title, /not a planet/i)

const housing = engage('rent and housing costs', topics)
assert.equal(housing.presence, 'minority')
assert.equal(housing.bestTopic.name, 'Housing Costs')
assert.ok(housing.followups.some((item) => item.action === 'open-topic'))

const face = engage('Why were writers replaced?', topics, { topicId: 1, perspectiveId: '1A' })
assert.equal(face.scope, 'face')
assert.equal(face.intent, 'why')
assert.ok(face.hitCount >= 1)

console.log('engagement tokenizer and verdicts ok')
