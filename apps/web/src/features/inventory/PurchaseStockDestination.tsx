import { stockIdFromSearch } from "./stockCode";
import { useEffect, useMemo, useState } from "react";
import { apiClient } from "../../shared/api/apiClient";
import { InventoryItemFields, emptyInventoryItemCatalog, type InventoryItemCatalog, type InventoryItemFieldValue } from "./InventoryItemFields";
import "./purchaseStockDestination.css";

export type InventoryReceiptDetails = { subtype_id: number | null; manufacturer: string | null; model: string | null; unit: string; slot_id: number | null; notes: string | null };
export const emptyInventoryReceiptDetails: InventoryReceiptDetails = { subtype_id: null, manufacturer: null, model: null, unit: "UN", slot_id: null, notes: null };
export type StockDestination = {
  inventory_destination: "" | "existing" | "new";
  inventory_item_id: string;
  inventory_name: string;
  inventory_mode: "bulk" | "serialized";
  inventory_serial: string;
  inventory_category: string;
  inventory_format_id: string;
  inventory_details: InventoryReceiptDetails;
};
export const emptyStockDestination: StockDestination = {
  inventory_destination: "", inventory_item_id: "", inventory_name: "",
  inventory_mode: "bulk", inventory_serial: "", inventory_category: "componentes", inventory_format_id: "", inventory_details: emptyInventoryReceiptDetails,
};
export const individualReceiptLimit = 1000;
export const individualReceiptLimitMessage = "O controle individual aceita até 1.000 unidades por recebimento. Para uma quantidade maior, use controle por quantidade ou divida a compra em solicitações menores.";
export function stockDestinationPayload(value: StockDestination, _quantity: number) {
  return {
    inventory_destination: value.inventory_destination || null,
    inventory_item_id: value.inventory_destination === "existing" ? Number(value.inventory_item_id) || null : null,
    inventory_name: value.inventory_destination === "new" ? value.inventory_name.trim() || null : null,
    inventory_mode: value.inventory_destination === "new" ? value.inventory_mode : null,
    inventory_serial: value.inventory_destination === "new" && value.inventory_mode === "serialized" ? value.inventory_serial.trim() || null : null,
    inventory_category: value.inventory_destination === "new" ? value.inventory_category : null,
    inventory_format_id: value.inventory_destination === "new" && value.inventory_format_id ? Number(value.inventory_format_id) : null,
    inventory_details: value.inventory_destination === "new" ? {
      ...value.inventory_details, unit: value.inventory_details.unit.trim() || "UN",
      manufacturer: value.inventory_details.manufacturer?.trim() || null, model: value.inventory_details.model?.trim() || null,
      notes: value.inventory_details.notes?.trim() || null,
    } : null,
  };
}
export function stockDestinationFromRequest(item: {
  inventory_destination?: "new" | "existing" | null; inventory_item_id?: number | null;
  inventory_name?: string | null; inventory_mode?: "bulk" | "serialized" | null;
  inventory_serial?: string | null; inventory_category?: string | null; inventory_format_id?: number | null;
  inventory_details?: Partial<InventoryReceiptDetails> | null;
}): StockDestination {
  return {
    inventory_destination: item.inventory_destination || "",
    inventory_item_id: item.inventory_item_id ? String(item.inventory_item_id) : "",
    inventory_name: item.inventory_name || "",
    inventory_mode: item.inventory_mode || "bulk",
    inventory_serial: item.inventory_serial || "",
    inventory_category: item.inventory_category || "componentes",
    inventory_format_id: item.inventory_format_id ? String(item.inventory_format_id) : "",
    inventory_details: { ...emptyInventoryReceiptDetails, ...item.inventory_details, unit: item.inventory_details?.unit || "UN" },
  };
}

type Item = { id: number; stock_code: string; name: string; quantity: number; mode: "bulk" | "serialized"; manufacturer_serial: string | null };

export function StockReceiptSummary({ quantity, mode }: { quantity: number; mode: "bulk" | "serialized" }) {
  if (!Number.isInteger(quantity) || quantity < 1) return null;
  const count = quantity.toLocaleString("pt-BR");
  return <div className="purchase-stock-receipt-summary" role="status">
    <strong>{mode === "serialized"
      ? `${count} ${quantity === 1 ? "unidade · 1 código próprio" : "unidades · um código para cada unidade"}`
      : `${count} ${quantity === 1 ? "unidade" : "unidades"} · um cadastro com saldo`}</strong>
    <span>{mode === "serialized"
      ? "O sistema usa a quantidade da compra e gera as etiquetas EST automaticamente no recebimento."
      : "O sistema usa a quantidade da compra e gera uma etiqueta EST para o novo cadastro."}</span>
    {mode === "serialized" && <span>A série do fabricante é opcional e pode ser informada depois, em cada item do Estoque.</span>}
    {mode === "serialized" && quantity > individualReceiptLimit && <p role="alert" className="stock-picker-warning">{individualReceiptLimitMessage}</p>}
  </div>;
}

export function PurchaseStockDestination({ companyCode, quantity, value, onChange, disabled = false, source = "purchasing" }: {
  companyCode: string; quantity: number; value: StockDestination; onChange: (next: StockDestination) => void;
  disabled?: boolean; source?: "purchasing" | "laboratory";
}) {
  const [items, setItems] = useState<Item[]>([]);
  const [catalog, setCatalog] = useState<InventoryItemCatalog>(emptyInventoryItemCatalog);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  useEffect(() => {
    if (!companyCode) { setItems([]); setCatalog(emptyInventoryItemCatalog); return; }
    let alive = true;
    async function load() {
      try {
        if (source === "purchasing") {
          const id = Number(value.inventory_item_id) || 0;
          const response = await apiClient.get<{ items: Item[] } & InventoryItemCatalog>(`/purchasing/stock-options?company_code=${encodeURIComponent(companyCode)}&search=${encodeURIComponent(query.trim())}${id ? `&selected_id=${id}` : ""}`);
          if (alive) { setItems(response.items); setCatalog({ ...emptyInventoryItemCatalog, ...response }); setError(""); }
        } else {
          const [stock, map] = await Promise.all([
            apiClient.get<(Item & {company_code: string})[]>(`/inventory/items?company_code=${encodeURIComponent(companyCode)}`),
            apiClient.get<InventoryItemCatalog>("/inventory/map"),
          ]);
          if (alive) { setItems(stock.filter(x => x.company_code === companyCode)); setCatalog(map); setError(""); }
        }
      } catch (e) { if (alive) setError(e instanceof Error ? e.message : "Erro ao consultar o Estoque."); }
    }
    const timer = window.setTimeout(() => void load(), query ? 200 : 0);
    return () => { alive = false; window.clearTimeout(timer); };
  }, [companyCode, source, value.inventory_item_id, query, reload]);
  const options = useMemo(() => items.filter(item =>
    String(item.id) === value.inventory_item_id || item.id === stockIdFromSearch(query) ||
    [item.stock_code, item.name, item.manufacturer_serial || ""].some(text => text.toLowerCase().includes(query.toLowerCase()))
  ), [items, query, value.inventory_item_id]);
  const selected = items.find(item => String(item.id) === value.inventory_item_id);
  const fieldValue: InventoryItemFieldValue = {
    name: value.inventory_name, mode: value.inventory_mode, category: value.inventory_category,
    quantity, manufacturer_serial: value.inventory_serial, format_id: value.inventory_format_id,
    subtype_id: value.inventory_details.subtype_id ? String(value.inventory_details.subtype_id) : "",
    manufacturer: value.inventory_details.manufacturer || "", model: value.inventory_details.model || "",
    slot_id: value.inventory_details.slot_id ? String(value.inventory_details.slot_id) : "",
    unit: value.inventory_details.unit, notes: value.inventory_details.notes || "",
  };
  const changeFields = (fields: InventoryItemFieldValue) => onChange({ ...value,
    inventory_name: fields.name, inventory_mode: fields.mode, inventory_category: fields.category,
    inventory_serial: fields.manufacturer_serial, inventory_format_id: fields.format_id,
    inventory_details: { subtype_id: Number(fields.subtype_id) || null, manufacturer: fields.manufacturer || null,
      model: fields.model || null, unit: fields.unit, slot_id: Number(fields.slot_id) || null, notes: fields.notes || null },
  });
  return <fieldset className="purchase-stock-target" disabled={disabled}>
    <legend>Como entra no Estoque?</legend>
    <p>Defina o destino agora ou quando o material chegar. O cadastro usa a quantidade já informada na compra e os mesmos campos do Estoque.</p>
    <label>Destino do material
      <select aria-label="Destino do material" value={value.inventory_destination} onChange={e => onChange({ ...value, inventory_destination: e.target.value as StockDestination["inventory_destination"], inventory_item_id: "" })}>
        <option value="">Definir quando chegar</option>
        <option value="existing">Somar a um item existente</option>
        <option value="new">Cadastrar novo item com etiqueta</option>
      </select>
    </label>
    {error && <p role="alert" className="stock-picker-warning">{error} <button type="button" onClick={() => setReload(current => current + 1)}>Tentar novamente</button></p>}
    {value.inventory_destination === "existing" && <>
      <label>Pesquisar item no Estoque<input value={query} onChange={e => setQuery(e.target.value)} placeholder="Código EST, resistor, capacitor, série..." /></label>
      <label>Item que receberá a quantidade
        <select value={value.inventory_item_id} onChange={e => { const chosen = items.find(item => String(item.id) === e.target.value); onChange({ ...value, inventory_item_id: e.target.value, inventory_name: chosen?.name || "" }); }}>
          <option value="">Escolha o item (somente por quantidade)</option>
          {options.map(item => <option key={item.id} disabled={item.mode !== "bulk"} value={item.id}>{item.stock_code} · {item.name} · saldo {item.quantity}{item.mode === "serialized" ? " (individual — não acumulável)" : ""}</option>)}
        </select>
      </label>
      {selected && <><label>Nome adotado do Estoque<input readOnly value={selected.name} /></label><p>Saldo atual: <strong>{selected.quantity}</strong> · Após receber: <strong>{selected.quantity + quantity}</strong> · mesma etiqueta {selected.stock_code}.</p></>}
    </>}
    {value.inventory_destination === "new" && <div className="purchase-stock-new-item">
      <InventoryItemFields value={fieldValue} onChange={changeFields} catalog={catalog} context="purchase" disabled={disabled} />
      <StockReceiptSummary quantity={quantity} mode={value.inventory_mode} />
      <p className="purchase-stock-location-tip">Salvar estes dados prepara o cadastro. A quantidade entra no Estoque somente ao confirmar o recebimento.</p>
    </div>}
  </fieldset>;
}
