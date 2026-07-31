// Left-hand brand panel shared by Login and Register.
export default function AuthBrand() {
  return (
    <div className="auth-brand">
      <div className="top">
        <div className="brand-mark">M</div>
        <div>
          <div className="brand-name">MATF</div>
          <div className="brand-sub">Test Framework</div>
        </div>
      </div>

      <div>
        <h2>
          Multi-agent test<br />generation & validation
        </h2>
        <p>
          Turn software requirements into structured, traceable test cases —
          then let specialised agents review, debate and score them against a
          single-prompt baseline.
        </p>
        <div className="pillline">
          <span className="mini-pill">Requirement Analysis</span>
          <span className="mini-pill">Test Generation</span>
          <span className="mini-pill">Review · Consensus</span>
          <span className="mini-pill">Coverage · Quality</span>
        </div>
      </div>

      <p style={{ position: "relative", fontSize: 12.5, color: "rgba(255,255,255,0.6)", margin: 0 }}>
        M.Sc research platform · thesis prototype
      </p>
    </div>
  );
}
