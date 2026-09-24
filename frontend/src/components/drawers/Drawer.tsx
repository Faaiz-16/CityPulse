import { X } from "lucide-react";
import { useEffect, useRef } from "react";

interface Props {
  side: "left" | "right";
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  icon?: React.ReactNode;
  onClose: () => void;
  children: React.ReactNode;
  width?: string;
}

/** Slide-in panel over the map. Closed by default everywhere; Esc closes it. */
export function Drawer({ side, title, subtitle, icon, onClose, children, width = "w-[400px]" }: Props) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <aside
      role="dialog"
      aria-label={typeof title === "string" ? title : undefined}
      className={`glass pointer-events-auto flex max-h-full min-h-0 flex-col overflow-hidden ${width} max-w-full ${side === "left" ? "cp-slide-left" : "cp-slide-right"}`}
    >
      <header className="flex items-start gap-2.5 border-b px-4 py-3" style={{ borderColor: "var(--line)" }}>
        {icon}
        <div className="min-w-0 flex-1">
          <h2 className="text-[15px] font-semibold leading-tight">{title}</h2>
          {subtitle && <p className="mt-0.5 text-[11.5px] text-[var(--muted)]">{subtitle}</p>}
        </div>
        <button ref={closeRef} type="button" onClick={onClose} aria-label="Close"
          className="rounded-md p-1 text-[var(--muted)] hover:bg-white/5 hover:text-[var(--text)]">
          <X size={17} />
        </button>
      </header>
      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto">{children}</div>
    </aside>
  );
}
