import assert from 'node:assert/strict'
import { PERSPECTIVE_COLORS, rankPerspectives, spikeColor } from '../src/lib/colors.js'
import { clampFaceCount, faceLayout, shapeName } from '../src/lib/faces.js'
import { SOLAR_BODIES, bodyForRank, decorateTopics } from '../src/lib/planets.js'
import { polyhedron } from '../src/lib/polyhedra.js'
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
assert.equal(
  selectionURL({ category: 'all', topicId: null, perspectiveId: null, page: 'about' }),
  '/perspectiverse/?page=about',
)

assert.equal(clampFaceCount(1), 2)
assert.equal(clampFaceCount(9), 6)
assert.equal(shapeName(2), 'Diamond')
assert.equal(shapeName(4), 'Tetrahedron')
assert.equal(shapeName(5), 'Pyramid')
assert.equal(shapeName(6), 'Cube')
assert.equal(faceLayout(2).length, 2)
assert.equal(faceLayout(4).length, 4)
assert.equal(faceLayout(6).length, 6)
assert.equal(polyhedron(5).faces.length, 5)
assert.equal(polyhedron(6).faces.length, 6)
assert.equal(spikeColor(0), PERSPECTIVE_COLORS[0])
assert.equal(spikeColor(0), '#f4c14e')
assert.deepEqual(
  rankPerspectives([
    { id: 'quiet', volume_percent: 12 },
    { id: 'loud', volume_percent: 40 },
  ]).map((item) => item.id),
  ['loud', 'quiet'],
)

console.log('planet order, selection urls, and face layouts ok')
