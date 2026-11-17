/** Traduções de dados legados e códigos internos, sem alterar os valores salvos no banco. */
export const statusEmPortugues: Record<string, string> = {
  received: "Recebido", awaiting_analysis: "Aguardando análise", under_analysis: "Analisado",
  in_analysis: "Analisado", awaiting_quote: "Aguardando orçamento", quote_sent: "Orçamento enviado",
  awaiting_approval: "Aguardando aprovação", approved: "Aprovado", rejected: "Reprovado",
  awaiting_parts: "Aguardando peças", in_repair: "Em manutenção", in_testing: "Em testes",
  completed: "Concluído", awaiting_pickup: "Aguardando retirada", delivered: "Entregue",
  warranty: "Garantia", invoiced: "Faturado", cancelled: "Cancelado", no_repair: "Sem conserto",
  pending: "Pendente", open: "Aberto", closed: "Fechado", issued: "Emitido",
  draft: "Rascunho", in_progress: "Em andamento", due_soon: "Prazo próximo", overdue: "Atrasado",
  ready: "Pronto", quotation: "Orçamento", quote: "Orçamento", purchase: "Compra",
};

export function traduzirStatus(valor: string | null | undefined): string {
  if (!valor) return "Não informado";
  return statusEmPortugues[valor.toLowerCase()] ?? valor;
}

export function formatarNumeroOS(numero: string | number | null | undefined): string {
  if (numero === undefined || numero === null) return "—";
  const semPrefixo = String(numero).trim().replace(/^OS[\s-]*/i, "");
  return semPrefixo ? `OS ${semPrefixo}` : "OS";
}

/** Normaliza apenas termos próprios do sistema; não traduz nomes de produtos ou textos digitados. */
export function textoEmPortugues(texto: string | null | undefined): string {
  if (!texto) return "";
  let saida = texto.replace(/\bOS\s+OS[\s-]+/gi, "OS ");
  // Compatibilidade com notificações antigas armazenadas no banco.
  saida = saida.replace(/\bEm\s+[Aa]nálise\b/gi, "Analisado");
  saida = saida.replace(/\b(Warranty|Awaiting[ _-]Quote|Awaiting[ _-]Approval|Under[ _-]Analysis|In[ _-]Repair|In[ _-]Testing|Awaiting[ _-]Pickup|In[ _-]Progress|No[ _-]Repair|Quote[ _-]Sent|Awaiting[ _-]Parts|Received|Approved|Rejected|Delivered|Invoiced|Cancelled|Completed|Pending|Draft|Issued|Overdue)\b/gi, (match) => {
    const codigo = match.toLowerCase().replace(/[\s-]+/g, "_");
    return statusEmPortugues[codigo] ?? match;
  });
  return saida.replace(/\b(received|awaiting_analysis|under_analysis|in_analysis|awaiting_quote|quote_sent|awaiting_approval|approved|rejected|awaiting_parts|in_repair|in_testing|completed|awaiting_pickup|delivered|warranty|invoiced|cancelled|no_repair|pending|draft|in_progress)\b/gi,
    (match) => statusEmPortugues[match.toLowerCase()] ?? match);
}

/** Retorna erros comuns de integração em português, mantendo mensagens específicas intactas. */
export function mensagemSistemaEmPortugues(texto: string): string {
  const msg = texto.trim();
  const comuns: Record<string, string> = {
    "Not Found": "Registro não encontrado.", "Internal Server Error": "Erro interno do servidor.",
    "Forbidden": "Você não tem permissão para acessar este recurso.",
    "Unauthorized": "Sua sessão não está autorizada.",
    "Field required": "Campo obrigatório.",
    "Input should be a valid integer": "Informe um número inteiro válido.",
    "Input should be a valid number": "Informe um número válido.",
    "Input should be a valid string": "Informe um texto válido.",
    "Input should be a valid date": "Informe uma data válida.",
  };
  if (comuns[msg]) return comuns[msg];
  const limite = msg.match(/^String should have at most (\d+) characters$/i);
  if (limite) return `O texto deve ter no máximo ${limite[1]} caracteres.`;
  const minimo = msg.match(/^String should have at least (\d+) characters$/i);
  if (minimo) return `O texto deve ter pelo menos ${minimo[1]} caracteres.`;
  return msg;
}
