import { useEffect, useState } from "react";
import { ExternalLink, FileText, Image, Trash2, UploadCloud } from "lucide-react";

import { apiClient } from "../../../shared/api/apiClient";
import "./equipmentDocuments.css";

type LaboratoryDocument = {
  id: number;
  work_order_id: number;
  item_id: number | null;
  category: "entry" | "technical" | "exit" | "general";
  original_name: string;
  mime_type: string;
  size_bytes: number;
  uploaded_by: number;
  created_at: string;
};

export function EquipmentDocumentsPanel({ workOrderId }: { workOrderId: number }) {
  const [documents, setDocuments] = useState<LaboratoryDocument[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      setDocuments(await apiClient.get<LaboratoryDocument[]>(`/laboratory/work-orders/${workOrderId}/documents`));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Falha ao carregar fotos e anexos.");
    }
  }

  useEffect(() => { void load(); }, [workOrderId]);

  async function upload(files: FileList | null) {
    if (!files?.length) return;
    setBusy(true); setError("");
    try {
      for (const file of Array.from(files)) {
        const body = new FormData();
        body.append("file", file);
        await apiClient.post(`/laboratory/work-orders/${workOrderId}/documents?category=entry`, body);
      }
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Falha ao anexar arquivo.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(documentId: number) {
    if (!window.confirm("Excluir este anexo da O.S.?")) return;
    setBusy(true); setError("");
    try {
      await apiClient.delete(`/laboratory/documents/${documentId}`);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Falha ao excluir anexo.");
    } finally {
      setBusy(false);
    }
  }

  const previewUrl = (id: number) => `/api/laboratory/documents/${id}/preview`;

  return <section className="equipment-documents">
    <header className="equipment-documents__header">
      <div>
        <h3><Image size={20} /> Fotos do equipamento</h3>
        <p>Fotos e documentos vinculados somente a esta O.S.</p>
      </div>
      <label className={`equipment-documents__upload ${busy ? "disabled" : ""}`}>
        <UploadCloud size={17} />
        <span>{busy ? "Enviando..." : "Adicionar fotos"}</span>
        <input disabled={busy} type="file" multiple accept="image/jpeg,image/png,image/webp,application/pdf"
          onChange={(event) => { void upload(event.target.files); event.currentTarget.value = ""; }} />
      </label>
    </header>

    {error && <div className="equipment-documents__error">{error}</div>}
    {!documents.length && <div className="equipment-documents__empty">Nenhuma foto ou documento anexado nesta O.S.</div>}

    {!!documents.length && <div className="equipment-documents__grid">
      {documents.map((document) => {
        const isImage = document.mime_type.startsWith("image/");
        return <article className="equipment-document-card" key={document.id}>
          <a className="equipment-document-card__preview" href={previewUrl(document.id)} target="_blank" rel="noreferrer">
            {isImage
              ? <img src={previewUrl(document.id)} alt={document.original_name} loading="lazy" />
              : <div className="equipment-document-card__pdf"><FileText size={38} /><strong>PDF</strong></div>}
          </a>
          <div className="equipment-document-card__meta">
            <strong title={document.original_name}>{document.original_name}</strong>
            <span>{formatBytes(document.size_bytes)} · {new Date(document.created_at).toLocaleString("pt-BR")}</span>
          </div>
          <div className="equipment-document-card__actions">
            <a href={previewUrl(document.id)} target="_blank" rel="noreferrer"><ExternalLink size={15} />Abrir</a>
            <button type="button" disabled={busy} onClick={() => void remove(document.id)}><Trash2 size={15} />Excluir</button>
          </div>
        </article>;
      })}
    </div>}
  </section>;
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
