type SenticoMarkProps = {
  className?: string;
  compact?: boolean;
};

/** Exibe os arquivos oficiais da marca, sem recriar o símbolo em SVG/CSS. */
export function SenticoMark({ className = "", compact = false }: SenticoMarkProps) {
  return (
    <span className={`sentico-mark ${compact ? "sentico-mark--compact" : "sentico-mark--full"} ${className}`.trim()} aria-hidden="true">
      <img
        src={compact ? "/branding/sentico-simbolo.png" : "/branding/sentico-logo-horizontal.png"}
        alt=""
        decoding="async"
      />
    </span>
  );
}
