import type { Locale, TranslationDict } from "../types";
import { en } from "./en";
import { zhHans } from "./zh-Hans";
import { yue } from "./yue";

export const translations: Record<Locale, TranslationDict> = {
  en,
  "zh-Hans": zhHans,
  yue,
};

export { en, zhHans, yue };
