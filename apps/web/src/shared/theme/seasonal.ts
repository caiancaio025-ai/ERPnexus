/** Aparência sazonal: exclusivamente visual, sem modificar temas ou permissões. */
export type Temporada = "ano_novo" | "carnaval" | "pascoa" | "junho" | "halloween" | "natal";
export type EscolhaTemporada = "automatico" | "desativado" | Temporada;
export type ConfigTemporada = { escolha: EscolhaTemporada; animacoes: boolean };

const CHAVE = "sentico:temporada:v1";
export const EVENTO_TEMPORADA = "sentico:temporada-alterada";
const OPCOES: EscolhaTemporada[] = ["automatico", "desativado", "ano_novo", "carnaval", "pascoa", "junho", "halloween", "natal"];

/** Algoritmo gregoriano de Meeus/Jones/Butcher para a Páscoa (1583–4099). */
export function dataPascoa(ano: number): { mes: number; dia: number } {
  const a = ano % 19;
  const b = Math.floor(ano / 100);
  const c = ano % 100;
  const d = Math.floor(b / 4);
  const e = b % 4;
  const f = Math.floor((b + 8) / 25);
  const g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30;
  const i = Math.floor(c / 4);
  const k = c % 4;
  const l = (32 + 2 * e + 2 * i - h - k + 7 * 30) % 7;
  const m = Math.floor((a + 11 * h + 22 * l) / 451);
  const n = h + l - 7 * m + 114;
  return { mes: Math.floor(n / 31), dia: (n % 31) + 1 };
}

export function temporadaNaData(data: Date): Temporada | null {
  const mes = data.getMonth() + 1;
  if (mes === 1) return "ano_novo";
  if (mes === 11 || mes === 12) return "natal";
  if (mes === 10) return "halloween";
  if (mes === 6) return "junho";
  if (mes === 2) return "carnaval"; // Opção pedida: tema carnavalesco durante fevereiro.
  if (mes === dataPascoa(data.getFullYear()).mes) return "pascoa";
  return null;
}

export function temporadaEfetiva(config: ConfigTemporada, data = new Date()): Temporada | null {
  if (config.escolha === "desativado") return null;
  if (config.escolha === "automatico") return temporadaNaData(data);
  return config.escolha;
}

export function lerConfigTemporada(): ConfigTemporada {
  try {
    const texto = window.localStorage.getItem(CHAVE);
    if (texto) {
      const valor = JSON.parse(texto) as Partial<ConfigTemporada>;
      if (valor && OPCOES.includes(valor.escolha as EscolhaTemporada)) {
        return { escolha: valor.escolha as EscolhaTemporada, animacoes: valor.animacoes !== false };
      }
    }
  } catch { /* Navegação particular ou armazenamento indisponível. */ }
  return { escolha: "automatico", animacoes: true };
}

export function aplicarConfigTemporada(config: ConfigTemporada, data = new Date()): void {
  const elemento = document.documentElement;
  const ativa = temporadaEfetiva(config, data);
  if (ativa) elemento.dataset.senticoTemporada = ativa;
  else delete elemento.dataset.senticoTemporada;
  elemento.dataset.senticoAnimacoes = config.animacoes ? "ligadas" : "desligadas";
}

export function salvarConfigTemporada(config: ConfigTemporada): void {
  const normalizada: ConfigTemporada = {
    escolha: OPCOES.includes(config.escolha) ? config.escolha : "automatico",
    animacoes: Boolean(config.animacoes),
  };
  try { window.localStorage.setItem(CHAVE, JSON.stringify(normalizada)); } catch { /* Somente preferência visual. */ }
  aplicarConfigTemporada(normalizada);
  window.dispatchEvent(new CustomEvent<ConfigTemporada>(EVENTO_TEMPORADA, { detail: normalizada }));
}

let iniciado = false;
export function iniciarTemporadas(): void {
  if (iniciado) return;
  iniciado = true;
  aplicarConfigTemporada(lerConfigTemporada());
  const sincronizar = () => {
    const config = lerConfigTemporada();
    aplicarConfigTemporada(config);
    window.dispatchEvent(new CustomEvent<ConfigTemporada>(EVENTO_TEMPORADA, { detail: config }));
  };
  // Preferências de outras abas e passagem de mês sem recarregar a página.
  window.addEventListener("storage", (evento) => { if (evento.key === CHAVE || evento.key === null) sincronizar(); });
  window.addEventListener("focus", sincronizar);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) sincronizar(); });
  window.setInterval(() => { if (!document.hidden) sincronizar(); }, 3_600_000);
}

export const nomesTemporadas: Record<Temporada, string> = {
  ano_novo: "Ano-Novo", carnaval: "Carnaval", pascoa: "Páscoa", junho: "São João", halloween: "Halloween", natal: "Natal",
};
