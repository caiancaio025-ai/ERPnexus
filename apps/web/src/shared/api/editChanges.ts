/** Only changed form fields are sent, so refreshes cannot overwrite other work. */
export function changedFields<T extends Record<string, unknown>>(baseline: T, current: T): Partial<T> {
  return Object.fromEntries(Object.entries(current).filter(([key, value]) => JSON.stringify(value) !== JSON.stringify(baseline[key]))) as Partial<T>;
}

export function conflictingFields<T extends Record<string, unknown>>(baseline: T, current: T, latest: T): Array<keyof T> {
  return Object.keys(changedFields(baseline, current)).filter((key) =>
    JSON.stringify(latest[key]) !== JSON.stringify(baseline[key]) &&
    JSON.stringify(latest[key]) !== JSON.stringify(current[key])
  ) as Array<keyof T>;
}

/** Reapply only the unsaved fields over a fresh response (including its version). */
export function mergeUnsaved<T extends Record<string, unknown>>(baseline: T, current: T, latest: T): T {
  return { ...latest, ...changedFields(baseline, current) };
}

const fieldLabels: Record<string, string> = {
  company_code: "empresa", customer_id: "cliente", customer_name: "nome do cliente", serial_number: "número de série",
  manufacturer: "fabricante", model: "modelo", equipment_type: "equipamento", power: "potência", voltage: "tensão",
  storage_location: "localização", assigned_technician_id: "técnico responsável", priority: "prioridade",
  reported_defect: "defeito informado", entry_condition: "condição de entrada", accessories_received: "acessórios recebidos",
  parts_cost: "custo de peças", quoted_value: "valor orçado", approved_value: "valor aprovado",
  internal_notes: "observações internas", customer_notes: "observações do cliente",
  entry_invoice: "NF de entrada", exit_invoice: "NF de saída", entry_invoice_access_key: "chave NF de entrada", exit_invoice_access_key: "chave NF de saída",
};

export class ConcurrentEditError extends Error {
  readonly fields: string[];
  constructor(fields: string[]) {
    super(`Esta O.S. foi alterada por outra operação nos mesmos campos: ${fields.map((field) => fieldLabels[field] ?? field.replace(/_/g, " ")).join(", ")}. Suas alterações continuam na tela. Use Recarregar O.S. para consultar os dados atuais; você poderá confirmar se deseja descartar as alterações locais.`);
    this.name = "ConcurrentEditError";
    this.fields = fields;
  }
}

/** A rejected version can be rebased once, only if none of our fields conflict. */
export async function saveVersionedChanges<T extends Record<string, unknown>, R extends { version: number }>(
  baseline: T,
  current: T,
  version: number,
  port: { save: (patch: Partial<T>, version: number) => Promise<R>; read: () => Promise<R>; snapshot: (record: R) => T },
): Promise<R> {
  const patch = changedFields(baseline, current);
  try { return await port.save(patch, version); }
  catch (cause) {
    if (!cause || typeof cause !== "object" || !("status" in cause) || cause.status !== 409) throw cause;
    const latest = await port.read();
    const conflicts = conflictingFields(baseline, current, port.snapshot(latest));
    if (conflicts.length) throw new ConcurrentEditError(conflicts.map(String));
    return port.save(patch, latest.version);
  }
}
