import { FormEvent, useEffect, useState } from "react";
import { getProfile, updateProfile } from "../services/api";

export default function SettingsPage() {
  const [riskPreference, setRiskPreference] = useState("medium");
  const [horizon, setHorizon] = useState("medium");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    getProfile()
      .then((profile) => {
        setRiskPreference((profile.risk_preference as string) || "medium");
        setHorizon((profile.horizon as string) || "medium");
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load profile"))
      .finally(() => setLoading(false));
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    setSaved(false);
    try {
      await updateProfile({ risk_preference: riskPreference, horizon });
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save profile");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="page">
        <section className="card">
          <p className="muted">Loading profile...</p>
        </section>
      </div>
    );
  }

  return (
    <div className="page">
      <section className="card">
        <h2>My Profile</h2>
        <p className="muted">Customize your investment preferences for personalized recommendations.</p>
        {error ? <div className="error">{error}</div> : null}
        {saved ? <div className="success">Profile saved successfully.</div> : null}
      </section>

      <section className="card">
        <form onSubmit={handleSubmit} className="form-grid">
          <label>
            Risk Preference
            <select value={riskPreference} onChange={(e) => setRiskPreference(e.target.value)}>
              <option value="low">Low — Conservative, prioritize capital preservation</option>
              <option value="medium">Medium — Balanced growth and safety</option>
              <option value="high">High — Aggressive, maximize returns</option>
            </select>
          </label>

          <label>
            Investment Horizon
            <select value={horizon} onChange={(e) => setHorizon(e.target.value)}>
              <option value="short">Short-term — Days to weeks</option>
              <option value="medium">Medium-term — Weeks to months</option>
              <option value="long">Long-term — Months to years</option>
            </select>
          </label>

          <button className="btn primary" type="submit" disabled={saving}>
            {saving ? "Saving..." : "Save Profile"}
          </button>
        </form>
      </section>
    </div>
  );
}