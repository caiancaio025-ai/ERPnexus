import { stockIdFromSearch } from "./stockCode";
import { useEffect, useMemo, useState } from "react";
import { Archive, ArrowDownToLine, ArrowLeft, Boxes, Camera, Eye, FolderPlus, LogOut, MapPinned, PackagePlus, Pencil, Trash2, Printer, RefreshCw, Search, Warehouse } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { apiClient } from "../../shared/api/apiClient";
import { SenticoSidebar } from "../../shared/ui/SenticoSidebar";
import type { AuthUser } from "../auth/AuthCard";
import "./inventory.css";
import { InventoryPhysicalMap } from "./InventoryPhysicalMap";
import { CameraCapture } from "../laboratory/components/CameraCapture";

export type StockItem = {
  id: number; stock_code: string; company_code: string; name: string; category: string;
  manufacturer: string | null; model: string | null; subtype_id: number | null; format_id: number | null; mode: "serialized" | "bulk";
  manufacturer_serial: string | null; quantity: number; unit: string;
  unit_cost?: string; slot_id: number | null; location_code: string | null;
  notes: string | null; photo_ids: number[]; is_active: boolean;
};
type Area = { id: number; code: string; name: string; is_active: boolean };
type Kind = { id: number; code: string; name: string; is_active: boolean };
type Container = { id: number; area_id: number; parent_id: number | null; type_id: number; code: string; name: string; rows: number; columns: number; layout_row: number; layout_column: number; layout_span: number; is_active: boolean };
type Slot = { id: number; container_id: number; code: string; name: string; row: number; column: number; is_active: boolean; items: Array<{ id: number; code: string; name: string; quantity: number }>; occupied: boolean };
type ComponentCategory = { id: number; code: string; name: string; is_active: boolean };
type ComponentSubtype = { id: number; category: string; code: string; name: string; is_active: boolean };
type ComponentFormat = { id: number; category: string; code: string; name: string; is_active: boolean };
type StockMap = { categories: ComponentCategory[]; subtypes: ComponentSubtype[]; formats: ComponentFormat[]; companies: Array<{code:string;name:string}>; areas: Area[]; types: Kind[]; containers: Container[]; slots: Slot[]; unlocated: number };

type InventoryProps = { user: AuthUser; onLogout: () => void };
const blankItem = { company_code: "universo_eletronica", name: "", category: "componentes", subtype_id: "", format_id: "", manufacturer: "", model: "", mode: "bulk" as "bulk" | "serialized", manufacturer_serial: "", unit: "UN", quantity: 1, unit_cost: "0", slot_id: "", notes: "" };
const blankContainer = { code: "", name: "", area_id: "", type_id: "", parent_id: "", rows: 1, columns: 1, layout_row: 1, layout_column: 1, layout_span: 3 };
// Mantém os códigos internos de categoria para integrar Compras e OS sem migrar vínculos antigos.
const categoryName = (map: StockMap, code: string) => map.categories.find(c => c.code === code)?.name ?? code;
const locationLabel = (code: string | null) => {
  if (!code) return "Local pendente";
  if (/^[A-Z]{1,3}[1-5]$/.test(code)) return `Estante ${code}`;
  if (code.startsWith("CAIXA-")) return `Caixa ${code.slice(6)}`;
  if (code.startsWith("GAVETA-")) return `Gaveta ${code.slice(7)}`;
  if (code.startsWith("GALERIA-")) return `Galeia ${code.slice(8)}`;
  return code;
};
const shelfCode = (position: number): string => {
  let num = position + 1;
  let result = "";
  while (num > 0) { num -= 1; result = String.fromCharCode(65 + num % 26) + result; num = Math.floor(num / 26); }
  return result;
};
const shelfIndex = (code: string): number | null => {
  const cleaned = code.trim().toUpperCase();
  if (!/^[A-Z]{1,3}$/.test(cleaned)) return null;
  let result = 0;
  for (const char of cleaned) result = result * 26 + (char.charCodeAt(0) - 64);
  return result - 1;
};
const locationKindLabel = (kind: string) => ({ estante: "Estante", gaveta: "Gaveta", caixa: "Caixa", galeria: "Galeia", galeia: "Galeia" }[kind] ?? "Local");
const locationTypeName = (kind: Pick<Kind, "code" | "name"> | null | undefined) => {
  if (!kind) return "Local";
  return ["galeria", "galeia"].includes(kind.code) ? "Galeia" : kind.name;
};
const itemFormatLabel = (item: StockItem, map: StockMap) => {
  const pieces = [
    categoryName(map, item.category),
    map.subtypes.find(st => st.id === item.subtype_id)?.name,
    map.formats.find(f => f.id === item.format_id)?.name,
  ].filter(Boolean);
  return pieces.join(" • ");
};
const itemDescription = (item: StockItem) => item.notes?.trim() || [item.manufacturer, item.model].filter(Boolean).join(" • ") || "Sem descrição complementar";
const errorText = (err: unknown) => err instanceof Error ? err.message : "Operação não concluída.";
const photoUrl = (id: number) => `/api/inventory/photos/${id}`;
const maySeeCost = (user: AuthUser) => ["gestao", "super_admin"].includes(user.role);

export function InventoryDashboard({ user, onLogout }: InventoryProps) {
  const navigate = useNavigate();
  const [view, setView] = useState<"items" | "map" | "locations" | "catalog">("items");
  const [stockMap, setStockMap] = useState<StockMap>({ companies: [], areas: [], types: [], categories: [], subtypes: [], formats: [], containers: [], slots: [], unlocated: 0 });
  const [items, setItems] = useState<StockItem[]>([]);
  const [filter, setFilter] = useState("");
  const [stockFilter, setStockFilter] = useState<"all" | "available" | "unlocated" | "empty">("all");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [editor, setEditor] = useState(false);
  const [editing, setEditing] = useState<StockItem | null>(null);
  const [form, setForm] = useState(blankItem);
  const [selected, setSelected] = useState<StockItem | null>(null);
  const [qty, setQty] = useState("1");
  const [itemMovements, setItemMovements] = useState<Array<{id:number;kind:string;quantity:number;work_order_id:number|null;created_at:string}>>([]);
  const [itemLocations,setItemLocations] = useState<Array<{id:number;from:string|null;to:string|null;created_at:string;moved_by:number}>>([]);
  const [areaForm, setAreaForm] = useState({ code: "", name: "" });
  const [typeForm, setTypeForm] = useState({ code: "", name: "" });
  const [categoryForm, setCategoryForm] = useState({ code: "", name: "" });
  const [subtypeForm, setSubtypeForm] = useState({ category: "capacitor", code: "", name: "" });
  const [formatForm, setFormatForm] = useState({ category: "resistor", code: "", name: "" });
  const [pendingPhoto, setPendingPhoto] = useState<File | null>(null);
  const [showAdvancedLocations, setShowAdvancedLocations] = useState(false);
  const [showFormatEditor, setShowFormatEditor] = useState(false);
  const [locForm, setLocForm] = useState(blankContainer);
  const [locationEdit, setLocationEdit] = useState<Container | null>(null);
  const [locEditName, setLocEditName] = useState("");
  const [locationSearch, setLocationSearch] = useState("");
  const [showArchivedLocations, setShowArchivedLocations] = useState(false);
  const [locationBatchCount, setLocationBatchCount] = useState("1");
  const [locationPage, setLocationPage] = useState(0);
  const [photoUploading, setPhotoUploading] = useState(false);
  const [cameraTarget, setCameraTarget] = useState<"form" | "details" | null>(null);

  async function load() {
    const [map, stock] = await Promise.all([
      apiClient.get<StockMap>("/inventory/map"), apiClient.get<StockItem[]>("/inventory/items"),
    ]);
    setStockMap(map); setItems(stock);
    setSelected(previous => previous ? stock.find(i => i.id === previous.id) ?? null : null);
  }
  useEffect(() => { void load().catch(err => setError(errorText(err))); }, []);
  const filtered = useMemo(() => items.filter(i => {
    if (!i.is_active) return false;
    if (stockFilter === "available" && i.quantity <= 0) return false;
    if (stockFilter === "unlocated" && i.slot_id !== null) return false;
    if (stockFilter === "empty" && i.quantity !== 0) return false;
    const term = filter.trim().toLocaleLowerCase("pt-BR");
    return !term || i.id === stockIdFromSearch(filter) || [i.name, i.stock_code, i.manufacturer_serial, i.category, categoryName(stockMap,i.category), stockMap.subtypes.find(st => st.id === i.subtype_id)?.name, i.location_code, i.notes, stockMap.formats.find(f => f.id === i.format_id)?.name]
      .some(v => v?.toLocaleLowerCase("pt-BR").includes(term));
  }), [items, filter, stockFilter, stockMap.categories, stockMap.subtypes, stockMap.formats]);
  const nextShelf = useMemo(() => {
    const taken = new Set(stockMap.containers.filter(c => stockMap.types.find(t => t.id === c.type_id)?.code === "estante").map(c => c.code.toUpperCase()));
    let i = 0; while (taken.has(shelfCode(i))) i++;
    return shelfCode(i);
  }, [stockMap.containers, stockMap.types]);
  const drawerNumbers = useMemo(() => new Set(stockMap.containers.filter(c => stockMap.types.find(t => t.id === c.type_id)?.code === "gaveta")
    .map(c => c.code.toUpperCase().match(/^GAVETA-(\d+)$/)?.[1]).filter((v): v is string => !!v).map(Number)), [stockMap.containers, stockMap.types]);
  const nextDrawer = useMemo(() => { let candidate = 1; while (drawerNumbers.has(candidate)) candidate += 1; return candidate; }, [drawerNumbers]);
  const currentLocationKind = stockMap.types.find(t=>String(t.id)===String(locForm.type_id))?.code || "estante";
  const nextGenericLocationNumber = useMemo(() => {
    const byKind = (kindCode: string) => {
      const prefix = `${kindCode.toUpperCase()}-`;
      const numbers = stockMap.containers
        .filter(c => stockMap.types.find(t => t.id === c.type_id)?.code === kindCode)
        .map(c => Number(c.code.toUpperCase().startsWith(prefix) ? c.code.slice(prefix.length) : NaN))
        .filter(n => Number.isFinite(n) && n > 0);
      let candidate = 1;
      while (numbers.includes(candidate)) candidate += 1;
      return candidate;
    };
    return byKind;
  }, [stockMap.containers, stockMap.types]);
  const locationDrafts = useMemo(() => {
    const selectedKind = stockMap.types.find(t => String(t.id) === String(locForm.type_id)) ?? stockMap.types.find(t => t.code === "estante");
    if (!selectedKind) return [] as Array<{code:string;name:string;summary:string}>;
    const requested = Math.max(1, Number(locationBatchCount) || 1);
    const suffix = locForm.name.trim();
    if (selectedKind.code === "estante") {
      const startIndex = shelfIndex(locForm.code || nextShelf) ?? shelfIndex(nextShelf) ?? 0;
      return Array.from({ length: requested }, (_, index) => {
        const code = shelfCode(startIndex + index);
        const name = requested === 1 && suffix ? suffix : `${locationKindLabel(selectedKind.code)} ${code}${suffix ? ` • ${suffix}` : ""}`;
        return { code, name, summary: `${code}1 até ${code}5` };
      });
    }
    const startNumber = Math.max(1, Number((locForm.code || String(selectedKind.code === "gaveta" ? nextDrawer : nextGenericLocationNumber(selectedKind.code))).replace(/[^0-9]/g, "")) || 1);
    return Array.from({ length: requested }, (_, index) => {
      const number = startNumber + index;
      const code = `${selectedKind.code.toUpperCase()}-${number}`;
      const base = `${locationKindLabel(selectedKind.code)} ${number}`;
      const name = requested === 1 && suffix ? suffix : `${base}${suffix ? ` • ${suffix}` : ""}`;
      return { code, name, summary: code };
    });
  }, [stockMap.types, locForm.type_id, locForm.code, locForm.name, locationBatchCount, nextDrawer, nextGenericLocationNumber, nextShelf]);
  const locationResults = useMemo(() => stockMap.containers.filter(c=>{
    if (!showArchivedLocations && !c.is_active) return false;
    const term=locationSearch.trim().toLocaleLowerCase("pt-BR");
    return !term || [c.name,c.code,stockMap.types.find(t=>t.id===c.type_id)?.name].some(x=>x?.toLocaleLowerCase("pt-BR").includes(term));
  }).sort((a,b)=>{
    const aNum=Number(a.code.match(/^GAVETA-(\d+)$/)?.[1]);const bNum=Number(b.code.match(/^GAVETA-(\d+)$/)?.[1]);
    return aNum && bNum ? aNum-bNum : a.name.localeCompare(b.name,"pt-BR",{numeric:true});
  }),[stockMap.containers,stockMap.types,locationSearch,showArchivedLocations]);
  const locationPageCount = Math.max(1,Math.ceil(locationResults.length/40));
  const totalUnits = items.filter(i => i.is_active).reduce((a, item) => a + item.quantity, 0);
  useEffect(()=>{if(!selected){setItemMovements([]);setItemLocations([]);return;}void Promise.all([
    apiClient.get<typeof itemMovements>(`/inventory/items/${selected.id}/movements`),
    apiClient.get<typeof itemLocations>(`/inventory/items/${selected.id}/location-history`),
  ]).then(([movements,locations])=>{setItemMovements(movements);setItemLocations(locations);}).catch(()=>{setItemMovements([]);setItemLocations([]);});},[selected?.id, selected?.quantity, selected?.slot_id]);
  function success(text: string) { setError(""); setMessage(text); }
  async function run(task: () => Promise<void>) { setBusy(true); setError(""); setMessage(""); try { await task(); await load(); } catch(e) { setError(errorText(e)); } finally { setBusy(false); } }
  function openNew() { setCameraTarget(null); setPendingPhoto(null); setEditing(null); setForm({ ...blankItem, company_code: stockMap.companies.find(c=>c.code===blankItem.company_code)?.code ?? stockMap.companies[0]?.code ?? blankItem.company_code, slot_id: "" }); setEditor(true); }
  function openEdit(item: StockItem) { setCameraTarget(null); setPendingPhoto(null); setEditing(item); setForm({ company_code:item.company_code, name:item.name, category:item.category, subtype_id:item.subtype_id?.toString()??"", format_id:item.format_id?.toString()??"", manufacturer:item.manufacturer??"", model:item.model??"", mode:item.mode, manufacturer_serial:item.manufacturer_serial??"", unit:item.unit, quantity:item.quantity, unit_cost:item.unit_cost??"0", slot_id:item.slot_id?.toString()??"", notes:item.notes??"" }); setEditor(true); }
  async function saveItem(event: React.FormEvent) {
    event.preventDefault();
    await run(async () => {
      if (editing) {
        await apiClient.put(`/inventory/items/${editing.id}`, {name:form.name, category:form.category, subtype_id:form.subtype_id?Number(form.subtype_id):null, format_id:form.format_id?Number(form.format_id):null, manufacturer:form.manufacturer||null, model:form.model||null, slot_id:form.slot_id?Number(form.slot_id):null, unit_cost:maySeeCost(user)?Number(form.unit_cost):null, notes:form.notes||null, is_active:true});
        if (pendingPhoto) {
          const photo = new FormData(); photo.append("file",pendingPhoto);
          try { await apiClient.post(`/inventory/items/${editing.id}/photos`,photo); }
          catch(e) { setEditor(false); setPendingPhoto(null); throw new Error(`Dados salvos, mas a foto não foi enviada: ${errorText(e)}. Anexe-a nos detalhes.`); }
        }
      } else {
        const created = await apiClient.post<{id:number}>("/inventory/items", { ...form, subtype_id:form.subtype_id?Number(form.subtype_id):null, format_id:form.format_id?Number(form.format_id):null, slot_id:form.slot_id?Number(form.slot_id):null, quantity:Number(form.quantity), unit_cost:maySeeCost(user)?Number(form.unit_cost):0, manufacturer_serial:form.manufacturer_serial||null });
        if (pendingPhoto) {
          const photo = new FormData(); photo.append("file", pendingPhoto);
          try { await apiClient.post(`/inventory/items/${created.id}/photos`, photo); }
          catch(e) { setEditor(false); setPendingPhoto(null); throw new Error(`Item ${created.id} salvo, mas a foto não foi enviada: ${errorText(e)}. Anexe-a nos detalhes; não cadastre o item novamente.`); }
        }
      }
      setEditor(false); setPendingPhoto(null); success(editing?"Item atualizado.":"Item cadastrado com etiqueta individual.");
    });
  }
  async function move(kind:"receive"|"issue", item:StockItem) {
    await run(async () => {
      if (kind === "issue") throw new Error("A baixa para O.S. deve ser realizada pela aba Materiais da ordem de serviço.");
      await apiClient.post(`/inventory/items/${item.id}/receive`, { quantity:Number(qty) });
      success("Entrada registrada no histórico do estoque.");
    });
  }
  async function uploadPhoto(file: File, item: StockItem) {
    setPhotoUploading(true);
    try {
      await run(async () => {
        const fd = new FormData();
        fd.append("file", file);
        await apiClient.post(`/inventory/items/${item.id}/photos`, fd);
        success("Foto anexada.");
      });
    } finally {
      setPhotoUploading(false);
    }
  }
  async function renameArea(area:Area) {
    const name=window.prompt(`Renomear área ${area.code}`,area.name);
    if(!name?.trim()||name.trim()===area.name)return;
    await run(async()=>{await apiClient.put(`/inventory/areas/${area.id}`,{code:area.code,name:name.trim()});success("Área atualizada.");});
  }
  async function renameType(kind:Kind) {
    const name=window.prompt(`Renomear tipo ${kind.code}`,kind.name);
    if(!name?.trim()||name.trim()===kind.name)return;
    await run(async()=>{await apiClient.put(`/inventory/types/${kind.id}`,{code:kind.code,name:name.trim()});success("Tipo atualizado.");});
  }
  async function createArea(e:React.FormEvent) {e.preventDefault(); await run(async()=>{await apiClient.post("/inventory/areas",areaForm);setAreaForm({code:"",name:""});success("Área criada.");});}
  async function createCategory(e:React.FormEvent) {e.preventDefault();await run(async()=>{
    await apiClient.post("/inventory/categories",categoryForm);setCategoryForm({code:"",name:""});success("Tipo de componente criado.");
  });}
  async function renameCategory(category:ComponentCategory) {
    const name=window.prompt(`Renomear ${category.name}`,category.name);
    if(!name?.trim()||name.trim()===category.name)return;
    await run(async()=>{await apiClient.put(`/inventory/categories/${category.id}`,{code:category.code,name:name.trim()});success("Tipo atualizado.");});
  }
  async function createSubtype(e:React.FormEvent) {e.preventDefault();await run(async()=>{
    await apiClient.post("/inventory/subtypes",subtypeForm);setSubtypeForm({...subtypeForm,code:"",name:""});success("Subtipo criado.");
  });}
  async function renameSubtype(subtype:ComponentSubtype) {
    const name=window.prompt(`Renomear ${subtype.name}`,subtype.name);
    if(!name?.trim()||name.trim()===subtype.name)return;
    await run(async()=>{await apiClient.put(`/inventory/subtypes/${subtype.id}`,{category:subtype.category,code:subtype.code,name:name.trim()});success("Subtipo atualizado.");});
  }
  async function createFormat(e:React.FormEvent) {e.preventDefault();await run(async()=>{
    await apiClient.post("/inventory/formats",formatForm);
    setFormatForm({...formatForm,code:"",name:""});success("Formato cadastrado.");
  });}
  async function renameFormat(format:ComponentFormat) {
    const name=window.prompt(`Nome do formato ${format.code}`,format.name);
    if(!name?.trim() || name.trim()===format.name)return;
    await run(async()=>{await apiClient.put(`/inventory/formats/${format.id}`, {category:format.category,code:format.code,name:name.trim()});success("Formato atualizado.");});
  }
  async function createType(e:React.FormEvent) {e.preventDefault();await run(async()=>{await apiClient.post("/inventory/types",typeForm);setTypeForm({code:"",name:""});success("Tipo criado.");});}
  async function createLocation(e:React.FormEvent) {e.preventDefault(); await run(async()=>{
    const kind=stockMap.types.find(t=>String(t.id)===String(locForm.type_id)) ?? stockMap.types.find(t=>t.code==="estante");
    if(!kind) throw new Error("Cadastre um tipo de local antes de continuar.");
    const areaId = Number(locForm.area_id || stockMap.areas.find(a=>a.is_active)?.id);
    if (!areaId) throw new Error("Cadastre uma área ativa antes de criar locais.");
    const drafts = locationDrafts;
    if (!drafts.length) throw new Error("Nenhum local foi preparado para cadastro.");
    const baseRow = Math.min(50, Math.max(0,...stockMap.containers.filter(c=>stockMap.types.find(t=>t.id===c.type_id)?.code==="estante").map(c=>c.layout_row))+1);
    for (const [index, draft] of drafts.entries()) {
      await apiClient.post("/inventory/containers", {
        area_id: areaId,
        type_id: kind.id,
        code: draft.code,
        name: draft.name,
        rows: 1,
        columns: kind.code==="estante" ? 5 : 1,
        parent_id: null,
        layout_row: kind.code==="estante" ? Math.min(50, baseRow + index) : 1,
        layout_column: 1,
        layout_span: kind.code==="estante" ? 6 : 3,
      });
    }
    setLocForm(blankContainer);
    setLocationBatchCount("1");
    success(drafts.length===1 ? `${drafts[0].name} cadastrado.` : `${drafts.length} ${locationKindLabel(kind.code).toLowerCase()}(s) cadastrados com sucesso.`);
  });}
  async function deleteLocation(location:Container) {
    if (!window.confirm(`EXCLUIR DEFINITIVAMENTE ${location.name} (${location.code})?\n\nO endereço e todas as suas posições serão apagados do banco, inclusive se estiver arquivado. Não será possível restaurá-lo.\n\nAs movimentações históricas manterão os códigos de localização. Se ainda houver itens vinculados, a exclusão será bloqueada até realocá-los.`)) return;
    await run(async()=>{
      const result=await apiClient.delete<{outcome:"deleted";message:string}>(`/inventory/containers/${location.id}`);
      setLocationEdit(null);
      success(result.message || "Endereço excluído definitivamente.");
    });
  }
  async function restoreLocation(location:Container) {
    await run(async()=>{
      await apiClient.put(`/inventory/containers/${location.id}`,{
        name:location.name,layout_row:location.layout_row,layout_column:location.layout_column,
        layout_span:location.layout_span,is_active:true,
      });
      setLocationEdit(null);
      success("Endereço restaurado. As posições estão disponíveis novamente.");
    });
  }
  async function deleteArea(area:Area) {
    if (!window.confirm(`Excluir a área ${area.name}? A área precisa estar sem endereços.`))return;
    await run(async()=>{await apiClient.delete(`/inventory/areas/${area.id}`);success("Área vazia excluída.");});
  }
  async function deleteKind(kind:Kind) {
    if (!window.confirm(`Excluir o tipo de local ${kind.name}? Só é possível se não estiver em uso.`))return;
    await run(async()=>{await apiClient.delete(`/inventory/types/${kind.id}`);success("Tipo sem uso excluído.");});
  }
  async function editLocation(e:React.FormEvent) { e.preventDefault(); if(!locationEdit)return;await run(async()=>{await apiClient.put(`/inventory/containers/${locationEdit.id}`,{name:locEditName,layout_row:locationEdit.layout_row,layout_column:locationEdit.layout_column,layout_span:locationEdit.layout_span,is_active:locationEdit.is_active});setLocationEdit(null);success("Local atualizado.");});}

  return <div className="sentico-shell sentico-inventory-shell">
    <SenticoSidebar
      user={user}
      onLogout={onLogout}
      sectionLabel="Estoque"
      sectionItems={[
        { id: "items", label: "Itens e entradas", icon: Archive, active: view === "items", onClick: () => setView("items") },
        { id: "map", label: "Mapa físico", icon: MapPinned, active: view === "map", onClick: () => setView("map") },
        { id: "locations", label: "Endereços", icon: Warehouse, active: view === "locations", onClick: () => setView("locations") },
        { id: "catalog", label: "Tipos e formatos", icon: Boxes, active: view === "catalog", onClick: () => setView("catalog") },
      ]}
    />
    <main className="inv-app sentico-content">
    <header className="inv-top"><button className="inv-back" onClick={()=>navigate("/painel")}><ArrowLeft size={17}/> Voltar</button><div><small>GESTÃO OPERACIONAL</small><h1><Boxes size={26}/> Estoque técnico</h1><p>Etiquetas individuais, endereço físico e baixa vinculada à ordem de serviço.</p></div><button type="button" className="inv-back inv-logout" onClick={onLogout}><LogOut size={16}/> Sair</button></header>
    <nav className="inv-tabs" aria-label="Seções do estoque"><button type="button" className={view==="items"?"active":""} aria-pressed={view==="items"} onClick={()=>setView("items")}><Archive size={16}/> Itens e entradas</button><button type="button" className={view==="map"?"active":""} aria-pressed={view==="map"} onClick={()=>setView("map")}><MapPinned size={16}/> Mapa físico</button><button type="button" className={view==="locations"?"active":""} aria-pressed={view==="locations"} onClick={()=>setView("locations")}><Warehouse size={16}/> Endereços</button><button type="button" className={view==="catalog"?"active":""} aria-pressed={view==="catalog"} onClick={()=>setView("catalog")}><Boxes size={16}/> Tipos e formatos</button><button type="button" className="inv-refresh" disabled={busy} onClick={()=>void run(async()=>{await load();success("Atualizado.");})}><RefreshCw size={16}/> Atualizar</button></nav>
    {error&&<div className="inv-alert error">{error}</div>}{message&&<div className="inv-alert good">{message}</div>}
    <section className="inv-stats"><article><small>Cadastros</small><b>{items.length}</b></article><article><small>Unidades disponíveis</small><b>{totalUnits}</b></article><article><small>Sem endereço</small><b>{stockMap.unlocated}</b></article><article><small>Posições físicas</small><b>{stockMap.slots.length}</b></article></section>
    {view==="items"&&<>
      <section className="inv-toolbar"><label><Search size={17}/><input placeholder="Pesquisar peça, etiqueta, série, tipo ou posição" value={filter} onChange={e=>setFilter(e.target.value)}/></label><button type="button" className="inv-primary" onClick={openNew}><PackagePlus size={18}/> Cadastrar item</button></section>
      <nav className="inv-quick-filters" aria-label="Filtrar itens do estoque">
        {([ ["all", "Todos"], ["available", "Disponíveis"], ["unlocated", "Sem local"], ["empty", "Sem saldo"] ] as const).map(([key, label]) =>
          <button type="button" key={key} className={stockFilter === key ? "active" : ""} aria-pressed={stockFilter === key} onClick={() => setStockFilter(key)}>{label}</button>)}
        <small>{filtered.length} item(ns) encontrado(s)</small>
      </nav>
      <div className="inv-results-summary"><b>{filtered.length}</b><span>resultado(s) com visual leve, foto, tipo, descrição e quantidade em destaque.</span></div>
      <div className="inv-list inv-list-cards">{filtered.map(item=>{
        const formatLabel = itemFormatLabel(item, stockMap);
        const description = itemDescription(item);
        const typeLabel = formatLabel || categoryName(stockMap, item.category);
        const stockState = item.quantity <= 0
          ? { label: "Sem saldo", tone: "empty" }
          : item.quantity <= 3
            ? { label: "Baixo", tone: "low" }
            : { label: "Em estoque", tone: "good" };
        const metaLine = [
          item.mode === "serialized" ? "Item serializado" : "Produto estocado",
          item.manufacturer,
          item.model,
        ].filter(Boolean).join(" • ");
        return <article className="inv-item inv-item-card inv-item-showcase" key={item.id}>
          <button type="button" className="inv-item-photo" aria-label={`Ver detalhes de ${item.name}`} onClick={()=>{setSelected(item);setQty("1");}}>
            {item.photo_ids.length?<img loading="lazy" alt={`Foto de ${item.name}`} src={photoUrl(item.photo_ids[0])}/>:<Camera size={28}/>}
          </button>
          <div className="inv-item-main inv-item-showcase-main">
            <div className="inv-item-heading">
              <b>{item.name}</b>
              <small className="inv-item-stockcode">{item.stock_code}</small>
            </div>
            <div className="inv-item-meta-row">
              <span className="inv-pill inv-pill-type">{typeLabel}</span>
              {metaLine&&<span className="inv-item-mini-meta">{metaLine}</span>}
              {item.manufacturer_serial&&<span className="inv-item-mini-meta">Série: {item.manufacturer_serial}</span>}
            </div>
          </div>
          <div className="inv-item-data-grid">
            <div className="inv-item-data">
              <small>Descrição</small>
              <strong title={description}>{description}</strong>
            </div>
            <div className="inv-item-data">
              <small>Local</small>
              <strong className={item.slot_id?"":"is-missing"}>{locationLabel(item.location_code)}</strong>
            </div>
            {maySeeCost(user)&&item.unit_cost!==undefined&&<div className="inv-item-data">
              <small>Valor unitário</small>
              <strong>R$ {Number(item.unit_cost).toFixed(2)}</strong>
            </div>}
          </div>
          <div className={`inv-item-stockbox ${stockState.tone}`}>
            <small>Estoque</small>
            <strong>{item.quantity} {item.unit}</strong>
            <span>{stockState.label}</span>
          </div>
          <div className="inv-actions inv-actions-compact">
            <button type="button" className="inv-action-details" onClick={()=>{setSelected(item);setQty("1");}}><Eye size={16}/> Ver</button>
            <button type="button" className="inv-action-icon" aria-label={`Editar ${item.name}`} title="Editar item" onClick={()=>openEdit(item)}><Pencil size={17}/></button>
            <button type="button" className="inv-action-icon" aria-label={`Imprimir etiqueta de ${item.name}`} title="Imprimir etiqueta" onClick={()=>window.open(`/api/inventory/items/${item.id}/label.pdf`,"_blank","noopener,noreferrer")}><Printer size={17}/></button>
          </div>
        </article>})}
        {!filtered.length&&<p className="inv-empty">Nenhum item encontrado.</p>}</div>
    </>}
    {view==="map"&&<InventoryPhysicalMap map={stockMap} onLocate={(code)=>{setView("items");setFilter(code);setStockFilter("all");}} />}
    {view==="locations"&&<div className="inv-locations-simple">
      <form onSubmit={createLocation} className="inv-panel inv-location-main">
        <div className="inv-panel-heading"><div><h2>Endereços do estoque</h2><p>Cadastre estantes, caixas, gavetas e galeias com criação livre, sem sequência forçada e com prévia simples.</p></div><Warehouse size={23}/></div>
        <div className="inv-location-types">
          {stockMap.types.filter(t=>t.is_active&&["estante","caixa","gaveta","galeria","galeia"].includes(t.code)).map(t=><button key={t.id} type="button" className={(locForm.type_id||String(stockMap.types.find(q=>q.code==="estante")?.id))===String(t.id)?"selected":""} aria-pressed={(locForm.type_id||String(stockMap.types.find(q=>q.code==="estante")?.id))===String(t.id)} onClick={()=>setLocForm({...locForm,type_id:String(t.id),code:"",name:""})}>{locationTypeName(t)}</button>)}
        </div>
        <div className="inv-location-builder">
          <label>{currentLocationKind==="estante"?"Começar na letra":"Começar no número"}<input placeholder={currentLocationKind==="estante"?`Automático: ${nextShelf}`:currentLocationKind==="gaveta"?`Automático: ${nextDrawer}`:`Automático: ${nextGenericLocationNumber(currentLocationKind)}`} value={locForm.code} onChange={e=>setLocForm({...locForm,code:e.target.value})}/></label>
          <label>Quantos locais criar?<input type="number" min="1" value={locationBatchCount} onChange={e=>setLocationBatchCount(e.target.value)}/></label>
          <label className="wide">Nome complementar / grupo (opcional)<input placeholder={currentLocationKind==="estante"?"Ex.: IGBTs / potência":"Ex.: Capacitores, cabos, contatores"} value={locForm.name} onChange={e=>setLocForm({...locForm,name:e.target.value})}/></label>
          {stockMap.areas.length>1&&<label className="wide">Área onde ficará o local<select value={locForm.area_id} onChange={e=>setLocForm({...locForm,area_id:e.target.value})}><option value="">{stockMap.areas.find(a=>a.is_active)?.name||"Escolha a área"} (padrão)</option>{stockMap.areas.filter(a=>a.is_active).map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label>}
        </div>
        <div className="inv-location-preview inv-location-preview-rich">
          <div><b>{locationDrafts.length===1?"Prévia do novo local":"Prévia dos novos locais"}</b><span>{currentLocationKind==="estante"?"Cada estante é criada com cinco posições em coluna, do topo para baixo.":"Cada caixa, gaveta ou galeia é criada como endereço simples."}</span></div>
          <div className="inv-location-preview-cards">{locationDrafts.slice(0,6).map(draft=><article key={draft.code}><strong>{draft.name}</strong><small>{draft.code}</small><span>{draft.summary}</span></article>)}{locationDrafts.length>6&&<article className="ghost"><strong>+{locationDrafts.length-6}</strong><small>locais adicionais</small><span>serão criados na mesma sequência</span></article>}</div>
        </div>
        <button type="submit" disabled={busy||!stockMap.areas.length}><FolderPlus size={16}/> {locationDrafts.length>1?`Criar ${locationDrafts.length} ${locationKindLabel(currentLocationKind).toLowerCase()}(s)`:currentLocationKind==="estante"?"Criar estante com 5 posições":"Salvar endereço"}</button>
        {!stockMap.areas.length&&<p>Primeiro cadastre uma área nas configurações avançadas.</p>}
      </form>
      <section className="inv-panel inv-location-directory"><h2>Endereços cadastrados</h2><p>Pesquise pelo código, número, letra ou tipo e abra rapidamente para editar.</p><label className="inv-location-search"><Search size={16}/><input placeholder="Ex.: Estante B, Gaveta 445, Caixa 12" value={locationSearch} onChange={e=>{setLocationSearch(e.target.value);setLocationPage(0);}} /></label><label className="inv-location-archived-toggle"><input type="checkbox" checked={showArchivedLocations} onChange={e=>{setShowArchivedLocations(e.target.checked);setLocationPage(0);}}/> Mostrar arquivados</label><small>{locationResults.length} endereço(s) encontrado(s) · página {Math.min(locationPage+1,locationPageCount)} de {locationPageCount}</small><div className="inv-location-list">{locationResults.slice(Math.min(locationPage,locationPageCount-1)*40,(Math.min(locationPage,locationPageCount-1)+1)*40).map(c=><button key={c.id} onClick={()=>{setLocationEdit(c);setLocEditName(c.name)}} type="button"><Warehouse size={17}/><span><b>{c.name}{!c.is_active&&<em className="inv-location-archive-badge">Arquivado</em>}</b><small>{locationTypeName(stockMap.types.find(t=>t.id===c.type_id))} · {c.code} · {c.rows*c.columns} posições</small></span><Pencil size={14}/></button>)}</div><div className="inv-page-nav"><button type="button" disabled={locationPage===0} onClick={()=>setLocationPage(Math.max(0,locationPage-1))}>Anterior</button><button type="button" disabled={locationPage>=locationPageCount-1} onClick={()=>setLocationPage(Math.min(locationPageCount-1,locationPage+1))}>Próxima</button></div></section>
      <details className="inv-panel inv-panel-wide" open={showAdvancedLocations} onToggle={e=>setShowAdvancedLocations(e.currentTarget.open)}><summary>Configurações avançadas: áreas, outros tipos e mapa</summary>
        <div className="inv-advanced-grid"><label>Selecionar outro tipo de local<select value={locForm.type_id} onChange={e=>setLocForm({...locForm,type_id:e.target.value})}><option value="">Estante (padrão)</option>{stockMap.types.filter(t=>t.is_active).map(t=><option key={t.id} value={t.id}>{locationTypeName(t)}</option>)}</select></label><form onSubmit={createArea}><h3>Áreas de estoque</h3><input required placeholder="Código: ALM2" value={areaForm.code} onChange={e=>setAreaForm({...areaForm,code:e.target.value})}/><input required placeholder="Nome da área" value={areaForm.name} onChange={e=>setAreaForm({...areaForm,name:e.target.value})}/><button disabled={busy}>Adicionar área</button><div className="inv-chips">{stockMap.areas.map(a=><span className="inv-admin-chip" key={a.id}><button type="button" key={a.id} onClick={()=>void renameArea(a)}>{a.name} <Pencil size={11}/></button><button type="button" className="inv-danger" title={`Excluir ${a.name}`} onClick={()=>void deleteArea(a)}><Trash2 size={12}/></button></span>)}</div></form>
        <form onSubmit={createType}><h3>Tipos extras de local</h3><input required placeholder="Código: armario" value={typeForm.code} onChange={e=>setTypeForm({...typeForm,code:e.target.value})}/><input required placeholder="Nome do tipo" value={typeForm.name} onChange={e=>setTypeForm({...typeForm,name:e.target.value})}/><button disabled={busy}>Adicionar tipo</button><div className="inv-chips">{stockMap.types.map(t=><span className="inv-admin-chip" key={t.id}><button type="button" key={t.id} onClick={()=>void renameType(t)}>{locationTypeName(t)} <Pencil size={11}/></button><button type="button" className="inv-danger" title={`Excluir tipo ${locationTypeName(t)}`} onClick={()=>void deleteKind(t)}><Trash2 size={12}/></button></span>)}</div></form></div>
        <p>Tipos extras ficam disponíveis no mapa e podem ser editados. Posições e proporções do mapa podem ser ajustadas clicando no local já cadastrado.</p>
      </details>
    </div>}
    {view==="catalog"&&<div className="inv-catalog-view">      <section className="inv-panel inv-panel-wide inv-catalog">
        <div className="inv-panel-heading"><div><h2>Tipos, subtipos e formatos de componentes</h2><p>Ex.: Capacitor → Eletrolítico → PTH radial. Os três níveis podem ser ampliados sem modificar o programa.</p></div><button type="button" onClick={()=>setShowFormatEditor(!showFormatEditor)}>{showFormatEditor?"Recolher configurações":"Gerenciar catálogo"}</button></div>
        {showFormatEditor&&<div className="inv-catalog-editors">
          <form onSubmit={createCategory}><h3>Novo tipo de componente</h3><label>Código<input required placeholder="placa_disparo" value={categoryForm.code} onChange={e=>setCategoryForm({...categoryForm,code:e.target.value})}/></label><label>Nome<input required placeholder="Placa de disparo" value={categoryForm.name} onChange={e=>setCategoryForm({...categoryForm,name:e.target.value})}/></label><button disabled={busy}>Adicionar tipo</button></form>
          <form onSubmit={createSubtype}><h3>Novo subtipo</h3><label>Tipo<select value={subtypeForm.category} onChange={e=>setSubtypeForm({...subtypeForm,category:e.target.value})}>{stockMap.categories.filter(c=>c.is_active).map(c=><option key={c.id} value={c.code}>{c.name}</option>)}</select></label><label>Código<input required placeholder="eletrolitico" value={subtypeForm.code} onChange={e=>setSubtypeForm({...subtypeForm,code:e.target.value})}/></label><label>Nome<input required placeholder="Eletrolítico" value={subtypeForm.name} onChange={e=>setSubtypeForm({...subtypeForm,name:e.target.value})}/></label><button disabled={busy}>Adicionar subtipo</button></form>
          <form onSubmit={createFormat}><h3>Novo formato / encapsulamento</h3><label>Tipo<select value={formatForm.category} onChange={e=>setFormatForm({...formatForm,category:e.target.value})}>{stockMap.categories.filter(c=>c.is_active).map(c=><option key={c.id} value={c.code}>{c.name}</option>)}</select></label><label>Código<input required placeholder="to263" value={formatForm.code} onChange={e=>setFormatForm({...formatForm,code:e.target.value})}/></label><label>Nome<input required placeholder="TO-263 / D2PAK" value={formatForm.name} onChange={e=>setFormatForm({...formatForm,name:e.target.value})}/></label><button disabled={busy}>Adicionar formato</button></form>
        </div>}
        <div className="inv-format-groups">{stockMap.categories.filter(c=>c.is_active).map(category=><div key={category.id}><strong><button type="button" title="Renomear tipo" onClick={()=>void renameCategory(category)}>{category.name} <Pencil size={11}/></button></strong>
          <div className="inv-chips">{stockMap.subtypes.filter(st=>st.category===category.code&&st.is_active).map(st=><button type="button" key={st.id} title="Renomear subtipo" onClick={()=>void renameSubtype(st)}>{st.name} <Pencil size={11}/></button>)}</div>
          <small>Encapsulamentos</small><div className="inv-chips">{stockMap.formats.filter(f=>f.category===category.code&&f.is_active).map(f=><button type="button" key={f.id} title="Renomear formato" onClick={()=>void renameFormat(f)}>{f.name} <Pencil size={11}/></button>)}</div></div>)}</div>
      </section>
    </div>}
    {locationEdit&&<div className="inv-overlay" onClick={()=>setLocationEdit(null)}><form className="inv-dialog" onClick={e=>e.stopPropagation()} onSubmit={editLocation}><h2>Editar local {locationEdit.code}</h2><label>Nome<input value={locEditName} required onChange={e=>setLocEditName(e.target.value)}/></label><details className="inv-edit-advanced"><summary>Configuração de layout (avançado)</summary><div className="inv-form-grid"><label>Linha no mapa<input type="number" min="1" max="50" value={locationEdit.layout_row} onChange={e=>setLocationEdit({...locationEdit,layout_row:Number(e.target.value)})}/></label><label>Coluna no mapa<input type="number" min="1" max="12" value={locationEdit.layout_column} onChange={e=>setLocationEdit({...locationEdit,layout_column:Number(e.target.value)})}/></label><label>Largura no mapa<input type="number" min="1" max="12" value={locationEdit.layout_span} onChange={e=>setLocationEdit({...locationEdit,layout_span:Number(e.target.value)})}/></label></div></details><label><input type="checkbox" checked={locationEdit.is_active} onChange={e=>setLocationEdit({...locationEdit,is_active:e.target.checked})}/> Ativo</label><footer><button type="button" className="inv-danger" disabled={busy} onClick={()=>void deleteLocation(locationEdit)}><Trash2 size={15}/> Excluir definitivamente</button>{!locationEdit.is_active&&<button type="button" disabled={busy} onClick={()=>void restoreLocation(locationEdit)}>Restaurar endereço</button>}<button type="button" onClick={()=>setLocationEdit(null)}>Cancelar</button><button disabled={busy}>Salvar</button></footer></form></div>}
    {editor&&<div className="inv-overlay" onClick={()=>setEditor(false)}><form className="inv-dialog" onClick={e=>e.stopPropagation()} onSubmit={saveItem}><h2>{editing?`Editar ${editing.stock_code}`:"Novo item do estoque"}</h2><p>Cadastro simplificado: preencha o essencial primeiro e use os detalhes avançados apenas quando precisar.</p><div className="inv-form-grid inv-form-grid-simple"><label>Controle<select disabled={!!editing} value={form.mode} onChange={e=>setForm({...form,mode:e.target.value as "bulk"|"serialized",quantity:1})}><option value="bulk">Item por quantidade</option><option value="serialized">Item individual com série</option></select></label><label className="wide">Nome do item<input required value={form.name} placeholder="Ex.: Capacitor 470µF 450V" onChange={e=>setForm({...form,name:e.target.value})}/></label><label>Tipo de componente<select value={form.category} onChange={e=>setForm({...form,category:e.target.value,subtype_id:"",format_id:""})}>{stockMap.categories.filter(c=>c.is_active).map(c=><option key={c.id} value={c.code}>{c.name}</option>)}</select></label><label>Posição física<select value={form.slot_id} onChange={e=>setForm({...form,slot_id:e.target.value})}><option value="">Sem localização</option>{stockMap.slots.filter(s=>s.is_active).map(s=><option value={s.id} key={s.id}>{s.code} · {s.name}</option>)}</select></label>{form.mode==="serialized"?<label>Série / lote do fabricante<input disabled={!!editing} required value={form.manufacturer_serial} placeholder="Número de série" onChange={e=>setForm({...form,manufacturer_serial:e.target.value})}/></label>:<label>Quantidade inicial<input disabled={!!editing} type="number" min="0" step="1" value={form.quantity} onChange={e=>setForm({...form,quantity:Number(e.target.value)})}/></label>}<label>Unidade<input value={form.unit} onChange={e=>setForm({...form,unit:e.target.value})}/></label><label className="wide">Descrição<textarea rows={3} value={form.notes} placeholder="Resumo visual e técnico do item para facilitar a identificação." onChange={e=>setForm({...form,notes:e.target.value})}/></label><div className="wide inv-camera-controls"><button type="button" className="inv-camera-action" onClick={()=>setCameraTarget("form")}><Camera size={18}/> Tirar foto com a câmera</button><label className="inv-upload inv-new-photo">Escolher foto do dispositivo<input type="file" accept="image/jpeg,image/png,image/webp" onChange={e=>{setPendingPhoto(e.target.files?.[0]??null);e.currentTarget.value="";}}/></label></div>{pendingPhoto&&<p className="wide inv-camera-caption">Foto pronta para anexar ao salvar: <strong>{pendingPhoto.name}</strong></p>}<details className="wide inv-edit-advanced"><summary>Mais detalhes do item</summary><div className="inv-form-grid"><label>Subtipo<select value={form.subtype_id} onChange={e=>setForm({...form,subtype_id:e.target.value})}><option value="">Não especificado</option>{stockMap.subtypes.filter(st=>st.is_active&&st.category===form.category).map(st=><option key={st.id} value={st.id}>{st.name}</option>)}</select></label><label>Formato / encapsulamento<select value={form.format_id} onChange={e=>setForm({...form,format_id:e.target.value})}><option value="">Não especificado</option>{stockMap.formats.filter(f=>f.is_active&&f.category===form.category.trim().toLowerCase()).map(f=><option key={f.id} value={f.id}>{f.name}</option>)}</select></label><label>Fabricante<input value={form.manufacturer} onChange={e=>setForm({...form,manufacturer:e.target.value})}/></label><label>Modelo<input value={form.model} onChange={e=>setForm({...form,model:e.target.value})}/></label>{maySeeCost(user)&&<label>Valor unitário (R$)<input type="number" step="0.01" min="0" value={form.unit_cost} onChange={e=>setForm({...form,unit_cost:e.target.value})}/></label>}</div></details></div><footer><button type="button" onClick={()=>setEditor(false)}>Cancelar</button><button disabled={busy}>Salvar item</button></footer></form></div>}
    {selected&&<div className="inv-overlay" onClick={()=>setSelected(null)}><section className="inv-dialog" onClick={e=>e.stopPropagation()}><h2>{selected.name}</h2><p>{selected.stock_code} · {selected.manufacturer_serial||"Controle por quantidade"} · {locationLabel(selected.location_code)}</p><p>Saldo atual: <strong>{selected.quantity} {selected.unit}</strong></p><div className="inv-photos">{selected.photo_ids.map(id=><img key={id} src={photoUrl(id)} alt="Fotografia do item"/>)}</div><div className="inv-camera-controls"><button type="button" className="inv-camera-action" disabled={photoUploading||busy} onClick={()=>setCameraTarget("details")}><Camera size={16}/> {photoUploading?"Enviando foto...":"Tirar foto com a câmera"}</button><label className="inv-upload">Escolher foto do dispositivo<input type="file" accept="image/jpeg,image/png,image/webp" disabled={photoUploading||busy} onChange={e=>{const f=e.target.files?.[0];if(f)void uploadPhoto(f,selected);e.target.value="";}}/></label></div>{selected.mode==="bulk"&&<div className="inv-inline"><label>Receber mais unidades<input type="number" min="1" step="1" value={qty} onChange={e=>setQty(e.target.value)}/></label><button disabled={busy} onClick={()=>void move("receive",selected)}><ArrowDownToLine size={16}/> Registrar entrada</button></div>}{selected.mode==="serialized"&&<p className="inv-note">Equipamento individual: uma única unidade por série. Para outra unidade, crie um novo cadastro.</p>}<p className="inv-note">Para usar esta peça numa OS, abra a OS em Laboratório → Materiais → Retirar do estoque. O custo será vinculado automaticamente.</p><h3>Histórico de movimentações</h3><div className="inv-history">{itemMovements.map(m=><div key={m.id}><strong>{m.kind==="issue"?"Saída":m.kind==="return"?"Devolução":"Entrada"}</strong> · {m.quantity} {selected.unit} {m.work_order_id?`· OS #${m.work_order_id}`:""}<small>{new Date(m.created_at).toLocaleString("pt-BR")}</small></div>)}</div><h3>Histórico de localização</h3><div className="inv-history">{itemLocations.map(h=><div key={h.id}><strong>{h.from||"Sem local"} → {h.to||"Sem local"}</strong><small>{new Date(h.created_at).toLocaleString("pt-BR")}</small></div>)}</div><footer><button onClick={()=>window.open(`/api/inventory/items/${selected.id}/label.pdf`,"_blank","noopener,noreferrer")}><Printer size={15}/> Etiqueta PDF</button><button onClick={()=>setSelected(null)}>Fechar</button></footer></section></div>}
    {cameraTarget && <CameraCapture
      title={cameraTarget === "form" ? "Fotografar item do estoque" : `Fotografar ${selected?.name ?? "item"}`}
      onClose={() => setCameraTarget(null)}
      onCapture={(file) => {
        const target = cameraTarget;
        setCameraTarget(null);
        if (target === "form") {
          setPendingPhoto(file);
        } else if (target === "details" && selected) {
          void uploadPhoto(file, selected);
        }
      }}
    />}
    </main>
  </div>;
}
