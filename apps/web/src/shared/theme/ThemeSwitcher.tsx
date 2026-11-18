import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { escolherTema, eventoTema, temaSalvo, type SenticoTheme } from "./theme";
import "./theme-switcher.css";

export function ThemeSwitcher({ compacto = false }: { compacto?: boolean }) {
  const [tema, setTema] = useState<SenticoTheme>(temaSalvo);
  useEffect(() => {
    const atualizar = (event: Event) => setTema((event as CustomEvent<SenticoTheme>).detail);
    window.addEventListener(eventoTema, atualizar);
    return () => window.removeEventListener(eventoTema, atualizar);
  }, []);
  return <div className={`sentico-tema ${compacto ? "sentico-tema--compacto" : ""}`} role="group" aria-label="Aparência do SÊNTICO">
    {!compacto && <span className="sentico-tema__titulo">Aparência</span>}
    <div className="sentico-tema__opcoes">
      <button type="button" onClick={() => escolherTema("claro")} aria-pressed={tema === "claro"} title="Ativar tema claro" aria-label="Tema claro" className={tema === "claro" ? "is-active" : ""}><Sun size={16} aria-hidden="true" /><span>Claro</span></button>
      <button type="button" onClick={() => escolherTema("escuro")} aria-pressed={tema === "escuro"} title="Ativar tema escuro" aria-label="Tema escuro" className={tema === "escuro" ? "is-active" : ""}><Moon size={16} aria-hidden="true" /><span>Escuro</span></button>
    </div>
  </div>;
}
