import { useEffect, useMemo, useState } from "react";
import {
  Camera, CheckCircle2, ClipboardCheck, ExternalLink, Image, PackageCheck,
  Paintbrush, Plus, RotateCcw, Send, Trash2, UploadCloud,
} from "lucide-react";

import { apiClient } from "../../../shared/api/apiClient";
import type { PaintingDispatch, PaintingItem } from "../types";
import { ActionButton } from "./ActionButton";
import { CameraCapture } from "./CameraCapture";

type Props = {
  workOrderId: number;
};

const statusLabel: Record<PaintingDispatch["status"], string> = {
  draft: "Preparando saída",
  sent: "Em pintura externa",
  returned: "Retorno conferido",
};

export function MechanicsPanel({ workOrderId }: Props) {
  const [rows, setRows] = useState<PaintingDispatch[]>([]);
  const [provider, setProvider] = useState("");
  const [notes, setNotes] = useState("");
  const [items, setItems] = useState<string[]>([""]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [cameraTarget, setCameraTarget] = useState<{ dispatchId: number; phase: "outbound" | "return" } | null>(null);

  async function load() {
    setError("");
    try {
      setRows(await apiClient.get<PaintingDispatch[]>(`/laboratory/work-orders/${workOrderId}/mechanics/painting`));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Falha ao carregar controles da Mecânica.");
    }
  }

  useEffect(() => { void load(); }, [workOrderId]);

  const activeCount = useMemo(
    () => rows.filter((row) => row.status !== "returned").length,
    [rows],
  );

  async function createDispatch() {
    const cleaned = items.map((item) => item.trim()).filter(Boolean);
    if (!cleaned.length) {
      setError("Informe ao menos uma peça ou parte que seguirá para pintura.");
      return;
    }
    setBusy(true); setError("");
    try {
      await apiClient.post(`/laboratory/work-orders/${workOrderId}/mechanics/painting`, {
        provider: provider.trim() || null,
        notes: notes.trim() || null,
        items: cleaned,
      });
      setProvider("");
      setNotes("");
      setItems([""]);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Falha ao criar controle de pintura.");
    } finally {
      setBusy(false);
    }
  }

  async function upload(dispatchId: number, phase: "outbound" | "return", files: FileList | File[] | null) {
    if (!files?.length) return;
    setBusy(true); setError("");
    try {
      for (const file of Array.from(files)) {
        const body = new FormData();
        body.append("file", file);
        await apiClient.post(`/laboratory/mechanics/painting/${dispatchId}/photos?phase=${phase}`, body);
      }
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Falha ao anexar evidência da pintura.");
    } finally {
      setBusy(false);
    }
  }

  async function send(dispatchId: number) {
    setBusy(true); setError("");
    try {
      await apiClient.post(`/laboratory/mechanics/painting/${dispatchId}/send`, {});
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Falha ao confirmar saída para pintura.");
    } finally {
      setBusy(false);
    }
  }

  async function patchItem(item: PaintingItem, returned: boolean, returnNote = item.return_note || "") {
    setBusy(true); setError("");
    try {
      await apiClient.patch(`/laboratory/mechanics/painting/items/${item.id}`, {
        returned,
        return_note: returnNote.trim() || null,
      });
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Falha ao atualizar conferência de retorno.");
    } finally {
      setBusy(false);
    }
  }

  async function confirmReturn(dispatchId: number) {
    setBusy(true); setError("");
    try {
      await apiClient.post(`/laboratory/mechanics/painting/${dispatchId}/return`, {});
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Falha ao concluir retorno da pintura.");
    } finally {
      setBusy(false);
    }
  }

  const previewUrl = (documentId: number) => `/api/laboratory/documents/${documentId}/preview`;

  return <section className="lab-mechanics">
    <header className="lab-mechanics__hero">
      <div>
        <span className="lab-eyebrow">MECÂNICA</span>
        <h3><Paintbrush size={21} /> Controle de peças em pintura externa</h3>
        <p>Registre exatamente o que saiu, anexe evidência e confira item a item no retorno.</p>
      </div>
      <div className="lab-mechanics__hero-kpi">
        <span>Controles em aberto</span>
        <strong>{activeCount}</strong>
      </div>
    </header>

    {error && <div className="lab-alert">{error}</div>}

    <section className="lab-mechanics__new">
      <div className="lab-grid">
        <label>Empresa / pintor externo
          <input value={provider} placeholder="Opcional" onChange={(e) => setProvider(e.target.value)} />
        </label>
        <label>Observações da saída
          <input value={notes} placeholder="Cor, acabamento, orientação..." onChange={(e) => setNotes(e.target.value)} />
        </label>
      </div>

      <div className="lab-mechanics__checklist-builder">
        <div className="lab-mechanics__section-title">
          <div><ClipboardCheck size={18} /><strong>Checklist do que vai sair</strong></div>
          <ActionButton variant="secondary" icon={<Plus size={15} />} onClick={() => setItems([...items, ""])}>Adicionar item</ActionButton>
        </div>
        {items.map((item, index) => <div key={index} className="lab-mechanics__item-input">
          <span>{index + 1}</span>
          <input
            value={item}
            placeholder="Ex.: tampa frontal, flange, carcaça, suporte..."
            onChange={(e) => {
              const next = [...items];
              next[index] = e.target.value;
              setItems(next);
            }}
          />
          <button
            type="button"
            aria-label="Remover item"
            disabled={items.length === 1}
            onClick={() => setItems(items.filter((_, itemIndex) => itemIndex !== index))}
          ><Trash2 size={16} /></button>
        </div>)}
      </div>

      <div className="lab-mechanics__create-actions">
        <small>Depois de criar o controle, anexe ao menos uma foto antes de confirmar a saída.</small>
        <ActionButton loading={busy} icon={<Plus size={17} />} onClick={() => void createDispatch()}>Criar controle de pintura</ActionButton>
      </div>
    </section>

    {!rows.length && <div className="lab-empty">Nenhuma saída para pintura registrada nesta O.S.</div>}

    <div className="lab-mechanics__dispatches">
      {rows.map((row) => {
        const outboundPhotos = row.photos.filter((photo) => photo.phase === "outbound");
        const returnPhotos = row.photos.filter((photo) => photo.phase === "return");
        const pendingItems = row.items.filter((item) => !item.returned).length;
        return <article key={row.id} className={`lab-paint-card ${row.status}`}>
          <header>
            <div>
              <span className={`lab-paint-status ${row.status}`}>{statusLabel[row.status]}</span>
              <strong>Saída #{row.id}</strong>
              <small>
                Criado por {row.created_by_name} · {new Date(row.created_at).toLocaleString("pt-BR")}
              </small>
            </div>
            {row.provider && <div className="lab-paint-provider"><span>Destino</span><strong>{row.provider}</strong></div>}
          </header>

          {row.notes && <p className="lab-paint-notes">{row.notes}</p>}

          <div className="lab-paint-items">
            <div className="lab-mechanics__section-title">
              <div><PackageCheck size={17} /><strong>Peças / partes</strong></div>
              <small>{row.items.length} item(ns)</small>
            </div>
            {row.items.map((item) => <div key={item.id} className={`lab-paint-item ${item.returned ? "returned" : ""}`}>
              {row.status === "sent"
                ? <input
                    type="checkbox"
                    checked={item.returned}
                    disabled={busy}
                    onChange={(e) => void patchItem(item, e.target.checked)}
                  />
                : <CheckCircle2 size={17} className={item.returned ? "ok" : ""} />}
              <div>
                <strong>{item.description}</strong>
                {row.status === "sent" && <input
                  className="lab-paint-return-note"
                  defaultValue={item.return_note || ""}
                  placeholder="Observação no retorno (opcional)"
                  onBlur={(e) => {
                    if ((item.return_note || "") !== e.target.value) void patchItem(item, item.returned, e.target.value);
                  }}
                />}
                {item.returned_at && <small>Conferido em {new Date(item.returned_at).toLocaleString("pt-BR")}</small>}
              </div>
            </div>)}
          </div>

          <PhotoBlock
            title="Evidência da saída"
            photos={outboundPhotos}
            previewUrl={previewUrl}
            busy={busy}
            disabled={row.status !== "draft"}
            onFiles={(files) => void upload(row.id, "outbound", files)}
            onCamera={() => setCameraTarget({ dispatchId: row.id, phase: "outbound" })}
          />

          {row.status !== "draft" && <div className="lab-paint-trace">
            <Send size={16} />
            <span>Enviado em <strong>{row.sent_at ? new Date(row.sent_at).toLocaleString("pt-BR") : "—"}</strong>{row.sent_by_name ? ` · por ${row.sent_by_name}` : ""}</span>
          </div>}

          {row.status === "sent" && <>
            <PhotoBlock
              title="Foto do retorno (opcional)"
              photos={returnPhotos}
              previewUrl={previewUrl}
              busy={busy}
              onFiles={(files) => void upload(row.id, "return", files)}
              onCamera={() => setCameraTarget({ dispatchId: row.id, phase: "return" })}
            />
            <div className="lab-paint-return-actions">
              <div>
                <strong>Conferência de retorno</strong>
                <span>{pendingItems ? `${pendingItems} item(ns) ainda não conferidos.` : "Todos os itens conferidos."}</span>
              </div>
              <ActionButton
                disabled={pendingItems > 0}
                loading={busy}
                icon={<RotateCcw size={17} />}
                onClick={() => void confirmReturn(row.id)}
              >Confirmar retorno completo</ActionButton>
            </div>
          </>}

          {row.status === "draft" && <div className="lab-paint-send-actions">
            <div>
              <strong>Pronto para sair?</strong>
              <span>{outboundPhotos.length ? `${outboundPhotos.length} foto(s) anexada(s).` : "Anexe ao menos uma foto do material."}</span>
            </div>
            <ActionButton
              className="lab-paint-confirm-button"
              disabled={!outboundPhotos.length}
              loading={busy}
              icon={<Send size={17} />}
              onClick={() => void send(row.id)}
            >Confirmar saída para pintura</ActionButton>
          </div>}

          {row.status === "returned" && <div className="lab-paint-returned">
            <CheckCircle2 size={18} />
            <div>
              <strong>Retorno integralmente conferido</strong>
              <span>{row.returned_at ? new Date(row.returned_at).toLocaleString("pt-BR") : "—"}{row.returned_by_name ? ` · por ${row.returned_by_name}` : ""}</span>
            </div>
          </div>}
        </article>;
      })}
    </div>

    {cameraTarget && <CameraCapture
      title={cameraTarget.phase === "outbound" ? "Foto do material saindo para pintura" : "Foto do material retornando da pintura"}
      onClose={() => setCameraTarget(null)}
      onCapture={(file) => {
        const target = cameraTarget;
        setCameraTarget(null);
        void upload(target.dispatchId, target.phase, [file]);
      }}
    />}
  </section>;
}

function PhotoBlock({
  title, photos, previewUrl, busy, disabled = false, onFiles, onCamera,
}: {
  title: string;
  photos: PaintingDispatch["photos"];
  previewUrl: (documentId: number) => string;
  busy: boolean;
  disabled?: boolean;
  onFiles: (files: FileList | File[] | null) => void;
  onCamera: () => void;
}) {
  return <section className="lab-paint-photos">
    <div className="lab-mechanics__section-title">
      <div><Image size={17} /><strong>{title}</strong></div>
      <div className="lab-paint-photo-actions">
        <label className={`lab-paint-upload ${(busy || disabled) ? "disabled" : ""}`}>
          <UploadCloud size={15} /> Anexar foto
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            multiple
            disabled={busy || disabled}
            onChange={(event) => { onFiles(event.target.files); event.currentTarget.value = ""; }}
          />
        </label>
        <button type="button" className="lab-paint-upload" disabled={busy || disabled} onClick={onCamera}><Camera size={15} /> Tirar foto</button>
      </div>
    </div>
    {!photos.length && <div className="lab-paint-no-photo">Nenhuma foto anexada.</div>}
    {!!photos.length && <div className="lab-paint-photo-grid">
      {photos.map((photo) => <a key={photo.id} href={previewUrl(photo.document_id)} target="_blank" rel="noreferrer">
        <img src={previewUrl(photo.document_id)} alt={photo.original_name} loading="lazy" />
        <span><ExternalLink size={13} /> {photo.original_name}</span>
      </a>)}
    </div>}
  </section>;
}
