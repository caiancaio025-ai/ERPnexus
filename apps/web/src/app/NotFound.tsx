import { ArrowLeft, SearchX } from "lucide-react";
import { motion } from "motion/react";
import { useNavigate } from "react-router-dom";

import "./module-placeholder.css";

export function NotFound() {
  const navigate = useNavigate();

  return (
    <main className="module-placeholder-shell">
      <motion.section
        className="module-placeholder-card"
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.28, ease: "easeOut" }}
      >
        <span className="module-placeholder-icon"><SearchX size={30} /></span>
        <p>ROTA NÃO ENCONTRADA</p>
        <h1>Página indisponível</h1>
        <span>O endereço acessado não existe ou ainda não foi liberado no NEXUS.</span>
        <div className="module-placeholder-status">Erro 404 · nenhuma informação foi alterada</div>
        <motion.button
          type="button"
          onClick={() => navigate("/painel")}
          whileHover={{ x: -2 }}
          whileTap={{ scale: 0.97 }}
        >
          <ArrowLeft size={18} /> Voltar ao painel
        </motion.button>
      </motion.section>
    </main>
  );
}
