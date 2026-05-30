import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { login, register, saveToken } from "../services/api";
import { useAuth } from "../App";

type Props = {
  defaultMode?: "login" | "register";
};

export default function LoginPage({ defaultMode = "login" }: Props) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [mode, setMode] = useState<"login" | "register">(defaultMode);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { setAuth } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const response =
        mode === "login"
          ? await login(username, password)
          : await register(username, password, displayName);
      saveToken(response.access_token);
      setAuth({ userId: response.user_id || null, username: response.username || username, authed: true });
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-layout">
      <form className="card auth-card" onSubmit={handleSubmit}>
        <h1>AlphaPilot</h1>
        <p className="muted">{mode === "login" ? "Sign in to your account" : "Create a new account"}</p>
        <label>
          Username
          <input value={username} onChange={(e) => setUsername(e.target.value)} required minLength={3} />
        </label>
        {mode === "register" && (
          <label>
            Display Name
            <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
          </label>
        )}
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
          />
        </label>
        {error ? <div className="error">{error}</div> : null}
        <button className="btn primary" disabled={loading}>
          {loading ? "Processing..." : mode === "login" ? "Sign in" : "Create account"}
        </button>
        {mode === "login" ? (
          <Link to="/register" className="btn ghost" style={{ textAlign: "center" }}>
            Need an account? Register
          </Link>
        ) : (
          <Link to="/login" className="btn ghost" style={{ textAlign: "center" }}>
            Already have an account? Sign in
          </Link>
        )}
      </form>
    </div>
  );
}
