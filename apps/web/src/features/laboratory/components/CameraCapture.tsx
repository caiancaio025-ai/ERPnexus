import { useEffect, useRef, useState } from "react";
import { Camera, ImagePlus, RotateCcw, X } from "lucide-react";

import "./cameraCapture.css";

type Props = {
  onCapture: (file: File) => void;
  onClose: () => void;
  title?: string;
};

export function CameraCapture({ onCapture, onClose, title = "Tirar foto" }: Props) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const fallbackInputRef = useRef<HTMLInputElement | null>(null);
  const [error, setError] = useState("");
  const [starting, setStarting] = useState(true);

  async function stopCamera() {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
  }

  async function startCamera() {
    setStarting(true);
    setError("");
    await stopCamera();

    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Este navegador não oferece acesso direto à câmera. Use 'Escolher foto'.");
      setStarting(false);
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          facingMode: { ideal: "environment" },
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
    } catch (reason) {
      const message = reason instanceof DOMException && reason.name === "NotAllowedError"
        ? "Permissão da câmera negada. Libere a câmera no navegador ou use 'Escolher foto'."
        : "Não foi possível abrir a câmera. Verifique se ela está disponível ou use 'Escolher foto'.";
      setError(message);
    } finally {
      setStarting(false);
    }
  }

  useEffect(() => {
    void startCamera();
    return () => { void stopCamera(); };
  }, []);

  async function capture() {
    const video = videoRef.current;
    if (!video || video.videoWidth <= 0 || video.videoHeight <= 0) {
      setError("A câmera ainda não está pronta para capturar a foto.");
      return;
    }

    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext("2d");
    if (!context) {
      setError("Não foi possível preparar a captura da imagem.");
      return;
    }

    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.92));
    if (!blob) {
      setError("Não foi possível gerar o arquivo da foto.");
      return;
    }

    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    const file = new File([blob], `foto-${timestamp}.jpg`, { type: "image/jpeg" });
    await stopCamera();
    onCapture(file);
  }

  return <div className="camera-capture-backdrop" role="dialog" aria-modal="true" aria-label={title}>
    <section className="camera-capture-modal">
      <header>
        <div><Camera size={20} /><strong>{title}</strong></div>
        <button type="button" onClick={onClose} aria-label="Fechar câmera"><X size={20} /></button>
      </header>

      <div className="camera-capture-preview">
        <video ref={videoRef} autoPlay muted playsInline />
        {starting && <div className="camera-capture-message">Abrindo câmera...</div>}
        {!starting && error && <div className="camera-capture-message camera-capture-error">{error}</div>}
      </div>

      <footer>
        <button type="button" className="camera-capture-secondary" onClick={() => fallbackInputRef.current?.click()}>
          <ImagePlus size={17} /> Escolher foto
        </button>
        {error && <button type="button" className="camera-capture-secondary" onClick={() => void startCamera()}>
          <RotateCcw size={17} /> Tentar novamente
        </button>}
        <button type="button" className="camera-capture-primary" disabled={starting || !!error} onClick={() => void capture()}>
          <Camera size={17} /> Capturar foto
        </button>
        <input ref={fallbackInputRef} className="camera-capture-file-input" type="file" accept="image/*" capture="environment" onChange={(event) => {
          const file = event.currentTarget.files?.[0];
          event.currentTarget.value = "";
          if (file) {
            void stopCamera();
            onCapture(file);
          }
        }} />
      </footer>
    </section>
  </div>;
}
