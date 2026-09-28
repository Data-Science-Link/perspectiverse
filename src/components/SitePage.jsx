import {
  AUTHOR_GITHUB_URL,
  AUTHOR_HANDLE,
  AUTHOR_NAME,
  FEEDBACK_URL,
  REPO_URL,
  SPONSORS_URL,
  neighborPages,
  pageById,
} from '../lib/pages'
import { OverviewGraphic, SystemsGraphic, TechnicalMapGraphic } from './MethodologyGraphics'

const FAQ_ITEMS = [
  {
    q: 'Is this a poll of everyone?',
    a: 'No. It is a sample of public English posts — usually Bluesky — from the last week. That is internet talk, not humanity. Younger, Western, and tech-heavy voices are over-represented.',
  },
  {
    q: 'What does planet size mean?',
    a: 'Share of attention in this sample. Bigger means more people were talking about that topic this week. Size is not importance, truth, or how much you should care.',
  },
  {
    q: 'What does the gold face mean?',
    a: 'The loudest opinion on that planet — the majority of the posts we kept for that topic. Loudest is not truest. Shorter faces are real minority views.',
  },
  {
    q: 'Why only ten planets?',
    a: 'So the sky stays readable. The ten largest topics after noise is dropped. Posts that fit no planet are left out of the percentages.',
  },
  {
    q: 'How often does it update?',
    a: 'Once a day. The pipeline looks at the last 168 hours, writes one data file, and the site loads that file. There is no live firehose in your browser.',
  },
  {
    q: 'Why is my take missing?',
    a: 'It may be rare in this sample, folded into a nearby face, or in the leftover posts that never became a planet. A face summary also smooths over disagreement inside that view.',
  },
  {
    q: 'Is this social listening or brand monitoring?',
    a: 'No. Those tools start from a query you already named. Perspectiverse starts from a week of public posts and keeps the ten largest topics. If something you care about is not a planet, that is the finding.',
  },
  {
    q: 'Can I search for a brand?',
    a: 'Not on this public page. Operators can run the live pipeline with --query on a laptop. Custom universes are a separate product idea, not the homepage.',
  },
  {
    q: 'Where does the data come from right now?',
    a: 'The public site may still be on demo data — made-up example posts, clearly labeled. The live path reads public Bluesky search. Either way you are looking at a snapshot, not your personal feed.',
  },
  {
    q: 'Do you keep the posts?',
    a: 'The published sky keeps a handful of example posts per face. The rest of the sample dies with the daily job. Nothing here is a firehose archive.',
  },
]

function PagePager({ pageId, onOpenPage }) {
  const { prev, next } = neighborPages(pageId)
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
    return 'demo data (made-up example posts, not a live feed)'
  }
  if (data.source === 'bluesky') return 'public English posts on Bluesky'
  return 'the snapshot bundled with this page'
}

function AboutPage({ data, onOpenPage }) {
  return (
    <>
      <p className="lede">
        Perspectiverse turns a week of public conversation into a small solar system so you
        can step out of an echo chamber. Tilt to see every side. Check whether your take is
        the majority, a minority, or not on the map at all.
      </p>
      <section>
        <h2>What you are looking at</h2>
        <p>
          The largest topic sits in the center as the sun. The next nine orbit around it.
          Open a planet and it becomes a crystal of two to six faces — one per real
          perspective, never more than a cube. Gold is the loudest opinion on that topic.
        </p>
      </section>
      <section>
        <h2>This week&apos;s snapshot</h2>
        <p>
          Source: {sourceLine(data)}. Window: the last {data?.window_hours ?? 168} hours.
          {data?.last_updated ? ` Updated ${data.last_updated}.` : ''} Only the ten largest
          topics are shown.
        </p>
      </section>
      <section>
        <h2>What this is not</h2>
        <ul className="page-list">
          <li>Not a poll, census, or score of who is right.</li>
          <li>Not social listening or a brand dashboard. Those start from a name you already typed.</li>
          <li>Not a live feed. It is yesterday’s snapshot of a week.</li>
        </ul>
      </section>
      <section>
        <h2>How to read it</h2>
        <ol className="page-list is-numbered">
          <li>Drag, pinch, or tilt. Planets keep turning so every side comes into view.</li>
          <li>Bigger planet = more talk this week, not more importance.</li>
          <li>Tap a planet, then a face. Gold is the majority — loudest, not truest.</li>
        </ol>
        <button type="button" className="text-link" onClick={() => onOpenPage('methodology')}>
          See how the sky is made
        </button>
      </section>
    </>
  )
}

function AuthorPage() {
  return (
    <>
      <p className="lede">
        {AUTHOR_NAME} builds Perspectiverse as a civic observatory: a way to see the shape
        of public talk without asking a feed to decide what matters.
      </p>
      <section>
        <h2>Why this exists</h2>
        <p>
          Feeds flatten argument into a For/Against scroll, and they hide scale. A loud
          fight can look like the whole sky. This project puts attention and disagreement
          in space: planet size for how widely something was discussed, faces for the
          actual views inside it.
        </p>
        <p>
          It is an independent research prototype — MIT licensed, cheap on purpose, and
          meant to stay readable on a phone.
        </p>
      </section>
      <section>
        <h2>Find Michael</h2>
        <ul className="page-list">
          <li>
            GitHub:{' '}
            <a href={AUTHOR_GITHUB_URL} target="_blank" rel="noreferrer">
              @{AUTHOR_HANDLE}
            </a>
          </li>
          <li>
            This repo:{' '}
            <a href={REPO_URL} target="_blank" rel="noreferrer">
              perspectiverse
            </a>
          </li>
          <li>
            Prefer a note?{' '}
            <a href={FEEDBACK_URL} target="_blank" rel="noreferrer">
              Open a GitHub issue
            </a>
          </li>
        </ul>
      </section>
    </>
  )
}

function MethodologyPage() {
  return (
    <>
      <p className="lede">
        One daily job reads a week of public posts, finds ten topics and a few opinions
        each, and writes a file. The site is that file, drawn as a sky.
      </p>

      <section>
        <h2>The big picture</h2>
        <p>
          You never query Bluesky from the browser. You never talk to a model from the
          browser. Clustering and labeling happen once, then the observatory just looks.
        </p>
        <OverviewGraphic />
      </section>

      <section>
        <h2>How the systems connect</h2>
        <p>
          Collect, sort, name, publish. Each stage is boring on purpose so the public
          sky can stay free. The map is the whole path; the cards underneath spell out
          what each box actually does.
        </p>
        <TechnicalMapGraphic />
        <SystemsGraphic />
      </section>

      <section>
        <h2>What we do not claim</h2>
        <ul className="page-list">
          <li>A face title is a summary of a cluster, not a person.</li>
          <li>Percentages ignore leftover posts that never became a planet.</li>
          <li>Bluesky is not the world. Demo mode is not a live feed.</li>
        </ul>
      </section>
    </>
  )
}

function FaqPage() {
  return (
    <>
      <p className="lede">
        Short answers. If something still feels off, that is useful — tell us.
      </p>
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
        The public sky is built to cost almost nothing — about a dollar a month at most
        today. Donations keep it independent, not pay the hosting bill.
      </p>
      <section>
        <h2>What support is for</h2>
        <ul className="page-list">
          <li>Keep the civic homepage query-free and ad-free.</li>
          <li>Thicken the snapshot: more example posts, better labels, a larger sample.</li>
          <li>Time to explain the method in public, not hide it in a dashboard.</li>
        </ul>
      </section>
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
        <p>
          If sponsorships are not open yet, starring the repo and{' '}
          <a href={FEEDBACK_URL} target="_blank" rel="noreferrer">
            sending feedback
          </a>{' '}
          is the most useful thing. There is no paywall on the sky.
        </p>
      </section>
    </>
  )
}

const PAGE_BODY = {
  about: AboutPage,
  author: AuthorPage,
  methodology: MethodologyPage,
  faq: FaqPage,
  donate: DonatePage,
}

export default function SitePage({ pageId, data, onOpenPage }) {
  const meta = pageById(pageId)
  const Body = PAGE_BODY[pageId]
  if (!meta || !Body) return null

  return (
    <main className="site-page" id="site-page">
      <div className="site-page-inner">
        <p className="eyebrow">{meta.eyebrow}</p>
        <h1>{meta.heading}</h1>
        <Body data={data} onOpenPage={onOpenPage} />
        <PagePager pageId={pageId} onOpenPage={onOpenPage} />
      </div>
    </main>
  )
}
