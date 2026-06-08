import { FormEvent, useEffect, useState } from "react";
import { useTranslation } from "../i18n";
import { getProfile, updateProfile } from "../services/api";

export default function SettingsPage() {
  const { t } = useTranslation();
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
      .catch((err) => setError(err instanceof Error ? err.message : t("errors.loadProfile")))
      .finally(() => setLoading(false));
  }, [t]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    setSaved(false);
    try {
      await updateProfile({ risk_preference: riskPreference, horizon });
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("errors.saveProfile"));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="page">
        <section className="card">
          <p className="muted">{t("common.loading")}</p>
        </section>
      </div>
    );
  }

  return (
    <div className="page">
      <section className="card">
        <h2>{t("settings.title")}</h2>
        <p className="muted">{t("settings.subtitle")}</p>
        {error ? <div className="error">{error}</div> : null}
        {saved ? <div className="success">{t("settings.saved")}</div> : null}
      </section>

      <section className="card">
        <form onSubmit={handleSubmit} className="form-grid">
          <label>
            {t("settings.riskPreference")}
            <select value={riskPreference} onChange={(e) => setRiskPreference(e.target.value)}>
              <option value="low">{t("settings.riskLow")}</option>
              <option value="medium">{t("settings.riskMedium")}</option>
              <option value="high">{t("settings.riskHigh")}</option>
            </select>
          </label>

          <label>
            {t("settings.horizon")}
            <select value={horizon} onChange={(e) => setHorizon(e.target.value)}>
              <option value="short">{t("settings.horizonShort")}</option>
              <option value="medium">{t("settings.horizonMedium")}</option>
              <option value="long">{t("settings.horizonLong")}</option>
            </select>
          </label>

          <button className="btn primary" type="submit" disabled={saving}>
            {saving ? t("settings.saving") : t("settings.saveProfile")}
          </button>
        </form>
      </section>
    </div>
  );
}
