const STEPS = [
  {
    title: 'Public posts from the web',
    body: 'We gather today’s posts — for example from Bluesky, X, and others.',
  },
  {
    title: 'Each planet is a topic',
    body: 'Posts about the same story are grouped together. A bigger planet means more people are talking about it.',
  },
  {
    title: '2–6 perspectives',
    body: 'Inside a topic, different takes are grouped and shown by how common they are — not scored as right or wrong.',
  },
  {
    title: 'How to explore',
    body: 'Tap a planet, or drag to look around. Bars show each view’s share. Then read the summary and example posts. The menu has the rest.',
  },
]

export default function WelcomeHowItWorks() {
  return (
    <figure className="welcome-graphic welcome-flow">
      <ol className="welcome-steps">
        {STEPS.map((step) => (
          <li key={step.title}>
            <strong>{step.title}</strong>
            <span>{step.body}</span>
          </li>
        ))}
      </ol>
      <figcaption>Curious how it works? See Methodology in the menu.</figcaption>
    </figure>
  )
}
