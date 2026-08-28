// The project's headline contribution, stated up front so anyone who opens the
// app sees what makes it novel — not just "multi-agent vs single AI".
export default function NoveltyBand() {
  return (
    <section className="novelty-band">
      <span className="nb-mark" aria-hidden>
        <svg width="18" height="18" viewBox="0 0 16 16" fill="currentColor">
          <path d="M8 0.8l1.6 4.4 4.4 1.6-4.4 1.6L8 12.8 6.4 8.4 2 6.8 6.4 5.2z" />
        </svg>
      </span>
      <div className="nb-text">
        <span className="nb-eyebrow">What makes this novel</span>
        <p className="nb-lead">
          Most AI test-review is <b>guesswork</b> — agents critique each other from opinion
          alone. This framework lets the reviewer <b>run the tests against correct code first</b>,
          so its critique is grounded in <b>real execution</b>. The question it tests: does that
          catch bugs pure AI debate misses?
        </p>
      </div>
    </section>
  );
}
