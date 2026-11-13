import { Check, LoaderCircle, X } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode;
  loading?: boolean;
  success?: boolean;
  error?: boolean;
  icon?: ReactNode;
  variant?: "primary" | "secondary" | "danger" | "ghost";
  intent?: "save" | "delete" | "launch" | "print" | "preview" | "refresh" | "default";
};

export function ActionButton({
  children,
  loading = false,
  success = false,
  error = false,
  icon,
  variant = "primary",
  intent = "default",
  className = "",
  disabled,
  ...props
}: Props) {
  const state = loading ? "loading" : success ? "success" : error ? "error" : "idle";
  const stateIcon = loading ? <LoaderCircle className="lab-spin" size={17} /> : success ? <Check size={17} /> : error ? <X size={17} /> : icon;

  return (
    <button
      {...props}
      disabled={disabled || loading}
      data-state={state}
      data-intent={intent}
      className={`lab-action-button ${variant} ${className}`.trim()}
    >
      <span className="lab-action-button__icon">{stateIcon}</span>
      <span className="lab-action-button__label">{children}</span>
      <span className="lab-action-button__shine" aria-hidden="true" />
    </button>
  );
}
