import { lazy, Suspense } from "react";
import { BarChart3, FlaskConical, Package, ShoppingCart, UsersRound } from "lucide-react";
import { Navigate, Route, Routes } from "react-router-dom";

import type { AuthUser } from "../../features/auth/AuthCard";
import { AuthCard } from "../../features/auth/AuthCard";
import { NotFound } from "../NotFound";
import { ProtectedRoute } from "./ProtectedRoute";
import { PublicRoute } from "./PublicRoute";

const Dashboard = lazy(() =>
  import("../../features/dashboard/Dashboard").then((module) => ({ default: module.Dashboard })),
);
const CustomerMaster = lazy(() =>
  import("../../features/customers/CustomerMaster").then((module) => ({ default: module.CustomerMaster })),
);
const CommercialDashboard = lazy(() =>
  import("../../features/commercial/CommercialDashboard").then((module) => ({ default: module.CommercialDashboard })),
);
const FinanceDashboard = lazy(() =>
  import("../../features/finance/FinanceDashboard").then((module) => ({ default: module.FinanceDashboard })),
);
const PurchasingDashboard = lazy(() =>
  import("../../features/purchasing/PurchasingDashboard").then((module) => ({ default: module.PurchasingDashboard })),
);
const LaboratoryDashboard = lazy(() =>
  import("../../features/laboratory/LaboratoryDashboard").then((module) => ({ default: module.LaboratoryDashboard })),
);
const InventoryDashboard = lazy(() =>
  import("../../features/inventory/InventoryDashboard").then((module) => ({ default: module.InventoryDashboard })),
);
const EmployeeDashboard = lazy(() =>
  import("../../features/employees/EmployeeDashboard").then((module) => ({ default: module.EmployeeDashboard })),
);

function RouteFallback() {
  return <main className="loading-screen">Carregando módulo...</main>;
}

type AppRouterProps = {
  user: AuthUser | null;
  onLogin: (user: AuthUser) => void;
  onLogout: () => void;
};

const loginModules = [
  { label: "Financeiro", icon: BarChart3 },
  { label: "Laboratório", icon: FlaskConical },
  { label: "Estoque", icon: Package },
  { label: "Compras", icon: ShoppingCart },
  { label: "Comercial", icon: UsersRound },
];

function LoginPage({ onLogin }: { onLogin: (user: AuthUser) => void }) {
  return (
    <main className="login-page">
      <div className="login-page__image" aria-hidden="true" />
      <div className="login-page__shade" aria-hidden="true" />

      <section className="login-story" aria-labelledby="page-title">
        <header className="login-brand">
          <img
            className="login-brand__logo"
            src="/branding/sentico-logo-horizontal.png"
            alt="SÊNTICO ERP"
            decoding="async"
          />
          <span className="login-brand__company">Universo Eletrônica Industrial</span>
        </header>

        <div className="login-kicker"><i />GESTÃO OPERACIONAL INTEGRADA</div>

        <h1 id="page-title">
          <span>Operação</span>
          <strong>conectada,</strong>
          <span>segura e rastreável.</span>
        </h1>

        <p className="login-description">ERP para financeiro, laboratório, estoque, compras e comercial.</p>

        <div className="login-modules" aria-label="Módulos integrados">
          {loginModules.map(({ label, icon: Icon }) => (
            <span key={label}><Icon size={17} aria-hidden="true" />{label}</span>
          ))}
        </div>

      </section>

      <AuthCard onLogin={onLogin} />
      <footer className="login-legal" aria-label="Informações legais do SÊNTICO">
        <span>© {new Date().getFullYear()} <strong>SÊNTICO®</strong> · Todos os direitos reservados.</span>
        <span className="login-legal__separator" aria-hidden="true" />
        <span>Plataforma de gestão corporativa · Acesso restrito</span>
      </footer>
    </main>
  );
}

export function AppRouter({ user, onLogin, onLogout }: AppRouterProps) {
  const authenticated = Boolean(user);
  const canAccessFinance = Boolean(user && ["gestao", "super_admin"].includes(user.role));

  return (
    <Suspense fallback={<RouteFallback />}>
      <Routes>
        <Route element={<PublicRoute authenticated={authenticated} />}>
          <Route path="/login" element={<LoginPage onLogin={onLogin} />} />
        </Route>

        <Route element={<ProtectedRoute authenticated={authenticated} />}>
          <Route path="/painel" element={<Dashboard user={user!} onLogout={onLogout} />} />
          <Route path="/clientes/*" element={<CustomerMaster user={user!} onLogout={onLogout} />} />
          <Route path="/financeiro/*" element={canAccessFinance ? <FinanceDashboard user={user!} onLogout={onLogout} /> : <Navigate to="/painel" replace />} />
          <Route path="/compras/*" element={<PurchasingDashboard user={user!} onLogout={onLogout} />} />
          <Route path="/laboratorio/*" element={<LaboratoryDashboard user={user!} onLogout={onLogout} />} />
          <Route path="/colaboradores/*" element={<EmployeeDashboard user={user!} onLogout={onLogout} />} />
          <Route path="/estoque/*" element={<InventoryDashboard user={user!} onLogout={onLogout} />} />
          <Route path="/comercial/*" element={<CommercialDashboard user={user!} onLogout={onLogout} />} />
          <Route path="*" element={<NotFound />} />
        </Route>

        <Route path="/" element={<Navigate to={authenticated ? "/painel" : "/login"} replace />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </Suspense>
  );
}
