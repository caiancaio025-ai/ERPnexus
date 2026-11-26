import { useCallback, useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ChevronDown, Palette, X } from "lucide-react";
import { ThemeSwitcher } from "./ThemeSwitcher";

/** Native popover keeps Escape, outside click and keyboard focus with its trigger. */
export function AppearanceMenu() {
  const id = useId();
  const trigger = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState({ top: 64, right: 16 });

  const placePanel = useCallback(() => {
    const button = trigger.current;
    if (!button) return;
    const rect = button.getBoundingClientRect();
    const height = panel.current?.offsetHeight || 310;
    const width = Math.min(320, window.innerWidth - 24);
    setPosition({
      top: Math.max(12, Math.min(rect.bottom + 10, window.innerHeight - height - 12)),
      right: Math.max(12, Math.min(window.innerWidth - rect.right, window.innerWidth - width - 12)),
    });
  }, []);

  useEffect(() => {
    if (!open) return;
    placePanel();
    panel.current?.querySelector<HTMLButtonElement>('button[aria-pressed="true"]')?.focus({ preventScroll: true });
    window.addEventListener("resize", placePanel);
    window.addEventListener("scroll", placePanel, true);
    return () => {
      window.removeEventListener("resize", placePanel);
      window.removeEventListener("scroll", placePanel, true);
    };
  }, [open, placePanel]);

  return <>
    <button
      ref={trigger}
      type="button"
      className="sentico-appearance-trigger"
      aria-label="Aparência"
      aria-haspopup="dialog"
      aria-expanded={open}
      aria-controls={id}
      popoverTarget={id}
      onClick={placePanel}
      title="Aparência e temas comemorativos"
    >
      <Palette size={18} aria-hidden="true" />
      <span className="sentico-appearance-trigger__label">Aparência</span>
      <ChevronDown size={14} aria-hidden="true" className="sentico-appearance-trigger__chevron" />
    </button>
    {createPortal(<div
      ref={panel}
      id={id}
      popover="auto"
      role="dialog"
      aria-labelledby={`${id}-title`}
      className="sentico-appearance-popover"
      style={position}
      onToggle={(event) => setOpen((event.nativeEvent as ToggleEvent).newState === "open")}
    >
      <div className="sentico-appearance-popover__heading">
        <h2 id={`${id}-title`}>Aparência</h2>
        <button type="button" className="sentico-appearance-close" popoverTarget={id} popoverTargetAction="hide" aria-label="Fechar aparência"><X size={18} aria-hidden="true" /></button>
      </div>
      <ThemeSwitcher titulo="Modo de cor" />
    </div>, document.body)}
  </>;
}
