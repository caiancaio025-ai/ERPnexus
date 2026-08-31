import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import type { AuthUser } from "../../features/auth/AuthCard";
import { AuthCard } from "../../features/auth/AuthCard";
import { ModulePlaceholder } from "../ModulePlaceholder";
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

function LoginPage({ onLogin }: { onLogin: (user: AuthUser) => void }) {
  return (
    <main className="page-shell">
      <section className="brand-copy" aria-labelledby="page-title">
        <p className="eyebrow">NEXUS ENTERPRISE</p>
        <h1 id="page-title">Operação conectada, segura e rastreável.</h1>
        <p>ERP para financeiro, laboratório, estoque, compras e comercial.</p>
      </section>
      <AuthCard onLogin={onLogin} />
    </main>
  );
}

export function AppRouter({ user, onLogin, onLogout }: AppRouterProps) {
  const authenticated = Boolean(user);

  return (
    <Suspense fallback={<RouteFallback />}>
      <Routes>
        <Route element={<PublicRoute authenticated={authenticated} />}>
          <Route path="/login" element={<LoginPage onLogin={onLogin} />} />
        </Route>

        <Route element={<ProtectedRoute authenticated={authenticated} />}>
          <Route path="/painel" element={<Dashboard user={user!} onLogout={onLogout} />} />
          <Route path="/clientes/*" element={<CustomerMaster user={user!} onLogout={onLogout} />} />
          <Route path="/financeiro/*" element={<FinanceDashboard user={user!} onLogout={onLogout} />} />
          <Route path="/compras/*" element={<PurchasingDashboard user={user!} onLogout={onLogout} />} />
          <Route path="/laboratorio/*" element={<LaboratoryDashboard user={user!} onLogout={onLogout} />} />
          <Route path="/colaboradores/*" element={<EmployeeDashboard user={user!} onLogout={onLogout} />} />
          <Route path="/estoque/*" element={<ModulePlaceholder />} />
          <Route path="/comercial/*" element={<CommercialDashboard user={user!} onLogout={onLogout} />} />
          <Route path="*" element={<NotFound />} />
        </Route>

        <Route path="/" element={<Navigate to={authenticated ? "/painel" : "/login"} replace />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </Suspense>
  );
}
