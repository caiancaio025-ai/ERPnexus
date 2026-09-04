import { useState } from "react";

export function NexusMark({ className = "" }: { className?: string }) {
  const [failed, setFailed] = useState(false);
  return <span className={`nexus-mark ${className}`.trim()} aria-hidden="true">
    {failed ? "N" : <img src="/branding/nexus-logo.png" alt="" onError={() => setFailed(true)} />}
  </span>;
}
