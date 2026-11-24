import type { CompanyCode, Customer } from "../types";

/** Busca local sobre os clientes já cadastrados, sem criar/alterar registros. */
export function normalizeCustomerSearch(value: string): string {
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("pt-BR").trim();
}

export function customerDisplayName(customer: Customer): string {
  return customer.trade_name?.trim() || customer.legal_name;
}

export function searchCustomers(
  customers: Customer[],
  companyCode: CompanyCode,
  query: string,
  selectedId: string,
  limit = 12,
): Customer[] {
  const term = normalizeCustomerSearch(query);
  const currentId = Number(selectedId);
  return customers
    .filter((customer) => customer.company_code === companyCode && (customer.is_active || customer.id === currentId))
    .map((customer) => {
      const primary = normalizeCustomerSearch(customerDisplayName(customer));
      const legal = normalizeCustomerSearch(customer.legal_name);
      const document = (customer.document || "").replace(/\D/g, "");
      const digits = query.replace(/\D/g, "");
      const matching = !term || primary.includes(term) || legal.includes(term) || (digits.length > 0 && document.includes(digits));
      const rank = primary.startsWith(term) ? 0 : legal.startsWith(term) ? 1 : primary.includes(term) ? 2 : legal.includes(term) ? 3 : 4;
      return { customer, matching, rank };
    })
    .filter((entry) => entry.matching)
    .sort((a, b) => a.rank - b.rank || customerDisplayName(a.customer).localeCompare(customerDisplayName(b.customer), "pt-BR"))
    .slice(0, limit)
    .map((entry) => entry.customer);
}
