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
  pageById,
} from '../lib/pages'
import { OverviewGraphic, SystemsGraphic, TechnicalMapGraphic } from './MethodologyGraphics'

const FAQ_ITEMS = [
  {
    q: 'What is this for?',
    a: 'To see what the public is paying attention to, what the opinions actually are, and that there are several of them — so you can leave an echo chamber and show up to debate prepared, not scandalized by a caricature. The Vision page spells it out.',
  },
  {
    q: 'Is this a poll of everyone?',
    a: 'No. It is a sample of public English posts — usually Bluesky — from the last week. That is internet talk, not humanity. Younger, Western, and tech-heavy voices are over-represented.',
  },
  {
    q: 'What does planet size mean?',
    a: 'Share of attention in this sample. Bigger means more people were talking about that topic this week. Size is not importance, truth, or how much you should care.',
  },
  {
    q: 'What does the longest spike mean?',
    a: 'The most common opinion on that planet — the largest share of the posts we kept for that topic. That spike is the longest and the darkest shade of the planet color. A smaller view is shorter and lighter. A dashed face has no perspective. Loudest is not truest.',
  },
  {
    q: 'Why only ten planets?',
    a: 'So the solar system stays readable. The ten largest topics after noise is dropped. Posts that fit no planet are left out of the percentages.',
  },
  {
    q: 'How often does it update?',
    a: 'Once a day. The pipeline looks at the last 168 hours, writes one data file, and the site loads that file. There is no live firehose in your browser.',
  },
  {
    q: 'Why is my take missing?',
    a: 'It may be rare in this sample, folded into a nearby face, or in the leftover posts that never became a planet. Opening a face shows a steelman of that view plus example posts — a synthesis, not every disagreement inside it.',
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
    a: 'A retained sample of English Bluesky posts from the last week, cleaned of obvious spam. The daily job rotates about one seventh of that sample. You are looking at a snapshot, not your personal feed.',
  },
  {
    q: 'Do you keep the posts?',
    a: 'The published snapshot keeps a handful of example posts per face. About a thousand cleaned posts sit in a retained SQLite window so tomorrow’s job can drop the oldest seventh and add yesterday’s posts. That is not a firehose archive.',
  },
  {
    q: 'How do I get in touch?',
    a: 'The Connect page has GitHub, LinkedIn, and a link to open an issue. There is no project inbox in the browser.',
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

function VisionPage({ onOpenPage }) {
  return (
    <>
      <p className="lede">
        Be well informed about current public attention, public opinion, and the several
        perspectives that form it. Then walk into debate ready to listen — not already
        scandalized by a caricature.
      </p>

      <div className="vision-points">
        <article className="vision-point">
          <strong>Public attention</strong>
          <p>What people were actually talking about this week — not what a feed ranked because it would keep you scrolling.</p>
        </article>
        <article className="vision-point">
          <strong>Public opinion</strong>
          <p>The views that showed up, common and rare. The longest, darkest spike is the most common. It is not a verdict on who is right.</p>
        </article>
        <article className="vision-point">
          <strong>Multiple perspectives</strong>
          <p>Most topics are not two-sided. A planet holds one to six real takes. Yours might be the long face, a short one, or missing. A dashed face has no perspective.</p>
        </article>
      </div>

      <section>
        <h2>Leave the echo chamber</h2>
        <p>
          Feeds reward what is sticky: outrage, tribe, the take that already agrees with
          you. That is a poor map of the public and a worse way to prepare for talking to
          someone you do not already like.
        </p>
        <p>
          The solar system is supposed to do the opposite. Tilt until every side comes into view.
          Check whether you are the majority, a minority, or not on the planet at all.
          Then you can walk into a conversation without plugging your ears.
        </p>
      </section>

      <section>
        <h2>Earnest debate, not a tribe</h2>
        <p>
          Meaningful public debate is not winning a thread. It is understanding the other
          view well enough to meet it, and being willing to change your mind when the
          facts are better than your side.
        </p>
        <p>
          We should not refuse to talk because we are scandalized by someone&apos;s opinion
          — or by what we imagine they think. That is how people stop being neighbors and
          start being avatars. Cohesive relationships come from seeing the argument as it
          is, not as it was packaged to keep us spinning.
        </p>
      </section>

      <section>
        <h2>Truth is real, and it is worth acting on</h2>
        <p>
          Truth can be nuanced. It still exists. People can hold different perspectives
          and still be aiming at the same thing: what is so, and what to do about it.
        </p>
        <p>
          Knowing the truth, and acting on it, is how you get better outcomes for
          humanity. Staying in tribes with our ears plugged — reinforcing bias, reinforcing
          whatever stuck in the feed — is how we alienate each other and never get there.
        </p>
        <p>
          Perspectiverse cannot hand you the truth. It can show you the shape of the
          public argument so you have a fairer chance of finding it, and of taking action
          accordingly.
        </p>
        <button type="button" className="text-link" onClick={() => onOpenPage('about')}>
          How to read the solar system
        </button>
      </section>
    </>
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
          Open a planet and it becomes a cube. Each real perspective is a spike in
          that planet&apos;s color: darkest for the most common view, the planet color
          for a middle view, and lighter for a smaller one. A dashed face has no
          perspective.
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
          <li>Tap a planet, then a spike. The longest, darkest one is the most common view — loudest, not truest. A dashed face has no perspective.</li>
        </ol>
        <div className="text-links">
          <button type="button" className="text-link" onClick={() => onOpenPage('vision')}>
            Read the vision
          </button>
          <button type="button" className="text-link" onClick={() => onOpenPage('methodology')}>
            See how the solar system is made
          </button>
        </div>
      </section>
    </>
  )
}

function AuthorPage({ onOpenPage }) {
  return (
    <>
      <p className="lede">
        {AUTHOR_NAME} is a data systems and analytics engineer in {AUTHOR_LOCATION}.
        He builds Perspectiverse as a personal civic project: a way to see the shape
        of public talk without asking a feed to decide what matters.
      </p>
      <section>
        <h2>Background</h2>
        <p>
          He started in water resources and ecological engineering — a B.S. at Oregon
          State, then a master&apos;s at UT Austin — and now spends his days turning
          messy operational data into something a decision can stand on. The habit is
          the same here: take a noisy public record, make the structure visible, and
          refuse to pretend a loud corner is the whole solar system.
        </p>
        <p>
          Perspectiverse is independent of his day job. MIT licensed, cheap on purpose,
          and meant to stay readable on a phone.
        </p>
      </section>
      <section>
        <h2>Why this exists</h2>
        <p>
          Feeds flatten argument into a For/Against scroll, and they hide scale. A loud
          fight can look like the whole solar system. This project puts attention and disagreement
          in space: planet size for how widely something was discussed, faces for the
          actual views inside it.
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
            LinkedIn:{' '}
            <a href={LINKEDIN_URL} target="_blank" rel="noreferrer">
              {AUTHOR_NAME}
            </a>
          </li>
          <li>
            This repo:{' '}
            <a href={REPO_URL} target="_blank" rel="noreferrer">
              perspectiverse
            </a>
          </li>
        </ul>
        <button type="button" className="text-link" onClick={() => onOpenPage('connect')}>
          All the ways to connect
        </button>
      </section>
    </>
  )
}

function MethodologyPage() {
  return (
    <>
      <p className="lede">
        One daily job reads a week of public posts, finds ten topics and a few opinions
        each, and writes a file. The site is that file, drawn as a solar system.
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
          solar system can stay free. The map is the whole path; the cards underneath spell out
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
        The public solar system is built to cost almost nothing — about a dollar a month at most
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
          is the most useful thing. There is no paywall on Perspectiverse.
        </p>
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

function ConnectPage({ onOpenPage }) {
  return (
    <>
      <p className="lede">
        {AUTHOR_NAME} is in {AUTHOR_LOCATION}. If you want to talk about Perspectiverse, the
        method, a missing perspective, or just say hello — these are the public doors.
        There is no inbox hiding in the page.
      </p>
      <nav className="connect-list" aria-label="Ways to connect">
        <a className="connect-link" href={AUTHOR_GITHUB_URL} target="_blank" rel="noreferrer">
          <GitHubIcon />
          <span>
            <strong>GitHub</strong>
            <em>@{AUTHOR_HANDLE} — profile and other work</em>
          </span>
        </a>
        <a className="connect-link" href={LINKEDIN_URL} target="_blank" rel="noreferrer">
          <LinkedInIcon />
          <span>
            <strong>LinkedIn</strong>
            <em>{AUTHOR_NAME} — {AUTHOR_LOCATION}, data systems and analytics</em>
          </span>
        </a>
        <a className="connect-link" href={REPO_URL} target="_blank" rel="noreferrer">
          <GitHubIcon />
          <span>
            <strong>This repository</strong>
            <em>perspectiverse — star, fork, or open a pull request</em>
          </span>
        </a>
        <a className="connect-link" href={FEEDBACK_URL} target="_blank" rel="noreferrer">
          <IssueIcon />
          <span>
            <strong>Send feedback</strong>
            <em>Open a GitHub issue about Perspectiverse</em>
          </span>
        </a>
      </nav>
      <p>
        There is no project Twitter, Bluesky, or email form. If that changes, it will
        show up here.
      </p>
      <button type="button" className="text-link" onClick={() => onOpenPage('author')}>
        About the author
      </button>
    </>
  )
}

const PAGE_BODY = {
  vision: VisionPage,
  about: AboutPage,
  author: AuthorPage,
  connect: ConnectPage,
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
