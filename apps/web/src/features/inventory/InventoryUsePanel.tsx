import { stockIdFromSearch } from "./stockCode";
import { useEffect, useMemo, useState } from "react";
import { Boxes, CornerUpLeft, Search, PackageCheck, RefreshCw, MapPin, Layers3 } from "lucide-react";
import { apiClient } from "../../shared/api/apiClient";
import type { StockItem } from "./InventoryDashboard";

type Movement = { id:number; item_id:number; kind:"issue"|"return"|"receipt"; quantity:number; stock_code:string; item_name:string; manufacturer_serial:string|null; reversal_of_id:number|null; work_order_id:number; created_at:string; unit_cost?:string };
function message(error:unknown) { return error instanceof Error ? error.message : "Falha na operação de estoque."; }

export function InventoryUsePanel({ workOrderId, onMovementChange }: { workOrderId:number; onMovementChange?:()=>Promise<void>|void }) {
  const [items,setItems]=useState<StockItem[]>([]);
  const [movements,setMovements]=useState<Movement[]>([]);
  const [company,setCompany]=useState("");
  const [query,setQuery]=useState("");
  const [selectedId,setSelectedId]=useState("");
  const [qty,setQty]=useState("1");
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [info,setInfo]=useState("");
  async function load() {
    const [order, stock, history]=await Promise.all([
      apiClient.get<{company_code:string}>(`/laboratory/work-orders/${workOrderId}`),
      apiClient.get<StockItem[]>("/inventory/items"),
      apiClient.get<Movement[]>(`/inventory/work-orders/${workOrderId}/movements`),
    ]);
    setCompany(order.company_code);
    setItems(stock.filter(x=>x.company_code===order.company_code&&x.is_active));
    setMovements(history);
  }
  useEffect(()=>{void load().catch(e=>setError(message(e)));},[workOrderId]);
  const choices=useMemo(()=>items.filter(x=>x.quantity>0&&(x.id===stockIdFromSearch(query)||[x.name,x.stock_code,x.manufacturer_serial,x.location_code,x.category].some(t=>t?.toLowerCase().includes(query.toLowerCase())))),[items,query]);
  const selected=items.find(x=>String(x.id)===selectedId);
  const issueMovements=movements.filter(m=>m.kind==="issue");
  function availableToReturn(m:Movement) {return m.quantity-movements.filter(r=>r.kind==="return"&&r.reversal_of_id===m.id).reduce((t,r)=>t+r.quantity,0);}
  async function issue(e:React.FormEvent) {
    e.preventDefault();if(!selected || !Number.isInteger(Number(qty)) || Number(qty)<1 || Number(qty)>selected.quantity || (selected.mode==="serialized" && Number(qty)!==1))return;
    if(!window.confirm(`Retirar ${qty} un. de ${selected.name} (${selected.stock_code}) para esta OS?`))return;
    setBusy(true);setError("");setInfo("");
    try {await apiClient.post(`/inventory/items/${selected.id}/issue`,{work_order_id:workOrderId,quantity:Number(qty)});setInfo("Baixa realizada. Saldo de estoque e custo canônico da OS atualizados.");setSelectedId("");setQty("1");await load();await onMovementChange?.();}
    catch(e){setError(message(e));}finally{setBusy(false);}
  }
  async function returnPart(m:Movement) {
    const max=availableToReturn(m);if(max<=0)return;
    const raw=window.prompt(`Quantas unidades devolver? (máximo ${max})`,String(max));
    if(raw===null)return;
    const n=Number(raw);
    if(!Number.isInteger(n)||n<1||n>max){setError("Quantidade de devolução inválida.");return;}
    setBusy(true);setError("");
    try {await apiClient.post(`/inventory/items/${m.item_id}/return`,{work_order_id:workOrderId,quantity:n,reversal_of_id:m.id});setInfo("Devolução registrada e custo da OS recalculado.");await load();await onMovementChange?.();}
    catch(e){setError(message(e));}finally{setBusy(false);}
  }
  return <section className="lab-stock-picker">
    <div className="lab-material-form-title"><Boxes size={20}/><div><strong>Retirar do estoque</strong><span>Busque por etiqueta, série, componente ou localização. Uma unidade serializada é baixada inteira; componentes descontam apenas a quantidade.</span></div></div>
    {error&&<p className="lab-material-error" role="alert">{error}</p>}{info&&<p className="lab-stock-success" role="status">{info}</p>}
    <form className="lab-material-form" onSubmit={issue}><div className="lab-material-grid">
      <label className="wide">Pesquisar peça <span style={{display:"flex",gap:8,alignItems:"center"}}><Search size={16}/><input value={query} placeholder="IGBT, capacitor, EST-01, série..." onChange={e=>setQuery(e.target.value)}/></span></label>
      <label className="wide">Item disponível ({company})<select required value={selectedId} onChange={e=>{setSelectedId(e.target.value);setQty("1");}}><option value="">Escolha uma peça</option>{choices.map(x=><option value={x.id} key={x.id}>{x.stock_code} · {x.name} {x.manufacturer_serial?`· Série/lote ${x.manufacturer_serial}`:""} · {x.quantity} {x.unit} · {x.location_code||"Sem local"}</option>)}</select></label>
      <label>Quantidade<input required type="number" min="1" max={selected?.mode==="serialized"?1:selected?.quantity||1} step="1" value={qty} onChange={e=>setQty(e.target.value)}/></label>
      <label>Controle<input disabled value={selected?.mode==="serialized"?"Por série — unidade única":"Por quantidade"}/></label>
    </div>{selected && <div className="lab-stock-selected"><div><strong>{selected.name}</strong><small>{selected.stock_code}{selected.manufacturer_serial ? ` · Série ${selected.manufacturer_serial}` : " · Controle por quantidade"}</small></div><span><MapPin size={15}/>{selected.location_code ?? "Local não definido"}</span><span><Layers3 size={15}/>{selected.quantity} {selected.unit} disponíveis</span></div>}
    <button className="lab-material-submit" disabled={busy||!selected||!Number.isInteger(Number(qty))||Number(qty)>selected.quantity||Number(qty)<1||selected.mode==="serialized"&&Number(qty)!==1}><PackageCheck size={17}/> {busy?"Registrando...":"Confirmar baixa na OS"}</button></form>
    <div className="lab-material-list"><h3>Peças vinculadas a esta OS <button type="button" onClick={()=>void load()} title="Atualizar"><RefreshCw size={14}/></button></h3>{!movements.length&&<p>Nenhuma peça retirada do estoque para esta OS.</p>}{movements.map(m=><article key={m.id}><div className="lab-material-main"><div className="lab-material-code">{m.stock_code} · {m.kind==="issue"?"Saída":m.kind==="return"?"Devolução":"Entrada"}</div><strong>{m.item_name}</strong><span>{m.quantity} unidade(s) · {m.manufacturer_serial?`Série/lote ${m.manufacturer_serial}`:"Código fixo do lote"} · {new Date(m.created_at).toLocaleString("pt-BR")}</span></div>{m.kind==="issue"&&availableToReturn(m)>0&&<button type="button" disabled={busy} onClick={()=>void returnPart(m)}><CornerUpLeft size={14}/> Devolver ({availableToReturn(m)})</button>}</article>)}</div>
  </section>;
}
