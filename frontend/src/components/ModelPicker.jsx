import { useEffect, useState } from "react";
import { api, getModelSelection, setModelSelection } from "../api/client";

export const PROVIDER_LABEL = {
  gemini: "Google Gemini",
  groq: "Groq",
  openrouter: "OpenRouter",
  anthropic: "Anthropic",
  ollama: "Ollama",
};

// Dropdown to choose which free model powers agent runs. The selection persists
// in localStorage (via the api client) and is attached to each generate / run /
// experiment call, so switching models needs no file edits. Shared by the
// requirement pipeline page and the experiments runner.
export default function ModelPicker({ onProviderChange }) {
  const [catalog, setCatalog] = useState(null);
  const [sel, setSel] = useState(getModelSelection());

  useEffect(() => {
    api
      .listModels()
      .then((data) => {
        setCatalog(data);
        let current = getModelSelection();
        if (!current) {
          const d = data.default;
          const match = data.models.find(
            (m) => m.provider === d.provider && m.model === d.model && m.ready
          );
          const first = match || data.models.find((m) => m.ready);
          if (first) {
            current = { provider: first.provider, model: first.model };
            setModelSelection(current);
            setSel(current);
          }
        }
        if (current) onProviderChange?.(current.provider);
      })
      .catch(() => {});
  }, [onProviderChange]);

  if (!catalog) return null;

  const current = sel || catalog.default;
  const value = `${current.provider}::${current.model}`;
  const groups = {};
  for (const m of catalog.models) (groups[m.provider] ||= []).push(m);

  function onChange(e) {
    const [provider, model] = e.target.value.split("::");
    setModelSelection({ provider, model });
    setSel({ provider, model });
    onProviderChange?.(provider);
  }

  return (
    <label className="model-picker" title="Which AI model runs every agent">
      <span className="mp-label">AI model</span>
      <select value={value} onChange={onChange}>
        {Object.entries(groups).map(([prov, items]) => (
          <optgroup key={prov} label={PROVIDER_LABEL[prov] || prov}>
            {items.map((m) => (
              <option
                key={`${m.provider}::${m.model}`}
                value={`${m.provider}::${m.model}`}
                disabled={!m.ready}
              >
                {m.label}
                {m.ready ? "" : " — add key"}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
    </label>
  );
}
