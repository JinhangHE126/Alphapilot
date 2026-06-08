import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { translations } from "./locales";
import {
  DATE_LOCALES,
  LOCALE_STORAGE_KEY,
  LOCALES,
  type Locale,
  type TranslationDict,
} from "./types";

type Params = Record<string, string | number>;

function getNestedValue(dict: TranslationDict, key: string): string | undefined {
  const parts = key.split(".");
  let current: unknown = dict;
  for (const part of parts) {
    if (!current || typeof current !== "object" || !(part in current)) {
      return undefined;
    }
    current = (current as Record<string, unknown>)[part];
  }
  return typeof current === "string" ? current : undefined;
}

function interpolate(template: string, params?: Params): string {
  if (!params) return template;
  return Object.entries(params).reduce(
    (result, [key, value]) => result.replace(new RegExp(`\\{\\{${key}\\}\\}`, "g"), String(value)),
    template,
  );
}

function detectLocale(): Locale {
  const stored = localStorage.getItem(LOCALE_STORAGE_KEY);
  if (stored && LOCALES.includes(stored as Locale)) {
    return stored as Locale;
  }
  const lang = navigator.language.toLowerCase();
  if (lang.startsWith("zh-hk") || lang.startsWith("zh-hant-hk") || lang === "yue") {
    return "yue";
  }
  if (lang.startsWith("zh")) {
    return "zh-Hans";
  }
  return "en";
}

interface I18nContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: string, params?: Params) => string;
  dateLocale: string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(() => detectLocale());

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    localStorage.setItem(LOCALE_STORAGE_KEY, next);
    document.documentElement.lang = next === "yue" ? "zh-HK" : next;
  }, []);

  const dict = translations[locale];

  const t = useCallback(
    (key: string, params?: Params) => {
      const value = getNestedValue(dict, key) ?? getNestedValue(translations.en, key);
      if (!value) return key;
      return interpolate(value, params);
    },
    [dict],
  );

  const value = useMemo(
    () => ({
      locale,
      setLocale,
      t,
      dateLocale: DATE_LOCALES[locale],
    }),
    [locale, setLocale, t],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useTranslation() {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    throw new Error("useTranslation must be used within I18nProvider");
  }
  return ctx;
}

export function useGreeting(): string {
  const { t } = useTranslation();
  const hour = new Date().getHours();
  if (hour < 12) return t("dashboard.greetingMorning");
  if (hour < 14) return t("dashboard.greetingNoon");
  if (hour < 18) return t("dashboard.greetingAfternoon");
  return t("dashboard.greetingEvening");
}
