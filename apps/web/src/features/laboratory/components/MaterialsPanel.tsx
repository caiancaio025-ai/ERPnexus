import { useEffect, useMemo, useState } from "react";
import { ExternalLink, PackagePlus, RefreshCw, ShoppingCart, Truck } from "lucide-react";

import { apiClient } from "../../../shared/api/apiClient";
import type { MaterialRequest, MaterialRequestStatus, Priority } from "../types";

const statusLabels: Record<MaterialRequestStatus, string> = {
  awaiting_approval: "Aguardando aprovação",
  approved: "Aprovado",
  rejected: "Reprovado",
  purchasing: "Em compras",
  purchased: "Comprado",
  in_transit: "Em trânsito",
  received: "Recebido",
  delivered_to_lab: "Entregue ao laboratório",
  cancelled: "Cancelado",
};

function blocker(items: MaterialRequest[]) {
  const open = items.filter((item) => !["delivered_to_lab", "cancelled", "rejected"].includes(item.status));
  if (!open.length) return { tone: "ok", title: "Sem bloqueio de material", detail: "Nenhuma peça pendente nesta O.S." };
  if (open.some((item) => item.status === "awaiting_approval")) return { tone: "warn", title: "Aguardando aprovação", detail: `${open.filter((i) => i.status === "awaiting_approval").length} solicitação(ões) precisa(m) de aprovação.` };
  if (open.some((item) => ["approved", "purchasing"].includes(item.status))) return { tone: "warn", title: "Aguardando compras", detail: "Há material aprovado ainda não comprado." };
  if (open.some((item) => ["purchased", "in_transit"].includes(item.status))) return { tone: "info", title: "Aguardando peças", detail: "Material comprado e aguardando recebimento." };
  if (open.some((item) => item.status === "received")) return { tone: "ok", title: "Material recebido", detail: "Peça recebida e aguardando entrega ao laboratório." };
  return { tone: "info", title: "Pendência de material", detail: "Existe uma solicitação em andamento." };
}

export function MaterialsPanel({ workOrderId }: { workOrderId: number }) {
  const [items, setItems] = useState<MaterialRequest[]>([]);
  const [itemName, setItemName] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [priority, setPriority] = useState<Priority>("normal");
  const [technicalNote, setTechnicalNote] = useState("");
  const [suggestedLink, setSuggestedLink] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    try {
      setItems(await apiClient.get<MaterialRequest[]>(`/laboratory/work-orders/${workOrderId}/materials`));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Falha ao carregar materiais.");
    }
  }

  useEffect(() => { void load(); }, [workOrderId]);
  const currentBlocker = useMemo(() => blocker(items), [items]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!itemName.trim()) return;
    setSaving(true); setError("");
    try {
      await apiClient.post(`/laboratory/work-orders/${workOrderId}/materials`, {
        item_name: itemName.trim(), quantity: Number(quantity), priority,
        technical_note: technicalNote.trim() || null, suggested_link: suggestedLink.trim() || null,
      });
      setItemName(""); setQuantity("1"); setTechnicalNote(""); setSuggestedLink(""); setPriority("normal");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível criar a solicitação.");
    } finally { setSaving(false); }
  }

  return <div className="lab-materials">
    <div className={`lab-material-blocker ${currentBlocker.tone}`}>
      <div><strong>{currentBlocker.title}</strong><span>{currentBlocker.detail}</span></div>
      <button onClick={() => void load()} title="Atualizar"><RefreshCw size={16} /></button>
    </div>

    <form className="lab-material-form" onSubmit={submit}>
      <div className="lab-material-form-title"><PackagePlus size={18} /><div><strong>Solicitar material</strong><span>A solicitação entra automaticamente na fila de Compras.</span></div></div>
      <div className="lab-material-grid">
        <label className="wide">Peça / componente<input required value={itemName} onChange={(e) => setItemName(e.target.value)} placeholder="Ex.: IGBT FS450R12KE4" /></label>
        <label>Qtd.<input type="number" min="1" value={quantity} onChange={(e) => setQuantity(e.target.value)} /></label>
        <label>Prioridade<select value={priority} onChange={(e) => setPriority(e.target.value as Priority)}><option value="low">Baixa</option><option value="normal">Normal</option><option value="high">Alta</option><option value="urgent">Urgente</option></select></label>
        <label className="wide">Observação técnica<textarea rows={3} value={technicalNote} onChange={(e) => setTechnicalNote(e.target.value)} placeholder="Motivo da substituição, especificação, referência..." /></label>
        <label className="wide">Link sugerido<input value={suggestedLink} onChange={(e) => setSuggestedLink(e.target.value)} placeholder="https://..." /></label>
      </div>
      {error && <div className="lab-material-error">{error}</div>}
      <button className="lab-material-submit" disabled={saving}>{saving ? "Enviando..." : "Enviar para aprovação"}</button>
    </form>

    <div className="lab-material-list">
      {items.map((item) => <article key={item.id}>
        <div className="lab-material-main"><div className="lab-material-code">{item.code}</div><strong>{item.item_name}</strong><span>{item.quantity} un. · solicitado por {item.requester_name}</span>{item.technical_note && <p>{item.technical_note}</p>}</div>
        <div className="lab-material-meta">
          <span className={`material-status ${item.status}`}>{statusLabels[item.status]}</span>
          {item.supplier_name && <small><ShoppingCart size={13} />{item.supplier_name}</small>}
          {item.expected_delivery_date && <small><Truck size={13} />Prev. {new Date(`${item.expected_delivery_date}T12:00:00`).toLocaleDateString("pt-BR")}</small>}
          {item.purchase_reference && <small>Compra: {item.purchase_reference}</small>}
          {item.purchase_link && <a href={item.purchase_link} target="_blank" rel="noreferrer"><ExternalLink size={13} />Abrir compra</a>}
        </div>
      </article>)}
      {!items.length && <div className="lab-empty">Nenhum material solicitado para esta O.S.</div>}
    </div>
  </div>;
}
