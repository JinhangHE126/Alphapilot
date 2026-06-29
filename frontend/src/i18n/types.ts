export type Locale = "en" | "zh-Hans" | "yue";

export const LOCALES: Locale[] = ["en", "zh-Hans", "yue"];

export const LOCALE_STORAGE_KEY = "alphapilot-locale";

export const DATE_LOCALES: Record<Locale, string> = {
  en: "en-US",
  "zh-Hans": "zh-CN",
  yue: "zh-HK",
};

export type TranslationDict = {
  nav: {
    dashboard: string;
    analyze: string;
    history: string;
    settings: string;
    logout: string;
  };
  language: {
    label: string;
    en: string;
    zhHans: string;
    yue: string;
  };
  common: {
    loading: string;
    back: string;
    delete: string;
    view: string;
    yes: string;
    no: string;
    score: string;
    prev: string;
    next: string;
    pageOf: string;
  };
  errors: {
    loadDashboard: string;
    loadHistory: string;
    loadProfile: string;
    saveProfile: string;
    loadDetail: string;
    deleteFailed: string;
    analyzeFailed: string;
    authFailed: string;
  };
  login: {
    signInSubtitle: string;
    registerSubtitle: string;
    username: string;
    displayName: string;
    password: string;
    processing: string;
    signIn: string;
    createAccount: string;
    needAccount: string;
    haveAccount: string;
  };
  dashboard: {
    greetingMorning: string;
    greetingNoon: string;
    greetingAfternoon: string;
    greetingEvening: string;
    commander: string;
    newAnalysis: string;
    overview: string;
    overviewSubtitle: string;
    totalAnalyses: string;
    totalAnalysesSub: string;
    symbolsAnalyzed: string;
    symbolsAnalyzedSub: string;
    avgConfidence: string;
    avgConfidenceSub: string;
    lastAnalysis: string;
    lastAnalysisSub: string;
    recentAnalyses: string;
    emptyTitle: string;
    emptyDesc: string;
    startFirst: string;
    listScore: string;
  };
  analyze: {
    title: string;
    subtitle: string;
    badge: string;
    researchInput: string;
    stockSymbol: string;
    stockPlaceholder: string;
    researchPrompt: string;
    promptPlaceholder: string;
    defaultPrompt: string;
    analyzing: string;
    startAnalysis: string;
    agentCollab: string;
    agentCollabSub: string;
    coreAgents: string;
    coreAgentsSub: string;
    enhancementAgents: string;
    enhancementAgentsSub: string;
    systemPipeline: string;
    statusAnalyzing: string;
    statusComplete: string;
    statusStandby: string;
    statusError: string;
    statusSkipped: string;
    descStandingBy: string;
    descReady: string;
    finalReport: string;
    emptyTitle: string;
    emptyDesc: string;
    inProgress: string;
    recommendation: string;
    guardTitle: string;
    guardPass: string;
    guardFail: string;
    guardConfidence: string;
    guardValid: string;
    guardIssues: string;
    guardCorrections: string;
    guardSources: string;
    guardReasoning: string;
    sessionTitle: string;
    clickToView: string;
    skippedHint: string;
    agentDetail: string;
    noOutput: string;
    closeDetail: string;
    agents: {
      market_data_expert: { label: string; role: string };
      fundamental_expert: { label: string; role: string };
      news_sentiment_expert: { label: string; role: string };
      strategy_expert: { label: string; role: string };
      risk_expert: { label: string; role: string };
      guard_agent: { label: string; role: string };
      recommendation_agent: { label: string; role: string };
      portfolio_agent: { label: string; role: string };
      backtesting_agent: { label: string; role: string };
    };
    nodes: {
      evidence_packet_builder: { label: string; role: string };
      orchestrator: { label: string; role: string };
    };
  };
  history: {
    title: string;
    subtitleEmpty: string;
    subtitleWithScore: string;
    filterPlaceholder: string;
    newAnalysis: string;
    emptyTitle: string;
    emptyDesc: string;
    startFirst: string;
    viewReport: string;
    statusDone: string;
  };
  settings: {
    title: string;
    subtitle: string;
    saved: string;
    riskPreference: string;
    riskLow: string;
    riskMedium: string;
    riskHigh: string;
    horizon: string;
    horizonShort: string;
    horizonMedium: string;
    horizonLong: string;
    saving: string;
    saveProfile: string;
  };
  detail: {
    finalScore: string;
    status: string;
    recommendation: string;
    report: string;
    noReport: string;
    eventTimeline: string;
    noEvents: string;
  };
  citations: {
    title: string;
    subtitle: string;
    empty: string;
    noChunks: string;
    chunkCount: string;
    colMarker: string;
    colChunkId: string;
    colSection: string;
    colSource: string;
  };
};
