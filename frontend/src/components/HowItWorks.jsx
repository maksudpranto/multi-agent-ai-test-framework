// The story spine of the whole product, shown wherever a newcomer might land.
// Three steps: Describe -> Generate -> Prove. Keep the wording plain — an
// examiner should grasp the idea in one read.

const STEPS = [
  {
    n: 1,
    key: "describe",
    title: "Describe",
    body: "Give a plain-language requirement — a user story, acceptance criteria, anything.",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
        <path d="M6 3h9l4 4v14a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z" />
        <path d="M14 3v5h5M8.5 13h7M8.5 17h7M8.5 9h2" />
      </svg>
    ),
  },
  {
    n: 2,
    key: "generate",
    title: "Generate",
    body: "A team of AI agents writes the test cases, then reviews and debates them to make them better.",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="8" cy="8" r="3" />
        <circle cx="16" cy="8" r="3" />
        <path d="M3 20c0-2.8 2.2-5 5-5s5 2.2 5 5M13.5 15.2A5 5 0 0 1 21 20" />
      </svg>
    ),
  },
  {
    n: 3,
    key: "prove",
    title: "Prove",
    body: "Run those tests against code with deliberately planted bugs — and count how many bugs they catch.",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z" />
        <path d="M9 12l2 2 4-4" />
      </svg>
    ),
  },
];

export default function HowItWorks({ compact = false }) {
  return (
    <div className={`hiw ${compact ? "compact" : ""}`}>
      {STEPS.map((s, i) => (
        <div className="hiw-step" key={s.key}>
          <div className="hiw-card">
            <div className="hiw-top">
              <span className="hiw-badge">{s.n}</span>
              <span className="hiw-icon">{s.icon}</span>
            </div>
            <div className="hiw-title">{s.title}</div>
            <div className="hiw-body">{s.body}</div>
          </div>
          {i < STEPS.length - 1 && (
            <span className="hiw-arrow" aria-hidden>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M5 12h14M13 6l6 6-6 6" />
              </svg>
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
