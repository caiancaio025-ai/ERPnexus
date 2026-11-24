import { useEffect, useState, type CSSProperties } from "react";
import { EVENTO_TEMPORADA, lerConfigTemporada, temporadaEfetiva, type Temporada } from "./seasonal";

const NEVE = Array.from({ length: 25 }, (_, indice) => ({
  x: (indice * 41 + 11) % 98, delay: -((indice * 17) % 24),
  duracao: 13 + ((indice * 7) % 15), tamanho: 3 + ((indice * 13) % 5),
}));
const CONFETES = Array.from({ length: 34 }, (_, indice) => ({
  x: (indice * 47 + 9) % 98,
  delay: -((indice * 11) % 17), duracao: 10 + ((indice * 5) % 9),
  cor: ["#f3c14c", "#58cbea", "#d878ec", "#79dfa7", "#fc6f9d"][indice % 5],
}));
const LAMPADAS = ["#eb6a79", "#f6c45e", "#75cf9d", "#80c8f3", "#c79ce7", "#f6c45e", "#ed728b", "#8bd5e8", "#79d5a6", "#f3c565", "#d6a7ed", "#ed8da5"];
const FOGOS = Array.from({ length: 9 }, (_, indice) => ({
  x: 12 + ((indice * 23) % 76), y: 12 + ((indice * 17) % 48),
  delay: `${indice * -.61}s`, duracao: `${3.8 + (indice % 3) * .55}s`,
  cor: ["#ffcc70", "#87d6ff", "#fca8c8", "#a5ebc2", "#d9b0ff"][indice % 5],
}));

const ORNAMENTOS: Record<Temporada, string[]> = {
  natal: ["🎄", "✨", "🎁", "❄️", "🎀", "🎅"],
  ano_novo: ["🎆", "✨", "🥂", "🎇", "🍾", "✨"],
  carnaval: ["🎭", "☂️", "🎉", "🎊", "☂️", "🎭"],
  pascoa: ["🌸", "🥚", "🐇", "🌼", "🥚", "🌸"],
  junho: ["🌽", "🌻", "🎏", "🔥", "🌻", "🌽"],
  halloween: ["🎃", "🕸️", "🦇", "💀", "🍬", "👻", "🍭", "🎃"],
};

/** Camada apenas decorativa, não captura toques nem substitui páginas do ERP. */
export function SeasonalDecorations() {
  const [temporada, setTemporada] = useState<Temporada | null>(() => temporadaEfetiva(lerConfigTemporada()));
  const [animacoes, setAnimacoes] = useState(() => lerConfigTemporada().animacoes);

  useEffect(() => {
    const atualizar = () => {
      const config = lerConfigTemporada();
      setTemporada(temporadaEfetiva(config));
      setAnimacoes(config.animacoes);
    };
    window.addEventListener(EVENTO_TEMPORADA, atualizar);
    return () => window.removeEventListener(EVENTO_TEMPORADA, atualizar);
  }, []);

  if (!temporada) return null;
  return (
    <div className={`sentico-festas sentico-festas--${temporada}${animacoes ? " is-animated" : ""}`} aria-hidden="true">
      <div className="sentico-festas__ambient" />
      <div className="sentico-festas__friso">
        {ORNAMENTOS[temporada].map((simbolo, index) => <span key={index} style={{ "--ornament-delay": `${index * -.53}s` } as CSSProperties}>{simbolo}</span>)}
      </div>
      {(temporada === "carnaval" || temporada === "halloween" || temporada === "ano_novo") && <div className="sentico-festas__cantos">
        <span className="sentico-festas__canto sentico-festas__canto--esquerdo">{temporada === "halloween" ? "🎃💀🍬" : temporada === "carnaval" ? "☂️🎭🎊" : "🥂✨"}</span>
        <span className="sentico-festas__canto sentico-festas__canto--direito">{temporada === "halloween" ? "🍭🦴🎃" : temporada === "carnaval" ? "🎉🎭☂️" : "🎇🍾"}</span>
      </div>}
      {temporada === "ano_novo" && <div className="sentico-festas__fireworks">{FOGOS.map((fogo, indice) => <span key={indice} className="sentico-festas__burst" style={{ left: `${fogo.x}%`, top: `${fogo.y}%`, animationDelay: fogo.delay, animationDuration: fogo.duracao, "--burst-color": fogo.cor } as CSSProperties}><i /><i /><i /><i /><i /><i /><i /><i /></span>)}</div>}
      {temporada === "natal" && <>
        <div className="sentico-festas__lights">{LAMPADAS.map((cor, index) => <span key={index} className="sentico-festas__bulb" style={{ "--bulb-color": cor, "--phase": `${index * -.28}s` } as CSSProperties} />)}</div>
        <div className="sentico-festas__particles">{NEVE.map((particula, indice) => <i key={indice} className="sentico-festas__snow" style={{ left: `${particula.x}%`, width: particula.tamanho, height: particula.tamanho, animationDelay: `${particula.delay}s`, animationDuration: `${particula.duracao}s` }} />)}</div>
      </>}
      {temporada === "carnaval" && <>
        <div className="sentico-festas__fitas" />
        <div className="sentico-festas__particles">{CONFETES.map((particula, indice) => <i key={indice} className="sentico-festas__confetti" style={{ left: `${particula.x}%`, backgroundColor: particula.cor, animationDelay: `${particula.delay}s`, animationDuration: `${particula.duracao}s`, "--confetti-angle": `${indice * 23}deg` } as CSSProperties} />)}</div>
      </>}
      {temporada === "junho" && <div className="sentico-festas__bunting">{LAMPADAS.map((cor, indice) => <span key={indice} style={{ "--bulb-color": cor } as CSSProperties} />)}</div>}
      {temporada === "pascoa" && <div className="sentico-festas__petalas">{CONFETES.slice(0, 12).map((flor, indice) => <span key={indice} style={{ left: `${flor.x}%`, animationDelay: `${flor.delay}s`, animationDuration: `${flor.duracao + 4}s` }}>🌸</span>)}</div>}
      {temporada === "halloween" && <>
        <div className="sentico-festas__teias"><span>🕸️</span><span>🕸️</span></div>
        <div className="sentico-festas__morcegos"><span>🦇</span><span>🦇</span><span>🦇</span></div>
      </>}
    </div>
  );
}
