function IconPosts() {
  return (
    <svg className="welcome-mini" viewBox="0 0 48 48" aria-hidden="true">
      <circle cx="11" cy="24" r="7" fill="none" stroke="#6ea8ff" strokeWidth="1.6" />
      <path d="M8 24h6M11 21v6" stroke="#6ea8ff" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M18 20h6M18 28h5" stroke="#f4c14e" strokeWidth="1.6" strokeLinecap="round" />
      <rect x="26" y="10" width="16" height="11" rx="4" fill="rgba(255,255,255,0.06)" stroke="#efeef7" strokeWidth="1.4" />
      <rect x="28" y="26" width="14" height="9" rx="4" fill="rgba(255,255,255,0.04)" stroke="#9a98ad" strokeWidth="1.4" />
    </svg>
  )
}

function IconPlanets() {
  return (
    <svg className="welcome-mini" viewBox="0 0 48 48" aria-hidden="true">
      <circle cx="12" cy="30" r="6" fill="#e25a2b" />
      <circle cx="24" cy="26" r="9" fill="#4aa3e6" />
      <circle cx="37" cy="22" r="11" fill="#f4c14e" />
    </svg>
  )
}

function IconFaces() {
  return (
    <svg className="welcome-mini" viewBox="0 0 48 48" aria-hidden="true">
      <circle cx="18" cy="24" r="12" fill="#1d4e78" />
      <path d="M18 12 A12 12 0 0 1 28.4 30.5 L18 24 Z" fill="#f4c14e" />
      <path d="M18 12 A12 12 0 0 0 8.2 18.5 L18 24 Z" fill="#4aa3e6" />
      <path d="M8.2 18.5 A12 12 0 0 0 18 36 L18 24 Z" fill="#e25a2b" />
      <rect x="33" y="14" width="11" height="4" rx="2" fill="#f4c14e" />
      <rect x="33" y="22" width="8" height="4" rx="2" fill="#4aa3e6" />
      <rect x="33" y="30" width="5" height="4" rx="2" fill="#e25a2b" />
    </svg>
  )
}

function IconExplore() {
  return (
    <svg className="welcome-mini" viewBox="0 0 48 48" aria-hidden="true">
      <circle cx="16" cy="18" r="5" fill="none" stroke="#efeef7" strokeWidth="1.6" />
      <path d="M16 23 v6" stroke="#efeef7" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M22 16 h8 l-3-3 M30 16 l-3 3" stroke="#f4c14e" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      <rect x="10" y="34" width="22" height="4" rx="2" fill="#4aa3e6" />
      <rect x="10" y="40" width="14" height="4" rx="2" fill="rgba(74,163,230,0.55)" />
    </svg>
  )
}

const STEPS = [
  {
    title: 'Public posts from the web',
    body: 'We gather today’s posts — for example from Bluesky, X, and others.',
    icon: <IconPosts />,
  },
  {
    title: 'Each planet is a topic',
    body: 'Posts about the same story are grouped together. A bigger planet means more people are talking about it.',
    icon: <IconPlanets />,
  },
  {
    title: '2–6 perspectives',
    body: 'Inside a topic, different takes are grouped and shown by how common they are — not scored as right or wrong.',
    icon: <IconFaces />,
  },
  {
    title: 'How to explore',
    body: 'Tap a planet, or drag to look around. Bars show each view’s share. Then read the summary and example posts. The menu has the rest.',
    icon: <IconExplore />,
  },
]

export default function WelcomeHowItWorks() {
  return (
    <figure className="welcome-graphic welcome-flow">
      <ol className="welcome-steps">
        {STEPS.map((step) => (
          <li key={step.title}>
            <span className="welcome-icon">{step.icon}</span>
            <span className="welcome-copy">
              <strong>{step.title}</strong>
              <span>{step.body}</span>
            </span>
          </li>
        ))}
      </ol>
      <figcaption>
        <span>An unbiased pipeline, so you can meet the biases that challenge your own.</span>
        <span>Curious how it works? See Methodology in the menu.</span>
      </figcaption>
    </figure>
  )
}
