import { stockIdFromSearch } from "./stockCode";
import { useEffect, useMemo, useState } from "react";
import { apiClient } from "../../shared/api/apiClient";
import "./purchaseStockDestination.css";

export type StockDestination = {
  inventory_destination: "" | "existing" | "new";
  inventory_item_id: string;
  inventory_name: string;
  inventory_mode: "bulk" | "serialized";
  inventory_serial: string;
  inventory_category: string;
  inventory_format_id: string;
};
export const emptyStockDestination: StockDestination = {
  inventory_destination: "", inventory_item_id: "", inventory_name: "",
  inventory_mode: "bulk", inventory_serial: "", inventory_category: "componentes", inventory_format_id: "",
};
export function stockDestinationPayload(value: StockDestination) {
  return {
    inventory_destination: value.inventory_destination || null,
    inventory_item_id: value.inventory_destination === "existing" ? Number(value.inventory_item_id) || null : null,
    inventory_name: value.inventory_destination === "new" ? value.inventory_name.trim() || null : null,
    inventory_mode: value.inventory_destination === "new" ? value.inventory_mode : null,
    inventory_serial: value.inventory_destination === "new" && value.inventory_mode === "serialized" ? value.inventory_serial.trim() || null : null,
    inventory_category: value.inventory_destination === "new" ? value.inventory_category : null,
    inventory_format_id: value.inventory_destination === "new" && value.inventory_format_id ? Number(value.inventory_format_id) : null,
  };
}
export function stockDestinationFromRequest(item: {
  inventory_destination?: "new" | "existing" | null; inventory_item_id?: number | null;
  inventory_name?: string | null; inventory_mode?: "bulk" | "serialized" | null;
  inventory_serial?: string | null; inventory_category?: string | null; inventory_format_id?: number | null;
}): StockDestination {
  return {
    inventory_destination: item.inventory_destination || "",
    inventory_item_id: item.inventory_item_id ? String(item.inventory_item_id) : "",
    inventory_name: item.inventory_name || "",
    inventory_mode: item.inventory_mode || "bulk",
    inventory_serial: item.inventory_serial || "",
    inventory_category: item.inventory_category || "componentes",
    inventory_format_id: item.inventory_format_id ? String(item.inventory_format_id) : "",
  };
}

type Item = { id: number; stock_code: string; name: string; quantity: number; mode: "bulk" | "serialized"; manufacturer_serial: string | null };
type Format = { id: number; name: string; code: string; category: string };

export function PurchaseStockDestination({ companyCode, quantity, value, onChange, disabled = false, source = "purchasing" }: {
  companyCode: string; quantity: number; value: StockDestination; onChange: (next: StockDestination) => void;
  disabled?: boolean; source?: "purchasing" | "laboratory";
}) {
  const [items, setItems] = useState<Item[]>([]);
  const [formats, setFormats] = useState<Format[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    if (!companyCode) { setItems([]); setFormats([]); return; }
    let alive = true;
    async function load() {
      try {
        if (source === "purchasing") {
          const id = Number(value.inventory_item_id) || 0;
          const response = await apiClient.get<{ items: Item[]; formats: Format[] }>(`/purchasing/stock-options?company_code=${encodeURIComponent(companyCode)}${id ? `&selected_id=${id}` : ""}`);
          if (alive) { setItems(response.items); setFormats(response.formats); setError(""); }
        } else {
          const [stock, map] = await Promise.all([
            apiClient.get<(Item & {company_code: string})[]>(`/inventory/items?company_code=${encodeURIComponent(companyCode)}`),
            apiClient.get<{ formats: Format[] }>("/inventory/map"),
          ]);
          if (alive) { setItems(stock.filter(x => x.company_code === companyCode)); setFormats(map.formats); setError(""); }
        }
      } catch (e) { if (alive) setError(e instanceof Error ? e.message : "Erro ao consultar o Estoque."); }
    }
    void load();
    return () => { alive = false; };
  }, [companyCode, source, value.inventory_item_id]);
  const options = useMemo(() => items.filter(item =>
    String(item.id) === value.inventory_item_id || item.id === stockIdFromSearch(query) ||
    [item.stock_code, item.name, item.manufacturer_serial || ""].some(text => text.toLowerCase().includes(query.toLowerCase()))
  ), [items, query, value.inventory_item_id]);
  const selected = items.find(item => String(item.id) === value.inventory_item_id);
  const formatOptions = formats.filter(fmt => fmt.category === value.inventory_category);
  return <fieldset className="purchase-stock-target" disabled={disabled}>
    <legend>Como entra no Estoque?</legend>
    <p>Opcional enquanto a compra está em andamento; obrigatório antes de confirmar o recebimento. A descrição da solicitação pode ser diferente do cadastro de Estoque.</p>
    <label>Destino do material
      <select value={value.inventory_destination} onChange={e => onChange({ ...value, inventory_destination: e.target.value as StockDestination["inventory_destination"], inventory_item_id: "" })}>
        <option value="">Definir quando chegar</option>
        <option value="existing">Somar a um item existente</option>
        <option value="new">Cadastrar novo item com etiqueta</option>
      </select>
    </label>
    {error && <p role="alert" className="stock-picker-warning">{error}</p>}
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
    {value.inventory_destination === "new" && <div className="purchase-stock-target-grid">
      <label>Nome no Estoque<input value={value.inventory_name} onChange={e => onChange({ ...value, inventory_name: e.target.value })} placeholder="Ex.: Resistor 10k SMD (independente da descrição da compra)" /></label>
      <label>Controle<select value={value.inventory_mode} onChange={e => onChange({ ...value, inventory_mode: e.target.value as "bulk" | "serialized", inventory_serial: "" })}><option value="bulk">Componentes / quantidade</option><option value="serialized">Equipamento único / número de série</option></select></label>
      {value.inventory_mode === "serialized" && <><label>Número de série<input value={value.inventory_serial} onChange={e => onChange({ ...value, inventory_serial: e.target.value })} placeholder="Série obrigatória ao receber" /></label>{quantity !== 1 && <p className="stock-picker-warning">Equipamento individual deve ter quantidade igual a 1.</p>}</>}
      <label>Categoria<input value={value.inventory_category} onChange={e => onChange({ ...value, inventory_category: e.target.value, inventory_format_id: "" })} placeholder="resistor, capacitor, transistor..." /></label>
      <label>Formato<select value={value.inventory_format_id} onChange={e => onChange({ ...value, inventory_format_id: e.target.value })}><option value="">Sem formato específico</option>{formatOptions.map(fmt => <option key={fmt.id} value={fmt.id}>{fmt.name} ({fmt.code})</option>)}</select></label>
      <p className="purchase-stock-location-tip">A posição física (estante, caixa ou gaveta) poderá ser definida depois, na aba Estoque.</p>
    </div>}
  </fieldset>;
}
