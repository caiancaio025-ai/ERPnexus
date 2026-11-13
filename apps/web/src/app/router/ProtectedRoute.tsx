import { Navigate, Outlet, useLocation } from "react-router-dom";

type ProtectedRouteProps = {
  authenticated: boolean;
};

export function ProtectedRoute({ authenticated }: ProtectedRouteProps) {
  const location = useLocation();

  if (!authenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <Outlet />;
}
