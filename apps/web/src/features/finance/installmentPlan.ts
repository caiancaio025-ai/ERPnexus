/** Divide o total em centavos: nunca perde centavos por arredondamento. */
export function splitInstallmentAmounts(total: number, count: number): string[] {
  const cents = Math.round(total * 100);
  if (!Number.isFinite(total) || !Number.isInteger(count) || count < 2 || count > 60 || cents < count) {
    throw new Error("Confira o total e a quantidade: cada parcela precisa ter pelo menos R$ 0,01.");
  }
  const base = Math.floor(cents / count);
  const remainder = cents % count;
  return Array.from({ length: count }, (_, index) => {
    const itemCents = base + (index < remainder ? 1 : 0);
    return (itemCents / 100).toFixed(2).replace(".", ",");
  });
}

/** Sugere aniversários mensais; 31/jan -> 28/fev -> 31/mar, sem deriva. */
export function monthlyInstallmentDates(firstDueDate: string, count: number): string[] {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(firstDueDate) || !Number.isInteger(count) || count < 2 || count > 60) {
    throw new Error("Informe a data de vencimento inicial e uma quantidade válida de parcelas.");
  }
  const [year, month, day] = firstDueDate.split("-").map(Number);
  if (month < 1 || month > 12 || day < 1 || day > new Date(year, month, 0).getDate()) {
    throw new Error("A data do primeiro vencimento é inválida.");
  }
  return Array.from({ length: count }, (_, index) => {
    const date = new Date(year, month - 1 + index, 1);
    const lastDay = new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate();
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(Math.min(day, lastDay)).padStart(2, "0")}`;
  });
}
