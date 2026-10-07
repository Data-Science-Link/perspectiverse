import {
  AUTHOR_GITHUB_URL,
  AUTHOR_HANDLE,
  AUTHOR_LOCATION,
  AUTHOR_NAME,
  FEEDBACK_URL,
  LINKEDIN_URL,
  REPO_URL,
  SPONSORS_URL,
  neighborPages,
  normalizePageId,
  pageById,
} from '../lib/pages'
import { OverviewGraphic, SystemsGraphic } from './MethodologyGraphics'

const FAQ_ITEMS = [
  {
    q: 'What is this for?',
    a: 'To see what people were discussing this week, how much attention each topic drew, and the main perspectives inside it — without a feed picking winners.',
  },
  {
    q: 'Is this a poll of everyone?',
    a: 'No. It is a sample of public English posts — usually Bluesky — from the last week. Internet talk is not humanity.',
  },
  {
    q: 'What does planet size mean?',
    a: 'Share of attention in this sample.',
  },
  {
    q: 'What does a longer bar mean?',
    a: 'A larger share of that conversation. We do not score views as right or wrong.',
  },
  {
    q: 'Why only ten planets?',
    a: 'So the solar system stays readable. The job keeps the largest tight groups and stops at ten.',
  },
  {
    q: 'How often does it update?',
    a: 'Once a day. The pipeline looks at the last 168 hours and writes one data file.',
  },
  {
    q: 'Why is my take missing?',
    a: 'It may be rare in this sample, filtered out, or never clustered into a planet.',
  },
  {
    q: 'Where does the data come from?',
    a: 'Today: English Bluesky posts from the last week, after spam and quality filters. We hope to add broader inputs later.',
  },
  {
    q: 'How do I get in touch?',
    a: 'GitHub issues and the links on the Connect page.',
  },
]

function PagePager({ pageId, onOpenPage }) {
  const canonical = normalizePageId(pageId) ?? pageId
  const { prev, next } = neighborPages(canonical)
  if (!prev && !next) return null
  return (
    <nav className="page-pager" aria-label="More pages">
      {prev ? (
        <button
          type="button"
          className="page-pager-link"
          aria-label={`Previous: ${prev.menuLabel}`}
          onClick={() => onOpenPage(prev.id)}
        >
          <span>Previous</span>
          <strong>{prev.menuLabel}</strong>
        </button>
      ) : (
        <span />
      )}
      {next ? (
        <button
          type="button"
          className="page-pager-link is-next"
          aria-label={`Next: ${next.menuLabel}`}
          onClick={() => onOpenPage(next.id)}
        >
          <span>Next</span>
          <strong>{next.menuLabel}</strong>
        </button>
      ) : null}
    </nav>
  )
}

function sourceLine(data) {
  if (!data) return 'the snapshot bundled with this page'
  if (data.mode === 'demo' || data.source === 'synthetic') {
    return 'demo data (synthetic example posts)'
  }
  if (data.source === 'bluesky') return 'public English posts on Bluesky'
  return 'the snapshot bundled with this page'
}

function AboutPage({ data, onOpenPage }) {
  return (
    <>
      <p className="lede">
        Perspectiverse maps a week of public conversation as a small solar system. We aim to show
        how much attention each topic drew and the perspectives that showed up — ordered by prevalence,
        with each side steelmanned in summary form, not ranked as correct or incorrect.
      </p>
      <section>
        <h2>What you see</h2>
        <p>
          The largest topic is the sun; nine more orbit it. Planet size is share of talk in this sample.
          Tap a planet or bar to read summaries and example posts.
        </p>
      </section>
      <section>
        <h2>This week&apos;s snapshot</h2>
        <p>
          Source: {sourceLine(data)}. Window: {data?.window_hours ?? 168} hours.
          {data?.last_updated ? ` Updated ${data.last_updated}.` : ''} Ten planets max.
        </p>
      </section>
      <section>
        <h2>What we are not doing</h2>
        <ul className="page-list">
          <li>Not a poll, census, or truth score.</li>
          <li>Not a live feed or personal timeline.</li>
          <li>Not claiming perfect neutrality — see Methodology for limits and maintainer bias.</li>
        </ul>
        <button type="button" className="text-link" onClick={() => onOpenPage('methodology')}>
          How the map is built
        </button>
      </section>
    </>
  )
}

function MethodologyPage() {
  return (
    <>
      <p className="lede">
        A daily job reads public posts, filters noise, clusters topics, splits perspectives, and writes
        one file. The site only displays that snapshot.
      </p>

      <section>
        <h2>Representation, not verdict</h2>
        <p>
          Perspectives are ordered by how much they showed up in the sample. Summaries try to steelman
          each cluster&apos;s argument — state it clearly as its holders might — without labeling a view
          right or wrong. The goal is to mirror public attention and disagreement as we find it, not to
          interfere with or skew it toward what maintainers wish were true.
        </p>
        <p className="method-disclaimer">
          Michael Link and other maintainers have personal beliefs and biases. This project tries to
          keep them out of the measurement and labeling steps, but no pipeline is perfectly neutral.
          Treat the map as a structured sample, not an oracle.
        </p>
      </section>

      <section>
        <h2>From posts to planets</h2>
        <OverviewGraphic />
      </section>

      <section>
        <h2>Why Bluesky (for now)</h2>
        <p>
          Bluesky offers a free, practical public search API for English posts. That makes a civic
          prototype affordable. It is not representative of the whole world; we hope to add more inputs
          over time so the solar system can better reflect society.
        </p>
      </section>

      <section>
        <h2>Jev filters</h2>
        <p>
          When configured, Jev scores each post for spam, whether it makes a public claim worth mapping,
          and a newspaper-style section (World, Politics, Business, and the rest). High-confidence spam
          drops out. Sections help the topic filter match how editors bucket news — see{' '}
          <code>pipeline/jev.py</code> and the README. Without an API key, regex cleaning and keyword
          sections still run.
        </p>
      </section>

      <section>
        <h2>Pipeline stages</h2>
        <SystemsGraphic />
      </section>

      <section>
        <h2>Limits</h2>
        <ul className="page-list">
          <li>Labels describe clusters, not individuals.</li>
          <li>Percentages omit posts that never became a planet.</li>
          <li>Demo mode uses synthetic posts, not a live feed.</li>
        </ul>
      </section>
    </>
  )
}

function FaqPage() {
  return (
    <>
      <p className="lede">Short answers. Confusing bits are useful feedback.</p>
      <div className="faq-list">
        {FAQ_ITEMS.map((item) => (
          <details key={item.q} className="faq-item">
            <summary>{item.q}</summary>
            <p>{item.a}</p>
          </details>
        ))}
      </div>
      <p>
        <a className="text-link" href={FEEDBACK_URL} target="_blank" rel="noreferrer">
          Open a GitHub issue
        </a>
      </p>
    </>
  )
}

function DonatePage() {
  return (
    <>
      <p className="lede">
        The public solar system is built to cost almost nothing. Donations support independence and time
        on the method, not a large hosting bill.
      </p>
      <section>
        <h2>Ways to help</h2>
        <div className="donate-actions">
          <a className="page-cta" href={SPONSORS_URL} target="_blank" rel="noreferrer">
            Sponsor on GitHub
          </a>
          <a className="page-cta is-quiet" href={REPO_URL} target="_blank" rel="noreferrer">
            Star the repository
          </a>
        </div>
      </section>
    </>
  )
}

function GitHubIcon() {
  return (
    <svg className="connect-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 2a10 10 0 0 0-3.16 19.49c.5.09.68-.22.68-.48v-1.7c-2.78.6-3.37-1.34-3.37-1.34-.46-1.16-1.12-1.47-1.12-1.47-.92-.63.07-.62.07-.62 1 .07 1.54 1.04 1.54 1.04.9 1.54 2.36 1.1 2.94.84.09-.65.35-1.1.64-1.35-2.22-.25-4.56-1.11-4.56-4.95 0-1.1.39-1.99 1.03-2.69-.1-.25-.45-1.27.1-2.64 0 0 .84-.27 2.75 1.02A9.56 9.56 0 0 1 12 6.8c.85 0 1.7.11 2.5.32 1.9-1.3 2.74-1.02 2.74-1.02.55 1.37.2 2.39.1 2.64.64.7 1.03 1.6 1.03 2.69 0 3.85-2.34 4.7-4.57 4.95.36.31.68.92.68 1.86v2.76c0 .26.18.58.69.48A10 10 0 0 0 12 2Z" />
    </svg>
  )
}

function LinkedInIcon() {
  return (
    <svg className="connect-icon is-stroke" viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3" y="3" width="18" height="18" rx="3" />
      <path d="M8 10v7M8 7.2v.1M12.5 17v-4.2a2.3 2.3 0 0 1 4.5.6V17" />
    </svg>
  )
}

function IssueIcon() {
  return (
    <svg className="connect-icon is-stroke" viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="8" />
      <circle cx="12" cy="12" r="2.2" />
    </svg>
  )
}

function ConnectPage() {
  return (
    <>
      <p className="lede">
        {AUTHOR_NAME} ({AUTHOR_LOCATION}) builds Perspectiverse as an independent civic project — data
        systems engineer by day, observatory maintainer here.
      </p>
      <nav className="connect-list" aria-label="Ways to connect">
        <a className="connect-link" href={AUTHOR_GITHUB_URL} target="_blank" rel="noreferrer">
          <GitHubIcon />
          <span>
            <strong>GitHub</strong>
            <em>@{AUTHOR_HANDLE}</em>
          </span>
        </a>
        <a className="connect-link" href={LINKEDIN_URL} target="_blank" rel="noreferrer">
          <LinkedInIcon />
          <span>
            <strong>LinkedIn</strong>
            <em>{AUTHOR_NAME}</em>
          </span>
        </a>
        <a className="connect-link" href={REPO_URL} target="_blank" rel="noreferrer">
          <GitHubIcon />
          <span>
            <strong>Repository</strong>
            <em>perspectiverse</em>
          </span>
        </a>
        <a className="connect-link" href={FEEDBACK_URL} target="_blank" rel="noreferrer">
          <IssueIcon />
          <span>
            <strong>Feedback</strong>
            <em>GitHub issue</em>
          </span>
        </a>
      </nav>
    </>
  )
}

const PAGE_BODY = {
  about: AboutPage,
  connect: ConnectPage,
  methodology: MethodologyPage,
  faq: FaqPage,
  donate: DonatePage,
}

export default function SitePage({ pageId, data, onOpenPage }) {
  const canonical = normalizePageId(pageId)
  const meta = pageById(canonical)
  const Body = canonical ? PAGE_BODY[canonical] : null
  if (!meta || !Body) return null

  return (
    <main className="site-page" id="site-page">
      <div className="site-page-inner">
        <p className="eyebrow">{meta.eyebrow}</p>
        <h1>{meta.heading}</h1>
        <Body data={data} onOpenPage={onOpenPage} />
        <PagePager pageId={canonical} onOpenPage={onOpenPage} />
      </div>
    </main>
  )
}
