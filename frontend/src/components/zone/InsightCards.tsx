import { ChevronDown, Link2, OctagonAlert, ShieldAlert } from "lucide-react";
import { useState } from "react";
import type { Relationship, RiskInsight } from "../../types";
import { STRENGTH_META } from "../../utils/status";

export function RiskCard({ risk }: { risk: RiskInsight }) {
  const high = risk.level === "high";
  const color = high ? "var(--bad)" : "var(--warn)";
  const Icon = high ? OctagonAlert : ShieldAlert;
  return (
    <div className="rounded-xl p-3.5" style={{ border: `1px solid ${color}`, background: `color-mix(in srgb, ${color} 9%, transparent)` }}>
      <div className="flex items-center gap-2">
        <Icon size={16} color={color} aria-hidden />
        <span className="label-caps" style={{ color }}>
          {risk.kind === "potential_disruption" ? "Possible impact" : "Early warning"}
        </span>
      </div>
      <p className="mt-1 text-[15px] font-semibold leading-snug">{risk.headline}</p>
      <ul className="mt-2 space-y-0.5 text-[12.5px] text-[var(--muted)]">
        {risk.evidence.map((e) => (
          <li key={e}>• {e}</li>
        ))}
      </ul>
      <p className="mt-2 rounded-lg px-2.5 py-1.5 text-[12.5px]" style={{ background: "var(--panel-2)" }}>
        <span className="font-semibold">For residents: </span>
        {risk.resident_advice}
      </p>
    </div>
  );
}

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
