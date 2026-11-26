import type { ReactNode } from "react";
import { InventorySlotSearch, type SearchableArea, type SearchableContainer, type SearchableKind, type SearchableSlot } from "./InventorySlotSearch";
import "./inventoryItemFields.css";

export type InventoryItemFieldValue = {
  name: string; mode: "bulk" | "serialized"; category: string; quantity: number;
  manufacturer_serial: string; unit: string; subtype_id: string; format_id: string;
  manufacturer: string; model: string; slot_id: string; notes: string;
};
export type InventoryItemCatalog = {
  categories: Array<{ id: number; code: string; name: string; is_active?: boolean }>;
  subtypes: Array<{ id: number; category: string; name: string; is_active?: boolean }>;
  formats: Array<{ id: number; category: string; name: string; code?: string; is_active?: boolean }>;
  slots: SearchableSlot[]; containers: SearchableContainer[];
  areas: SearchableArea[]; types: SearchableKind[];
};
export const emptyInventoryItemCatalog: InventoryItemCatalog = { categories: [], subtypes: [], formats: [], slots: [], containers: [], areas: [], types: [] };

/** The same item fields are used for direct stock entry and a purchase receipt. */
export function InventoryItemFields({ value, onChange, catalog, context = "inventory", editing = false, disabled = false, extraFields, extraDetails }: {
  value: InventoryItemFieldValue; onChange: (next: InventoryItemFieldValue) => void;
  catalog: InventoryItemCatalog; context?: "inventory" | "purchase"; editing?: boolean;
  disabled?: boolean; extraFields?: ReactNode; extraDetails?: ReactNode;
}) {
  const update = (next: Partial<InventoryItemFieldValue>) => onChange({ ...value, ...next });
  const category = value.category.trim().toLowerCase();
  const categories = catalog.categories.filter(row => row.is_active !== false);
  const subtypes = catalog.subtypes.filter(row => row.is_active !== false && row.category === category);
  const formats = catalog.formats.filter(row => row.is_active !== false && row.category === category);
  return <div className="inventory-item-fields">
    <label>Controle<select aria-label="Controle" disabled={disabled || editing} value={value.mode} onChange={event => update({ mode: event.target.value as "bulk" | "serialized", ...(context === "inventory" && event.target.value === "serialized" ? { quantity: 1 } : {}), manufacturer_serial: "" })}>
      <option value="bulk">Item por quantidade</option><option value="serialized">Item individual · código automático</option>
    </select></label>
    <label className="wide">Nome do item<input aria-label="Nome do item" disabled={disabled} required={context === "inventory"} maxLength={220} value={value.name} placeholder="Ex.: Capacitor 470µF 450V" onChange={event => update({ name: event.target.value })} /></label>
    <label>Tipo de componente<select aria-label="Tipo de componente" disabled={disabled} value={value.category} onChange={event => update({ category: event.target.value, subtype_id: "", format_id: "" })}>
      {!categories.some(row => row.code === value.category) && <option value={value.category}>{value.category === "componentes" ? "Componentes" : value.category || "Selecione o tipo"}</option>}
      {categories.map(row => <option key={row.id} value={row.code}>{row.name}</option>)}
    </select></label>
    <InventorySlotSearch value={value.slot_id} onChange={slot_id => update({ slot_id })} slots={catalog.slots} containers={catalog.containers} areas={catalog.areas} types={catalog.types} disabled={disabled} />
    {value.mode === "serialized" && (context === "inventory" || value.quantity === 1 || value.manufacturer_serial.trim()) && <label>Série do fabricante (opcional)<input aria-label="Série do fabricante (opcional)" disabled={disabled} maxLength={120} value={value.manufacturer_serial} placeholder="Preencha somente se o fabricante informar" onChange={event => update({ manufacturer_serial: event.target.value })} />{context === "purchase" && value.quantity > 1 && <small>Esta compra tem várias unidades. Deixe a série em branco para gerar um código por unidade e informe as séries depois no Estoque.</small>}</label>}
    {context === "inventory" && value.mode === "bulk" && <label>Quantidade inicial<input aria-label="Quantidade inicial" disabled={disabled || editing} type="number" min="0" step="1" value={value.quantity} onChange={event => update({ quantity: Number(event.target.value) })} /></label>}
    <label>Unidade<input aria-label="Unidade" disabled={disabled || editing} maxLength={12} value={value.unit} placeholder="UN" onChange={event => update({ unit: event.target.value })} /></label>
    <label className="wide">Descrição<textarea aria-label="Descrição" disabled={disabled} rows={3} maxLength={4000} value={value.notes} placeholder="Resumo visual e técnico do item para facilitar a identificação." onChange={event => update({ notes: event.target.value })} /></label>
    {extraFields}
    <details className="wide inventory-item-details"><summary>Mais detalhes do item</summary><div className="inventory-item-fields">
      <label>Subtipo<select aria-label="Subtipo" disabled={disabled} value={value.subtype_id} onChange={event => update({ subtype_id: event.target.value })}><option value="">Não especificado</option>{value.subtype_id && !subtypes.some(row => String(row.id) === value.subtype_id) && <option value={value.subtype_id}>Subtipo #{value.subtype_id}</option>}{subtypes.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
      <label>Formato / encapsulamento<select aria-label="Formato / encapsulamento" disabled={disabled} value={value.format_id} onChange={event => update({ format_id: event.target.value })}><option value="">Não especificado</option>{value.format_id && !formats.some(row => String(row.id) === value.format_id) && <option value={value.format_id}>Formato #{value.format_id}</option>}{formats.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
      <label>Fabricante<input aria-label="Fabricante" disabled={disabled} maxLength={120} value={value.manufacturer} onChange={event => update({ manufacturer: event.target.value })} /></label>
      <label>Modelo<input aria-label="Modelo" disabled={disabled} maxLength={120} value={value.model} onChange={event => update({ model: event.target.value })} /></label>
      {extraDetails}
    </div></details>
  </div>;
}
