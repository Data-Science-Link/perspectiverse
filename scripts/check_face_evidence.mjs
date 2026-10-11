import assert from 'node:assert/strict'
import { morePostsLabel } from '../src/lib/postFeed.js'

assert.equal(morePostsLabel(1, false), 'Show 1 more post')
assert.equal(morePostsLabel(2, false), 'Show 2 more posts')
assert.equal(morePostsLabel(1, true), 'Show fewer posts')

console.log('face evidence copy checks passed')
