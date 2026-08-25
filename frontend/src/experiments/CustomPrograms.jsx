import { useState } from "react";
import { api } from "../api/client";
import Modal from "../components/Modal";

// Spark mark used on AI-driven actions across the app.
const SparkIcon = () => (
  <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" aria-hidden>
    <path d="M8 0.8l1.5 4.2 4.2 1.5-4.2 1.5L8 12.2 6.5 8 2.3 6.5 6.5 5z" />
    <path d="M13 10.2l.7 1.9 1.9.7-1.9.7-.7 1.9-.7-1.9-1.9-.7 1.9-.7z" opacity="0.8" />
  </svg>
);

// The fault classes the benchmark taxonomy recognises (kept in sync with the
// backend FAULT_TAXONOMY). Tagging a bug is optional but powers the
// "which kinds of bug did each catch?" breakdown.
const FAULT_TYPES = [
  { key: "", label: "— fault type (optional) —" },
  { key: "boundary", label: "Boundary (off-by-one)" },
  { key: "wrong_constant", label: "Wrong value" },
  { key: "wrong_operator", label: "Wrong operator" },
  { key: "missing_condition", label: "Missing check" },
  { key: "control_flow", label: "Control flow" },
];
const FAULT_LABEL = Object.fromEntries(FAULT_TYPES.map((f) => [f.key, f.label]));

const EXAMPLE_REF = `def is_even(n):
    return n % 2 == 0`;

// A complete, self-checking example the user can prefill to see the expected
// shape. Both bugs genuinely diverge from the reference on the given inputs.
const SAMPLE = {
  title: "Checkout total with discount",
  entrypoint: "final_price",
  requirement:
    "A shop gives a 10% discount when the subtotal is $100 or more; below $100 there is no discount. Return the amount to charge, rounded to the nearest cent.",
  reference: `def final_price(subtotal):
    if subtotal >= 100:
        return round(subtotal * 0.9, 2)
    return round(subtotal, 2)`,
  inputs: "[100]\n[99.99]\n[250]\n[0]\n[100.5]",
  bugs: [
    {
      description: "Uses > 100 instead of >= 100, so an exact $100 subtotal misses the discount",
      fault_type: "boundary",
      code: `def final_price(subtotal):
    if subtotal > 100:
        return round(subtotal * 0.9, 2)
    return round(subtotal, 2)`,
    },
    {
      description: "Applies a 20% discount instead of 10%",
      fault_type: "wrong_constant",
      code: `def final_price(subtotal):
    if subtotal >= 100:
        return round(subtotal * 0.8, 2)
    return round(subtotal, 2)`,
    },
  ],
};

const emptyBug = () => ({ description: "", fault_type: "", code: "" });

// Parse the inputs textarea: one call's positional arguments per line, each a
// JSON array — e.g. "[1000, 200, 0, 500]". Returns [rows, error].
function parseInputs(text) {
  const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
  if (lines.length === 0) return [null, "Add at least one input row."];
  const rows = [];
  for (let i = 0; i < lines.length; i++) {
    let v;
    try {
      v = JSON.parse(lines[i]);
    } catch {
      return [null, `Line ${i + 1} isn't valid JSON — use e.g. [1000, 200, 0, 500].`];
    }
    if (!Array.isArray(v)) return [null, `Line ${i + 1} must be a JSON array of arguments.`];
    rows.push(v);
  }
  return [rows, null];
}

function AddForm({ onCreated, onCancel }) {
  const [title, setTitle] = useState("");
  const [entrypoint, setEntrypoint] = useState("");
  const [requirement, setRequirement] = useState("");
  const [reference, setReference] = useState("");
  const [inputs, setInputs] = useState("");
  const [bugs, setBugs] = useState([emptyBug()]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [warnings, setWarnings] = useState([]);

  function setBug(i, patch) {
    setBugs((prev) => prev.map((b, j) => (j === i ? { ...b, ...patch } : b)));
  }

  function fillSample() {
    setTitle(SAMPLE.title);
    setEntrypoint(SAMPLE.entrypoint);
    setRequirement(SAMPLE.requirement);
    setReference(SAMPLE.reference);
    setInputs(SAMPLE.inputs);
    setBugs(SAMPLE.bugs.map((b) => ({ ...b })));
    setError("");
    setWarnings([]);
  }

  async function submit(e) {
    e.preventDefault();
    setError("");
    setWarnings([]);
    const [rows, inputErr] = parseInputs(inputs);
    if (inputErr) {
      setError(inputErr);
      return;
    }
    const cleanBugs = bugs
      .map((b) => ({ ...b, description: b.description.trim(), code: b.code.trim() }))
      .filter((b) => b.description || b.code);
    if (cleanBugs.length === 0) {
      setError("Add at least one bug (a copy of the reference with one deliberate fault).");
      return;
    }
    for (let i = 0; i < cleanBugs.length; i++) {
      if (!cleanBugs[i].description || !cleanBugs[i].code) {
        setError(`Bug ${i + 1} needs both a description and code.`);
        return;
      }
    }
    setBusy(true);
    try {
      const res = await api.createCustomProgram({
        title: title.trim(),
        entrypoint: entrypoint.trim(),
        requirement: requirement.trim(),
        reference_code: reference,
        canonical_inputs: rows,
        mutants: cleanBugs.map((b) => ({
          description: b.description,
          fault_type: b.fault_type || null,
          code: b.code,
        })),
      });
      if (res.warnings && res.warnings.length) {
        // Keep the form open so the user sees which bug is dead, but the program
        // is already saved — surface the warnings, then let them close.
        setWarnings(res.warnings);
        onCreated(res.program, true);
      } else {
        onCreated(res.program, false);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="cp-form" onSubmit={submit}>
      <div className="cp-samplebar">
        <span className="muted">Not sure of the format?</span>
        <button type="button" className="cp-sample-btn" onClick={fillSample}>
          Prefill a sample program
        </button>
      </div>

      <div className="cp-form-grid">
        <label className="field">
          <span className="field-label">Program name</span>
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Is even" required />
        </label>
        <label className="field">
          <span className="field-label">Function name (entrypoint)</span>
          <input value={entrypoint} onChange={(e) => setEntrypoint(e.target.value)} placeholder="is_even" required />
        </label>
      </div>

      <label className="field">
        <span className="field-label">Requirement</span>
        <span className="field-sub">Plain-English description the agents generate tests from.</span>
        <textarea rows={2} value={requirement} onChange={(e) => setRequirement(e.target.value)} placeholder="Return whether an integer n is even." required />
      </label>

      <label className="field">
        <span className="field-label">Reference implementation <span className="cp-hint">the correct code — the oracle</span></span>
        <textarea className="code-area" rows={5} value={reference} onChange={(e) => setReference(e.target.value)} placeholder={EXAMPLE_REF} spellCheck={false} required />
      </label>

      <label className="field">
        <span className="field-label">Inputs <span className="cp-hint">one call's arguments per line, as a JSON array</span></span>
        <textarea className="code-area" rows={3} value={inputs} onChange={(e) => setInputs(e.target.value)} placeholder={"[2]\n[3]\n[0]\n[-1]"} spellCheck={false} required />
      </label>

      <div className="field">
        <span className="field-label">Bugs to seed <span className="cp-hint">each is the reference with one deliberate fault</span></span>
        <div className="cp-bugs">
          {bugs.map((b, i) => (
            <div className="cp-bug" key={i}>
              <div className="cp-bug-head">
                <span className="cp-bug-n">Bug {i + 1}</span>
                {bugs.length > 1 && (
                  <button type="button" className="cp-bug-del" onClick={() => setBugs((p) => p.filter((_, j) => j !== i))}>
                    Remove
                  </button>
                )}
              </div>
              <div className="cp-bug-row">
                <input
                  value={b.description}
                  onChange={(e) => setBug(i, { description: e.target.value })}
                  placeholder="What's wrong, e.g. “Uses n % 2 == 1 (inverts parity)”"
                />
                <select value={b.fault_type} onChange={(e) => setBug(i, { fault_type: e.target.value })}>
                  {FAULT_TYPES.map((f) => (
                    <option key={f.key} value={f.key}>{f.label}</option>
                  ))}
                </select>
              </div>
              <textarea
                className="code-area"
                rows={4}
                value={b.code}
                onChange={(e) => setBug(i, { code: e.target.value })}
                placeholder={"def is_even(n):\n    return n % 2 == 1"}
                spellCheck={false}
              />
            </div>
          ))}
        </div>
        <button type="button" className="ghost btn-sm cp-add-bug" onClick={() => setBugs((p) => [...p, emptyBug()])}>
          + Add another bug
        </button>
      </div>

      {error && <p className="error">{error}</p>}
      {warnings.length > 0 && (
        <div className="cp-warn">
          <b>Saved, with warnings:</b>
          <ul>{warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
        </div>
      )}

      <div className="cp-form-foot">
        <button type="button" className="ghost" onClick={onCancel}>{warnings.length ? "Close" : "Cancel"}</button>
        <button type="submit" className="exp-run-btn" disabled={busy}>
          {busy ? <span className="busy-label"><span className="spinner" /> Checking…</span> : "Add program"}
        </button>
      </div>
    </form>
  );
}

export default function CustomPrograms({ programs, onChanged }) {
  const [modalOpen, setModalOpen] = useState(false);
  const [busyId, setBusyId] = useState(null);

  async function remove(id) {
    setBusyId(id);
    try {
      await api.deleteCustomProgram(id);
      onChanged();
    } catch (err) {
      alert(err.message);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="cp">
      <div className="cp-top">
        <div className="cp-top-text">
          <h3 className="cp-heading">Your programs</h3>
          <p className="muted cp-lead">
            Add your own program with known bugs, then run a <b>Custom</b> experiment to watch the
            pipeline catch them — a hands-on way to verify the whole thing. Kept separate from the
            built-in benchmark.
          </p>
        </div>
        <button className="ai-btn" onClick={() => setModalOpen(true)}>
          <SparkIcon /> Add a program
        </button>
      </div>

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title="Add a program"
        subtitle="Define a program, its correct reference, some inputs, and the bugs to seed."
        width={820}
      >
        <AddForm
          onCancel={() => setModalOpen(false)}
          onCreated={(_prog, hadWarnings) => {
            onChanged();
            if (!hadWarnings) setModalOpen(false);
          }}
        />
      </Modal>

      {programs.length === 0 ? (
        <p className="muted cp-empty">No custom programs yet.</p>
      ) : (
        <div className="cp-list">
          {programs.map((p) => (
            <div className="cp-card" key={p.id}>
              <div className="cp-card-main">
                <div className="cp-card-title">
                  {p.title} <code className="cp-entry">{p.entrypoint}()</code>
                </div>
                <div className="cp-card-req">{p.requirement}</div>
                <div className="cp-card-bugs">
                  {p.mutants.map((m) => (
                    <span key={m.id} className={`cp-bugchip ${m.kills === false ? "dead" : ""}`} title={m.description || ""}>
                      {m.fault_type ? FAULT_LABEL[m.fault_type] || m.fault_type : "bug"}
                      {m.kills === false && " · never triggers"}
                    </span>
                  ))}
                </div>
              </div>
              <button className="icon-btn danger" title="Delete program" disabled={busyId === p.id} onClick={() => remove(p.id)}>
                {busyId === p.id ? <span className="spinner sm" /> : "✕"}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
