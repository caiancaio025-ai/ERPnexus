import { ArrowLeft, Boxes, FlaskConical, Handshake, PackageOpen } from "lucide-react";
import { motion } from "motion/react";
import { useLocation, useNavigate } from "react-router-dom";

import "./module-placeholder.css";

function content(path: string) {
  if (path.startsWith("/laboratorio/os/nova")) {
    return {
      icon: FlaskConical,
      eyebrow: "ATALHO OPERACIONAL",
      title: "Criar nova OS",
      description:
        "O atalho está conectado à rota correta. O cadastro será liberado quando o módulo Laboratório for implantado.",
    };
  }

  if (path.startsWith("/laboratorio/os")) {
    return {
      icon: Boxes,
      eyebrow: "ATALHO OPERACIONAL",
      title: "Orçamentos de OS",
      description:
        "O atalho está conectado à área de orçamentos. A operação será habilitada junto com o módulo Laboratório.",
    };
  }

  if (path.startsWith("/laboratorio")) {
    return {
      icon: FlaskConical,
      eyebrow: "MÓDULO EM PREPARAÇÃO",
      title: "Laboratório",
      description:
        "A rota do módulo está protegida e pronta para receber ordens de serviço, equipamentos e diagnósticos.",
    };
  }

  if (path.startsWith("/comercial")) {
    return {
      icon: Handshake,
      eyebrow: "MÓDULO EM PREPARAÇÃO",
      title: "Comercial",
      description:
        "A rota do módulo está protegida e pronta para receber clientes, oportunidades e orçamentos comerciais.",
    };
  }

  if (path.startsWith("/estoque/movimentos/sem-nota")) {
    return {
      icon: PackageOpen,
      eyebrow: "ATALHO OPERACIONAL",
      title: "Documento sem nota",
      description:
        "O atalho está conectado à futura movimentação de estoque sem nota. O formulário será habilitado no módulo Estoque.",
    };
  }

  return {
    icon: Boxes,
    eyebrow: "MÓDULO EM PREPARAÇÃO",
    title: "Estoque",
    description:
      "A rota do módulo está protegida e pronta para receber itens, saldos, movimentações e reservas.",
  };
}

export function ModulePlaceholder() {
  const location = useLocation();
  const navigate = useNavigate();
  const item = content(location.pathname);
  const Icon = item.icon;

  return (
    <main className="module-placeholder-shell">
      <motion.section
        className="module-placeholder-card"
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.28, ease: "easeOut" }}
      >
        <span className="module-placeholder-icon"><Icon size={30} /></span>
        <p>{item.eyebrow}</p>
        <h1>{item.title}</h1>
        <span>{item.description}</span>
        <div className="module-placeholder-status">
          Rota funcionando · módulo operacional ainda não implantado
        </div>
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
