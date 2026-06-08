import { Languages } from "lucide-react";
import { useId } from "react";
import { LOCALES, type Locale, useTranslation } from "../i18n";

const LOCALE_LABEL_KEYS: Record<Locale, "language.en" | "language.zhHans" | "language.yue"> = {
  en: "language.en",
  "zh-Hans": "language.zhHans",
  yue: "language.yue",
};

type Props = {
  className?: string;
  variant?: "default" | "compact";
};

export default function LanguageSwitcher({ className = "", variant = "default" }: Props) {
  const { locale, setLocale, t } = useTranslation();
  const selectId = useId();

  const select = (
    <select
      id={selectId}
      value={locale}
      onChange={(e) => setLocale(e.target.value as Locale)}
      aria-label={t("language.label")}
    >
      {LOCALES.map((code) => (
        <option key={code} value={code}>
          {t(LOCALE_LABEL_KEYS[code])}
        </option>
      ))}
    </select>
  );

  if (variant === "compact") {
    return (
      <div className={`language-switcher compact ${className}`.trim()}>
        <Languages size={16} aria-hidden="true" />
        {select}
      </div>
    );
  }

  return (
    <div className={`language-switcher ${className}`.trim()}>
      <label htmlFor={selectId}>{t("language.label")}</label>
      {select}
    </div>
  );
}
