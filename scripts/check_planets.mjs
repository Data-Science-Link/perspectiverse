import assert from 'node:assert/strict'
import { SOLAR_BODIES, bodyForRank, decorateTopics } from '../src/lib/planets.js'
import { selectionURL } from '../src/lib/navigation.js'

assert.equal(SOLAR_BODIES.length, 10)
assert.deepEqual(
  SOLAR_BODIES.map((body) => body.key),
  ['sun', 'mercury', 'venus', 'earth', 'mars', 'jupiter', 'saturn', 'uranus', 'neptune', 'pluto'],
)
assert.equal(bodyForRank(0).name, 'Sun')
assert.equal(bodyForRank(3).name, 'Earth')
assert.equal(bodyForRank(6).rings, true)
assert.equal(bodyForRank(9).name, 'Pluto')
assert.equal(bodyForRank(-1).name, 'Sun')
assert.equal(bodyForRank(99).name, 'Pluto')

const decorated = decorateTopics([{ id: 4, name: 'Example' }, { id: 9, name: 'Other' }])
assert.equal(decorated[0].body.key, 'sun')
assert.equal(decorated[1].body.key, 'mercury')

globalThis.window = {
  location: { pathname: '/perspectiverse/', search: '' },
}
assert.equal(
  selectionURL({ category: 'Technology', topicId: 3, perspectiveId: '3A' }),
  '/perspectiverse/?category=Technology&topic=3&face=3A',
)
assert.equal(selectionURL({ category: 'all', topicId: null, perspectiveId: null }), '/perspectiverse/')

console.log('planet order and selection urls ok')
