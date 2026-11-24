import { useEffect, useState } from "react";
import {
  EVENTO_TEMPORADA,
  lerConfigTemporada,
  temporadaEfetiva,
  type Temporada,
} from "./seasonal";

type Conteudo = { etiqueta: string; titulo: string; descricao: string; simbolo: string };

function tituloAnoNovo(data = new Date()) {
  // Em novembro/dezembro anuncia a virada seguinte. Em janeiro mostra o ano corrente.
  const ano = data.getMonth() >= 10 ? data.getFullYear() + 1 : data.getFullYear();
  return `Feliz ${ano}!`;
}

function conteudoTemporada(temporada: Temporada): Conteudo {
  switch (temporada) {
    case "ano_novo":
      return { etiqueta: "JANEIRO · ANO-NOVO", titulo: tituloAnoNovo(), descricao: "Um novo ano de projetos, conquistas e bons resultados.", simbolo: "🥂" };
    case "carnaval":
      return { etiqueta: "FEVEREIRO · CARNAVAL", titulo: "É tempo de Carnaval!", descricao: "A energia da nossa equipe também entra no ritmo da festa.", simbolo: "🎭" };
    case "pascoa":
      return { etiqueta: "PÁSCOA", titulo: "Feliz Páscoa!", descricao: "Renovação, esperança e novas oportunidades para a equipe.", simbolo: "🌷" };
    case "junho":
      return { etiqueta: "JUNHO · SÃO JOÃO", titulo: "Viva São João!", descricao: "Tradição, alegria e trabalho bem-feito, juntos.", simbolo: "🌻" };
    case "halloween":
      return { etiqueta: "OUTUBRO · HALLOWEEN", titulo: "Halloween no SÊNTICO!", descricao: "Doces, abóboras e criatividade para vencer os desafios.", simbolo: "🎃" };
    case "natal":
      return { etiqueta: "NOVEMBRO E DEZEMBRO · NATAL", titulo: "Feliz Natal!", descricao: "Que esta temporada traga união, saúde e conquistas.", simbolo: "🎄" };
  }
}

/** Faixa temática real do painel: dados e botões continuam componentes funcionais. */
export function SeasonalDashboardBanner() {
  const [temporada, setTemporada] = useState<Temporada | null>(() => temporadaEfetiva(lerConfigTemporada()));
  useEffect(() => {
    const atualizar = () => setTemporada(temporadaEfetiva(lerConfigTemporada()));
    window.addEventListener(EVENTO_TEMPORADA, atualizar);
    return () => window.removeEventListener(EVENTO_TEMPORADA, atualizar);
  }, []);

  if (!temporada) return null;
  const conteudo = conteudoTemporada(temporada);
  return (
    <section className={`sentico-banner-festa sentico-banner-festa--${temporada}`} aria-label={`Decoração comemorativa: ${conteudo.titulo}`}>
      <div className="sentico-banner-festa__texto">
        <span className="sentico-banner-festa__etiqueta">{conteudo.simbolo} {conteudo.etiqueta}</span>
        <h2>{conteudo.titulo}</h2>
        <p>{conteudo.descricao}</p>
      </div>
      <img className="sentico-banner-festa__arte" src={`/temas-comemorativos/${temporada}.webp`} alt="" loading="lazy" decoding="async" />
      <div className="sentico-banner-festa__brilho" aria-hidden="true" />
    </section>
  );
}
