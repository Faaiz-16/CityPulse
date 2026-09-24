import { ChevronDown, Link2 } from "lucide-react";
import { useState } from "react";
import type { Relationship } from "../../types";
import { STRENGTH_META } from "../../utils/status";

function StrengthMeter({ strength }: { strength: Relationship["strength"] }) {
  const meta = STRENGTH_META[strength];
  return (
    <span className="inline-flex items-center gap-1.5" title={`Evidence strength: ${meta.word}`}>
      <span className="flex items-end gap-0.5" aria-hidden>
        {[1, 2, 3].map((b) => (
          <span key={b} className="w-1 rounded-sm" style={{ height: 4 + b * 3, background: b <= meta.bars ? meta.color : "var(--line)" }} />
        ))}
      </span>
      <span className="text-[11px] font-semibold" style={{ color: meta.color }}>
        {meta.word}
      </span>
    </span>
  );
}

export function RelationshipCard({ rel, defaultOpen }: { rel: Relationship; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(!!defaultOpen);
  const weak = rel.strength === "weak";
  return (
    <div className="rounded-xl p-3.5" style={{ border: `1px solid ${weak ? "var(--line)" : "#c084fc66"}`, background: weak ? "var(--panel-2)" : "rgba(192,132,252,0.07)" }}>
      <div className="flex items-center gap-2">
        <Link2 size={15} color={weak ? "var(--muted)" : "#c084fc"} aria-hidden />
        <span className="text-[13.5px] font-semibold">{rel.title}</span>
        <span className="ml-auto">
          <StrengthMeter strength={rel.strength} />
        </span>
      </div>
      <p className="mt-1.5 text-[13px] leading-relaxed">{rel.statement}</p>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="mt-2 flex items-center gap-1 text-[11.5px] font-semibold tracking-wide text-[#d8b4fe] hover:underline"
      >
        WHY THIS FLAG? <ChevronDown size={13} className={open ? "rotate-180 transition-transform" : "transition-transform"} aria-hidden />
      </button>
      {open && (
        <div className="cp-fade-in mt-1.5 rounded-lg p-2.5 text-[12.5px]" style={{ background: "rgba(0,0,0,0.2)" }}>
          <ul className="space-y-1">
            {rel.evidence.map((e) => (
              <li key={e} className="flex gap-1.5">
                <span className="text-[#c084fc]">•</span>
                <span>{e}</span>
              </li>
            ))}
          </ul>
          <div className="mt-2 text-[11px] text-[var(--faint)]">
            Evidence score {rel.score.toFixed(2)} · rolling window {rel.window_minutes} min · rule “{rel.rule_id.replace("_", " → ")}”
          </div>
        </div>
      )}
      <p className="mt-2 text-[11.5px] italic text-[var(--muted)]">{rel.caveat}</p>
    </div>
  );
}
