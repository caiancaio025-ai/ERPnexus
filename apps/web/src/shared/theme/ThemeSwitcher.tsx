import { useEffect, useId, useState } from "react";
import { Moon, Sun, Sparkles } from "lucide-react";
import { escolherTema, eventoTema, temaSalvo, type SenticoTheme } from "./theme";
import { EVENTO_TEMPORADA, lerConfigTemporada, salvarConfigTemporada, nomesTemporadas, temporadaEfetiva, type ConfigTemporada, type EscolhaTemporada } from "./seasonal";
import "./theme-switcher.css";

export function ThemeSwitcher({ compacto = false, titulo = "Aparência" }: { compacto?: boolean; titulo?: string }) {
  const seasonSelectId = useId();
  const [tema, setTema] = useState<SenticoTheme>(temaSalvo);
  const [festas, setFestas] = useState<ConfigTemporada>(lerConfigTemporada);
  useEffect(() => {
    const atualizar = (event: Event) => setTema((event as CustomEvent<SenticoTheme>).detail);
    window.addEventListener(eventoTema, atualizar);
    return () => window.removeEventListener(eventoTema, atualizar);
  }, []);
  useEffect(() => {
    const atualizar = () => setFestas(lerConfigTemporada());
    window.addEventListener(EVENTO_TEMPORADA, atualizar);
    return () => window.removeEventListener(EVENTO_TEMPORADA, atualizar);
  }, []);
  function alterarFestas(atualizacao: Partial<ConfigTemporada>) {
    const proxima = { ...festas, ...atualizacao };
    setFestas(proxima);
    salvarConfigTemporada(proxima);
  }
  return <div className={`sentico-tema ${compacto ? "sentico-tema--compacto" : ""}`} role="group" aria-label="Aparência do SÊNTICO">
    {!compacto && <span className="sentico-tema__titulo">{titulo}</span>}
    <div className="sentico-tema__opcoes">
      <button type="button" onClick={() => escolherTema("claro")} aria-pressed={tema === "claro"} title="Ativar tema claro" aria-label="Tema claro" className={tema === "claro" ? "is-active" : ""}><Sun size={16} aria-hidden="true" /><span>Claro</span></button>
      <button type="button" onClick={() => escolherTema("escuro")} aria-pressed={tema === "escuro"} title="Ativar tema escuro" aria-label="Tema escuro" className={tema === "escuro" ? "is-active" : ""}><Moon size={16} aria-hidden="true" /><span>Escuro</span></button>
    </div>
    {compacto ? (
      <button type="button" className="sentico-tema__temporada-compacto" aria-label={festas.escolha === "desativado" ? "Ativar temas comemorativos automáticos" : "Desativar temas comemorativos"} aria-pressed={festas.escolha !== "desativado"} title={festas.escolha === "desativado" ? "Ativar temas comemorativos" : "Desativar temas comemorativos"} onClick={() => alterarFestas({ escolha: festas.escolha === "desativado" ? "automatico" : "desativado" })}>
        <Sparkles size={18} aria-hidden="true" />
      </button>
    ) : (
      <div className="sentico-tema__festas">
        <label htmlFor={seasonSelectId}>Temas comemorativos</label>
        <select id={seasonSelectId} value={festas.escolha} onChange={(evento) => alterarFestas({ escolha: evento.target.value as EscolhaTemporada })}>
          <option value="automatico">Automático pela data</option>
          <option value="desativado">Desativado</option>
          {(Object.entries(nomesTemporadas) as Array<[EscolhaTemporada, string]>).map(([valor, nome]) => <option key={valor} value={valor}>{nome} (prévia)</option>)}
        </select>
        <label className="sentico-tema__animacoes">
          <input type="checkbox" checked={festas.animacoes} onChange={(evento) => alterarFestas({ animacoes: evento.target.checked })} />
          <span>Animar decoração</span>
        </label>
        {temporadaEfetiva(festas) && <span className="sentico-tema__ativo">Em destaque: {nomesTemporadas[temporadaEfetiva(festas)!]}</span>}
      </div>
    )}
  </div>;
}
