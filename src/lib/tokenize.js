/**
 * Pipeline-compatible tokenizer. Keep in lockstep with
 * pipeline/cluster_math.py tokenize() + STOPWORDS.
 */
export const TOKEN_RE = /[a-z]{3,}/g

export const STOPWORDS = new Set([
  'the',
  'and',
  'for',
  'that',
  'this',
  'with',
  'from',
  'have',
  'about',
  'discussion',
  'debate',
  'policy',
  'public',
  'people',
  'today',
  'just',
  'they',
  'them',
  'their',
  'what',
  'when',
  'where',
  'which',
  'would',
  'could',
  'should',
  'there',
  'here',
  'into',
  'your',
  'youre',
  'been',
  'being',
  'were',
  'was',
  'are',
  'not',
  'but',
  'its',
  'our',
  'out',
  'note',
])

export function tokenize(text) {
  const matches = String(text ?? '').toLowerCase().match(TOKEN_RE) ?? []
  return matches.filter((token) => !STOPWORDS.has(token))
}
