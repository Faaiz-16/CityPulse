import type { ZoneStatus } from "../../types";
import { STATUS_META } from "../../utils/status";

interface Props {
  status: ZoneStatus;
  label?: string;
  size?: "sm" | "md" | "lg";
}

/** Colour + icon + word, so status never depends on colour alone. */
export function StatusBadge({ status, label, size = "md" }: Props) {
  const meta = STATUS_META[status];
  const Icon = meta.icon;
  const sizes = {
    sm: "text-[11px] px-2 py-0.5 gap-1",
    md: "text-xs px-2.5 py-1 gap-1.5",
    lg: "text-sm px-3 py-1.5 gap-2",
  }[size];
  return (
    <span
      className={`inline-flex items-center rounded-full font-semibold whitespace-nowrap ${sizes}`}
      style={{ background: meta.soft, color: meta.color, border: `1px solid ${meta.color}40` }}
    >
      <Icon aria-hidden size={size === "lg" ? 16 : 13} strokeWidth={2.4} />
      {label ?? meta.word}
    </span>
  );
}
