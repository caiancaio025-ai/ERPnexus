export type SenticoTheme = "escuro" | "claro";

const CHAVE_TEMA = "sentico:preferencia-tema:v1";
const EVENTO_TEMA = "sentico:tema-alterado";

export function temaSalvo(): SenticoTheme {
  try { return window.localStorage.getItem(CHAVE_TEMA) === "claro" ? "claro" : "escuro"; }
  catch { return "escuro"; }
}

export function aplicarTema(tema: SenticoTheme): void {
  document.documentElement.setAttribute("data-sentico-theme", tema);
  document.documentElement.style.colorScheme = tema === "claro" ? "light" : "dark";
}

export function escolherTema(tema: SenticoTheme): void {
  try { window.localStorage.setItem(CHAVE_TEMA, tema); } catch { /* Navegação sem armazenamento. */ }
  aplicarTema(tema);
  window.dispatchEvent(new CustomEvent<SenticoTheme>(EVENTO_TEMA, { detail: tema }));
}

export function iniciarTema(): void {
  aplicarTema(temaSalvo());
  window.addEventListener("storage", (event) => {
    if (event.key === CHAVE_TEMA || event.key === null) {
      aplicarTema(temaSalvo());
      window.dispatchEvent(new CustomEvent<SenticoTheme>(EVENTO_TEMA, { detail: temaSalvo() }));
    }
  });
}

export const eventoTema = EVENTO_TEMA;
