import { createContext, useContext, useEffect, useState } from "react";
import { Link, Navigate, NavLink, Outlet, Route, Routes, useNavigate } from "react-router-dom";
import AnalyzePage from "./pages/AnalyzePage";
import AnalysisDetailPage from "./pages/AnalysisDetailPage";
import DashboardPage from "./pages/DashboardPage";
import HistoryPage from "./pages/HistoryPage";
import LoginPage from "./pages/LoginPage";
import SettingsPage from "./pages/SettingsPage";
import LanguageSwitcher from "./components/LanguageSwitcher";
import { useTranslation } from "./i18n";
import { clearToken, getMe, hasToken, refreshToken, saveToken } from "./services/api";

interface AuthState {
  userId: number | null;
  username: string | null;
  authed: boolean;
}

const AuthContext = createContext<{
  auth: AuthState;
  setAuth: (s: AuthState) => void;
  logout: () => void;
}>({
  auth: { userId: null, username: null, authed: false },
  setAuth: () => {},
  logout: () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

function AuthProvider({ children }: { children: React.ReactNode }) {
  const [auth, setAuth] = useState<AuthState>({ userId: null, username: null, authed: hasToken() });
  const navigate = useNavigate();

  useEffect(() => {
    if (!auth.authed || auth.userId) return;
    getMe()
      .then((user) => setAuth({ userId: user.id, username: user.username, authed: true }))
      .catch(async () => {
        try {
          const res = await refreshToken();
          saveToken(res.access_token);
          const user = await getMe();
          setAuth({ userId: user.id, username: user.username, authed: true });
        } catch {
          clearToken();
          setAuth({ userId: null, username: null, authed: false });
        }
      });
  }, [auth.authed, auth.userId]);

  function logout() {
    clearToken();
    setAuth({ userId: null, username: null, authed: false });
    navigate("/login");
  }

  return <AuthContext.Provider value={{ auth, setAuth, logout }}>{children}</AuthContext.Provider>;
}

function ProtectedRoute() {
  const { auth } = useAuth();
  if (!auth.authed) return <Navigate to="/login" replace />;
  return <AppShell />;
}

function AppShell() {
  const { logout } = useAuth();
  const { t } = useTranslation();

  return (
    <div className="layout">
      <aside className="sidebar">
        <h1>AlphaPilot</h1>
        <nav>
          <NavLink to="/" end>{t("nav.dashboard")}</NavLink>
          <NavLink to="/analyze">{t("nav.analyze")}</NavLink>
          <NavLink to="/history">{t("nav.history")}</NavLink>
          <NavLink to="/settings">{t("nav.settings")}</NavLink>
        </nav>
        <div className="sidebar-footer">
          <LanguageSwitcher />
          <button className="btn ghost" onClick={logout}>
            {t("nav.logout")}
          </button>
        </div>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<LoginPage defaultMode="register" />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/analyze" element={<AnalyzePage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/history/:id" element={<AnalysisDetailPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}
