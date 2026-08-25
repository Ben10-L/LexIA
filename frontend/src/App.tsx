import axios from "axios";
import { FormEvent, KeyboardEvent, useEffect, useLayoutEffect, useRef, useState } from "react";
import lexiaIcon from "./assets/lexia-icon.svg";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000",
  headers: { "Content-Type": "application/json" },
});

type Source = {
  document_title: string;
  article_number: string;
  category: string;
  page_start: number | null;
  page_end: number | null;
  excerpt: string;
};

type ChatLanguage = "fr" | "darija" | "ar";
type ThemeChoice = "system" | "light" | "dark";

type ChatResponse = {
  conversation_id: number;
  assistant_message_id: number;
  question: string;
  answer: string;
  language: ChatLanguage;
  legal_warning: string;
  sources: Source[];
  latency_ms: number;
  confidence: "none" | "low" | "medium" | "high";
  retrieval_method: "none" | "hybrid";
  answer_mode:
    | "greeting"
    | "thanks"
    | "off_topic"
    | "out_of_scope"
    | "structured"
    | "llm"
    | "fallback";
};

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  legalWarning?: string;
  assistantMessageId?: number;
  feedbackRating?: "positive" | "negative";
  feedbackStatus?: "loading" | "success" | "error";
  answerMode?: ChatResponse["answer_mode"];
  latencyMs?: number;
  confidence?: ChatResponse["confidence"];
  retrievalMethod?: ChatResponse["retrieval_method"];
};

type ConversationMessage = {
  id: number;
  role: "user" | "assistant";
  content: string;
  sources: Source[];
  created_at: string;
};

type ConversationDetail = {
  id: number;
  language: ChatLanguage;
  updated_at: string;
  messages: ConversationMessage[];
};

type LocalConversation = {
  id: number;
  title: string;
  updatedAt: string;
};

type StatsResponse = {
  conversations_count: number;
  messages_count: number;
  assistant_messages_count: number;
  user_messages_count: number;
  feedback_count: number;
  positive_feedback_count: number;
  negative_feedback_count: number;
  knowledge_entries_count: number;
  categories_count: number;
  recent_questions: Array<{
    id: number;
    content: string;
    created_at: string;
  }>;
};

const LOCAL_HISTORY_KEY = "lexia-local-conversation-ids";
const THEME_PREFERENCE_KEY = "lexia-theme";
const LEGAL_WARNING = "Les informations fournies par LexIA sont destinées à un usage informatif uniquement et ne constituent pas un avis juridique officiel.";
const DARJA_LEGAL_WARNING = "المعلومات اللي كتعطي LexIA هي غير للتوجيه والمعلومة العامة، وما كتعتبرش استشارة قانونية رسمية، وما كتبدلش استشارة محامي أو موثق أو سلطة مختصة.";
const ARABIC_LEGAL_WARNING = "المعلومات التي تقدمها LexIA مخصصة للتوجيه والمعلومة العامة فقط، ولا تشكل استشارة قانونية رسمية، ولا تعوض استشارة محام أو موثق أو جهة مختصة.";

const frenchSuggestions = [
  { label: "Charges déductibles", question: "Quelles sont les charges déductibles ?" },
  { label: "Divorce", question: "Comment divorcer au Maroc ?" },
  { label: "Licenciement", question: "Quels sont mes droits en cas de licenciement ?" },
  { label: "Droits du consommateur", question: "Quels sont les droits du consommateur ?" },
];

const darijaSuggestions = [
  { label: "Charges déductibles", question: "Chno homa les charges déductibles?" },
  { label: "Tla9", question: "Bghit ntla9, chno khasni n3ref?" },
  { label: "Licenciement", question: "Tardouni mn lkhedma, chno ndir?" },
  { label: "7o9o9 lmostahlik", question: "Chno homa 7o9o9 lmostahlik?" },
];

const arabicSuggestions = [
  { label: "المصاريف القابلة للخصم", question: "ما هي المصاريف القابلة للخصم؟" },
  { label: "الطلاق", question: "كيف يتم الطلاق في المغرب؟" },
  { label: "الفصل من العمل", question: "ما هي حقوقي في حالة الفصل من العمل؟" },
  { label: "حقوق المستهلك", question: "ما هي حقوق المستهلك؟" },
];

const DARJA_INDICATORS = new Set([
  "chno", "kifach", "wach", "bghit", "brit", "n9der", "ndir", "daba",
  "lbarra", "lflos", "dariba", "charika", "mo9awala", "tla9", "salam",
  "labas", "chokran", "bzaf", "3la", "3andi", "7it",
]);

function looksLikeDarija(question: string) {
  const words = question.toLocaleLowerCase().match(/[\p{L}\p{N}]+/gu) ?? [];
  return words.some((word) => DARJA_INDICATORS.has(word));
}

function applyDocumentTheme(preference: ThemeChoice, systemIsDark?: boolean) {
  const followsDarkSystem =
    systemIsDark ?? window.matchMedia("(prefers-color-scheme: dark)").matches;
  const resolvedTheme =
    preference === "system" ? (followsDarkSystem ? "dark" : "light") : preference;
  const root = document.documentElement;
  root.dataset.theme = resolvedTheme;
  root.classList.remove("dark");
  root.style.colorScheme = resolvedTheme;
}

const coveredDomains = [
  {
    name: "Fiscalité",
    document: "Code Général des Impôts 2024",
    symbol: "§",
    examples: ["Quelles sont les charges déductibles ?"],
  },
  {
    name: "Famille et travail",
    document: "Code de la famille · Code du travail",
    symbol: "§",
    examples: ["Divorce, pension, licenciement"],
  },
  {
    name: "Pénal et procédures",
    document: "Code pénal · Procédures civile et pénale",
    symbol: "⚖",
    examples: ["Plainte, recours, infractions"],
  },
  {
    name: "Affaires et immobilier",
    document: "Sociétés · Change · Immobilier",
    symbol: "◇",
    examples: ["Sociétés, virements, propriété"],
  },
];

function CoveredDomainsPanel() {
  return (
    <div className="space-y-3 text-sm">
      {coveredDomains.map((domain) => (
        <div key={domain.name} className="theme-source theme-border rounded-lg border px-3 py-2.5">
          <p className="theme-text font-semibold">{domain.name}</p>
          <p className="theme-muted mt-0.5 text-xs">{domain.document}</p>
        </div>
      ))}
      <p className="theme-muted px-1 text-xs leading-5">LexIA répond uniquement à partir des textes actuellement indexés.</p>
    </div>
  );
}

function StatsPanel({ stats, error }: { stats: StatsResponse | null; error: string | null }) {
  if (!stats) return <p className="theme-muted text-xs leading-5">{error ?? "Chargement…"}</p>;
  return (
    <div>
      <div className="grid grid-cols-2 gap-2 text-xs">
        {[
          ["Conversations", stats.conversations_count],
          ["Messages", stats.messages_count],
          ["Avis positifs", stats.positive_feedback_count],
          ["Avis négatifs", stats.negative_feedback_count],
          ["Entrées juridiques", stats.knowledge_entries_count],
        ].map(([label, value]) => (
          <div key={label} className="theme-source theme-border rounded-lg border p-2.5">
            <p className="theme-text text-lg font-semibold">{value}</p>
            <p className="theme-muted mt-0.5">{label}</p>
          </div>
        ))}
      </div>
      {stats.recent_questions.length > 0 && (
        <div className="theme-border mt-3 border-t pt-3">
          <p className="theme-muted-2 mb-2 text-[10px] font-semibold uppercase tracking-wider">Questions récentes</p>
          {stats.recent_questions.slice(0, 3).map((item) => <p key={item.id} className="theme-muted truncate py-1 text-xs">{item.content}</p>)}
        </div>
      )}
    </div>
  );
}

function cleanPdfText(value: string) {
  return value
    .replace(/’/g, "'")
    .replace(/“/g, '"')
    .replace(/”/g, '"')
    .replace(/…/g, "...")
    .replace(/œ/g, "oe")
    .replace(/Œ/g, "OE");
}

async function createConsultationPdf(
  conversationId: number | null,
  message: ChatMessage,
  userQuestion: string,
) {
  const { jsPDF } = await import("jspdf");
  const document = new jsPDF({ unit: "mm", format: "a4" });
  const pageWidth = document.internal.pageSize.getWidth();
  const pageHeight = document.internal.pageSize.getHeight();
  const margin = 18;
  const contentWidth = pageWidth - margin * 2;
  const bottomMargin = 18;
  let y = 20;

  function ensureSpace(requiredHeight: number) {
    if (y + requiredHeight > pageHeight - bottomMargin) {
      document.addPage();
      y = 20;
    }
  }

  function writeText(
    value: string,
    options: { size?: number; color?: [number, number, number]; bold?: boolean } = {},
  ) {
    const size = options.size ?? 10;
    const lineHeight = size * 0.48;
    document.setFont("helvetica", options.bold ? "bold" : "normal");
    document.setFontSize(size);
    document.setTextColor(...(options.color ?? [51, 65, 85]));
    const paragraphs = cleanPdfText(value).split("\n");

    paragraphs.forEach((paragraph, paragraphIndex) => {
      const lines = document.splitTextToSize(paragraph || " ", contentWidth);
      lines.forEach((line: string) => {
        ensureSpace(lineHeight + 1);
        document.text(line, margin, y);
        y += lineHeight;
      });
      if (paragraphIndex < paragraphs.length - 1) y += 1.5;
    });
  }

  function writeSectionTitle(title: string) {
    ensureSpace(12);
    y += 4;
    document.setDrawColor(229, 231, 235);
    document.line(margin, y, pageWidth - margin, y);
    y += 7;
    writeText(title, { size: 12, color: [30, 58, 138], bold: true });
    y += 2;
  }

  document.setProperties({
    title: "Consultation LexIA",
    subject: "Orientation juridique marocaine",
    author: "LexIA",
  });
  writeText("LexIA", { size: 24, color: [30, 58, 138], bold: true });
  writeText("Assistant juridique marocain", {
    size: 11,
    color: [37, 99, 235],
  });
  y += 3;
  writeText(`Exporté le ${new Date().toLocaleString("fr-FR")}`, {
    size: 9,
    color: [100, 116, 139],
  });

  writeSectionTitle("Question");
  writeText(userQuestion || "Question non disponible.");

  writeSectionTitle("Réponse LexIA");
  writeText(message.content);

  writeSectionTitle("Information importante");
  writeText(message.legalWarning || LEGAL_WARNING, {
    color: [154, 52, 18],
  });

  writeSectionTitle("Sources juridiques");
  if (!message.sources || message.sources.length === 0) {
    writeText("Aucune source juridique associée à cette réponse.", {
      color: [100, 116, 139],
    });
  } else {
    message.sources.forEach((source, index) => {
      ensureSpace(25);
      if (index > 0) y += 4;
      writeText(`${index + 1}. ${source.article_number || "Article non précisé"}`, {
        size: 11,
        color: [30, 58, 138],
        bold: true,
      });
      writeText(source.document_title, { bold: true });
      writeText(`Catégorie : ${source.category || "Non précisée"}`, {
        size: 9,
        color: [71, 85, 105],
      });
      if (source.page_start !== null) {
        const pages =
          source.page_end !== null
            ? `${source.page_start} à ${source.page_end}`
            : `${source.page_start}`;
        writeText(`Page : ${pages}`, {
          size: 9,
          color: [71, 85, 105],
        });
      }
      y += 1;
      writeText(source.excerpt, { size: 9, color: [71, 85, 105] });
    });
  }

  const messageId = message.assistantMessageId ?? message.id.replace(/\D/g, "");
  document.save(
    `lexia-consultation-${conversationId ?? "nouvelle"}-${messageId || "assistant"}.pdf`,
  );
}

function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [language, setLanguage] = useState<ChatLanguage>("fr");
  const [themePreference, setThemePreference] = useState<ThemeChoice>(() => {
    const savedTheme = localStorage.getItem(THEME_PREFERENCE_KEY);
    return savedTheme === "light" || savedTheme === "dark" ? savedTheme : "system";
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [historyItems, setHistoryItems] = useState<LocalConversation[]>([]);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [statsError, setStatsError] = useState<string | null>(null);
  const [isInfoOpen, setIsInfoOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const questionInputRef = useRef<HTMLTextAreaElement>(null);
  const activeRequestRef = useRef<AbortController | null>(null);

  useLayoutEffect(() => {
    const systemTheme = window.matchMedia("(prefers-color-scheme: dark)");
    const applyTheme = () => applyDocumentTheme(themePreference, systemTheme.matches);

    localStorage.setItem(THEME_PREFERENCE_KEY, themePreference);
    applyTheme();
    if (themePreference !== "system") return;
    systemTheme.addEventListener("change", applyTheme);
    return () => systemTheme.removeEventListener("change", applyTheme);
  }, [themePreference]);

  function changeTheme(preference: ThemeChoice) {
    localStorage.setItem(THEME_PREFERENCE_KEY, preference);
    applyDocumentTheme(preference);
    setThemePreference(preference);
  }

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  useEffect(() => {
    return () => activeRequestRef.current?.abort();
  }, []);

  useEffect(() => {
    void loadLocalHistory(readLocalConversationIds());
    void loadStats();
  }, []);

  async function loadStats() {
    try {
      const { data } = await api.get<StatsResponse>("/api/stats/");
      setStats(data);
      setStatsError(null);
    } catch {
      setStatsError("Les statistiques sont temporairement indisponibles.");
    }
  }

  function readLocalConversationIds() {
    try {
      const storedValue = JSON.parse(
        localStorage.getItem(LOCAL_HISTORY_KEY) ?? "[]",
      );
      if (!Array.isArray(storedValue)) return [];
      return [...new Set(
        storedValue.filter(
          (value): value is number => Number.isInteger(value) && value > 0,
        ),
      )];
    } catch {
      return [];
    }
  }

  function saveLocalConversationIds(ids: number[]) {
    localStorage.setItem(LOCAL_HISTORY_KEY, JSON.stringify(ids));
  }

  function rememberConversation(id: number, title: string) {
    const ids = [id, ...readLocalConversationIds().filter((item) => item !== id)];
    saveLocalConversationIds(ids);
    setHistoryItems((current) => {
      const existingTitle = current.find((item) => item.id === id)?.title;
      return [
        {
          id,
          title: existingTitle ?? title,
          updatedAt: new Date().toISOString(),
        },
        ...current.filter((item) => item.id !== id),
      ];
    });
  }

  function openLocalHistory() {
    setIsHistoryOpen(true);
    void loadLocalHistory(readLocalConversationIds());
  }

  async function loadLocalHistory(ids: number[]) {
    if (ids.length === 0) {
      setHistoryItems([]);
      return;
    }

    setIsHistoryLoading(true);
    setHistoryError(null);
    const missingIds: number[] = [];
    let requestFailed = false;

    const conversations = await Promise.all(
      ids.map(async (id) => {
        try {
          const { data } = await api.get<ConversationDetail>(
            `/api/conversations/${id}/`,
          );
          const firstUserMessage = data.messages.find(
            (message) => message.role === "user",
          );
          return {
            id: data.id,
            title: firstUserMessage?.content || `Conversation #${data.id}`,
            updatedAt: data.updated_at,
          };
        } catch (requestError) {
          if (
            axios.isAxiosError(requestError) &&
            requestError.response?.status === 404
          ) {
            missingIds.push(id);
          } else {
            requestFailed = true;
          }
          return null;
        }
      }),
    );

    const availableConversations = conversations.filter(
      (item): item is LocalConversation => item !== null,
    );
    setHistoryItems(availableConversations);
    if (missingIds.length > 0) {
      saveLocalConversationIds(ids.filter((id) => !missingIds.includes(id)));
    }
    if (requestFailed) {
      setHistoryError("Certaines consultations n’ont pas pu être chargées.");
    }
    setIsHistoryLoading(false);
  }

  async function openConversation(id: number) {
    activeRequestRef.current?.abort();
    activeRequestRef.current = null;
    setIsHistoryLoading(true);
    setHistoryError(null);

    try {
      const { data } = await api.get<ConversationDetail>(
        `/api/conversations/${id}/`,
      );
      setMessages(
        data.messages.map((message) => ({
          id: `history-${message.id}`,
          role: message.role,
          content: message.content,
          sources: message.sources,
          legalWarning:
            message.role === "assistant"
              ? data.language === "ar"
                ? ARABIC_LEGAL_WARNING
                : data.language === "darija" ? DARJA_LEGAL_WARNING : LEGAL_WARNING
              : undefined,
          assistantMessageId:
            message.role === "assistant" ? message.id : undefined,
        })),
      );
      setLanguage(data.language);
      setConversationId(data.id);
      setQuestion("");
      setError(null);
      setIsLoading(false);
      setIsHistoryOpen(false);
      rememberConversation(
        data.id,
        data.messages.find((message) => message.role === "user")?.content ||
          `Conversation #${data.id}`,
      );
      requestAnimationFrame(() => questionInputRef.current?.focus());
    } catch (requestError) {
      if (
        axios.isAxiosError(requestError) &&
        requestError.response?.status === 404
      ) {
        const ids = readLocalConversationIds().filter((item) => item !== id);
        saveLocalConversationIds(ids);
        setHistoryItems((current) => current.filter((item) => item.id !== id));
        setHistoryError("Cette consultation n’existe plus.");
      } else {
        setHistoryError("Impossible de charger cette consultation.");
      }
    } finally {
      setIsHistoryLoading(false);
    }
  }

  function clearLocalHistory() {
    localStorage.removeItem(LOCAL_HISTORY_KEY);
    setHistoryItems([]);
    setHistoryError(null);
  }

  async function sendQuestion(value: string) {
    const cleanQuestion = value.trim();
    if (!cleanQuestion || isLoading) return;
    const detectedDarija = looksLikeDarija(cleanQuestion);
    const requestLanguage: ChatLanguage =
      detectedDarija && language === "fr" ? "darija" : language;

    if (detectedDarija && language !== "darija") {
      setLanguage("darija");
    }

    setMessages((current) => [
      ...current,
      { id: `user-${Date.now()}`, role: "user", content: cleanQuestion },
    ]);
    setQuestion("");
    setError(null);
    setIsLoading(true);
    const requestController = new AbortController();
    activeRequestRef.current = requestController;

    try {
      const payload: {
        question: string;
        language: string;
        conversation_id?: number;
      } = { question: cleanQuestion, language: requestLanguage };
      if (conversationId !== null) payload.conversation_id = conversationId;

      const { data } = await api.post<ChatResponse>("/api/chat/", payload, {
        signal: requestController.signal,
      });
      if (activeRequestRef.current !== requestController) return;
      setConversationId(data.conversation_id);
      rememberConversation(data.conversation_id, cleanQuestion);
      setMessages((current) => [
        ...current,
        {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: data.answer,
          sources: data.sources,
          legalWarning: data.legal_warning,
          assistantMessageId: data.assistant_message_id,
          answerMode: data.answer_mode,
          latencyMs: data.latency_ms,
          confidence: data.confidence,
          retrievalMethod: data.retrieval_method,
        },
      ]);
      void loadStats();
    } catch (requestError) {
      if (requestController.signal.aborted) return;
      setError(
        axios.isAxiosError(requestError)
          ? "Impossible de joindre LexIA. Vérifiez que le serveur Django est démarré."
          : "Une erreur inattendue est survenue.",
      );
    } finally {
      if (activeRequestRef.current === requestController) {
        activeRequestRef.current = null;
        setIsLoading(false);
      }
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void sendQuestion(question);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendQuestion(question);
    }
  }

  function startNewConversation() {
    activeRequestRef.current?.abort();
    activeRequestRef.current = null;
    setMessages([]);
    setConversationId(null);
    setQuestion("");
    setError(null);
    setIsLoading(false);
    requestAnimationFrame(() => questionInputRef.current?.focus());
  }

  async function submitFeedback(
    message: ChatMessage,
    rating: "positive" | "negative",
  ) {
    if (
      !message.assistantMessageId ||
      message.feedbackStatus === "loading" ||
      message.feedbackStatus === "success"
    ) {
      return;
    }

    setMessages((current) =>
      current.map((item) =>
        item.id === message.id
          ? { ...item, feedbackStatus: "loading", feedbackRating: rating }
          : item,
      ),
    );

    try {
      await api.post("/api/feedback/", {
        message: message.assistantMessageId,
        rating,
        comment: "",
      });
      setMessages((current) =>
        current.map((item) =>
          item.id === message.id
            ? { ...item, feedbackStatus: "success", feedbackRating: rating }
            : item,
        ),
      );
      void loadStats();
    } catch {
      setMessages((current) =>
        current.map((item) =>
          item.id === message.id
            ? { ...item, feedbackStatus: "error", feedbackRating: undefined }
            : item,
        ),
      );
    }
  }

  return (
    <main className="theme-page min-h-screen">
      <header className="theme-sidebar theme-border sticky top-0 z-40 border-b lg:hidden">
        <div className="mx-auto flex items-center justify-between px-4 py-2.5">
          <div className="flex items-center gap-3">
            <img src={lexiaIcon} alt="" className="h-8 w-8" />
            <div>
              <p className="theme-text text-lg font-semibold tracking-tight">LexIA</p>
              <p className="theme-muted-2 text-[9px] font-medium uppercase tracking-[0.15em]">Droit marocain</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button type="button" onClick={openLocalHistory} className="theme-card theme-border rounded-full border px-3 py-1.5 text-xs font-medium transition soft-hover">
              Historique{historyItems.length > 0 ? ` (${historyItems.length})` : ""}
            </button>
            <button type="button" onClick={() => setIsInfoOpen(true)} className="theme-card theme-border rounded-full border px-3 py-1.5 text-xs font-medium transition soft-hover">
              Infos
            </button>
            <button type="button" onClick={startNewConversation} className="grid h-9 w-9 place-items-center rounded-full bg-accent-500 text-lg text-white" aria-label="Nouvelle consultation">
              ＋
            </button>
          </div>
        </div>
      </header>

      {isHistoryOpen && (
        <div className="mobile-overlay fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-labelledby="history-title" onMouseDown={(event) => {
          if (event.currentTarget === event.target) setIsHistoryOpen(false);
        }}>
          <aside className="theme-sidebar theme-border flex h-full w-full max-w-md flex-col border-l shadow-2xl">
            <div className="theme-border flex items-start justify-between border-b px-6 py-6">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.15em] text-accent-600">Ce navigateur uniquement</p>
                <h2 id="history-title" className="theme-text mt-1 text-xl font-semibold">Historique local</h2>
              </div>
              <button type="button" onClick={() => setIsHistoryOpen(false)} className="theme-card theme-border grid h-10 w-10 place-items-center rounded-full border text-xl text-accent-800 transition hover:bg-accent-50" aria-label="Fermer l’historique">×</button>
            </div>

            <div className="flex-1 overflow-y-auto p-5">
              {historyError && <p className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{historyError}</p>}
              {isHistoryLoading && <p className="theme-muted py-8 text-center text-sm">Chargement de l’historique…</p>}
              {!isHistoryLoading && historyItems.length === 0 && (
                <div className="theme-assistant theme-border rounded-2xl border p-6 text-center">
                  <p className="theme-text text-base font-semibold">Aucune consultation locale</p>
                  <p className="theme-muted mt-2 text-sm leading-6">Les nouvelles conversations créées depuis ce navigateur apparaîtront ici.</p>
                </div>
              )}
              {!isHistoryLoading && historyItems.length > 0 && (
                <div className="space-y-3">
                  {historyItems.map((item) => (
                    <button key={item.id} type="button" onClick={() => void openConversation(item.id)} className={`theme-card theme-border block w-full rounded-xl border p-3 text-left transition soft-hover ${conversationId === item.id ? "theme-active-history" : ""}`}>
                      <span className="theme-text block truncate text-sm font-medium">{item.title}</span>
                      <span className="theme-muted mt-1 block text-xs">Conversation n° {item.id}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="theme-border border-t p-5">
              <button type="button" onClick={clearLocalHistory} disabled={historyItems.length === 0} className="theme-card theme-border w-full rounded-xl border px-4 py-2.5 text-sm font-medium transition soft-hover disabled:cursor-not-allowed disabled:opacity-40">Effacer l’historique local</button>
              <p className="theme-muted-2 mt-2 text-center text-[11px] leading-4">Cette action ne supprime aucune donnée du serveur.</p>
            </div>
          </aside>
        </div>
      )}

      {isInfoOpen && (
        <div className="mobile-overlay fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-labelledby="info-title" onMouseDown={(event) => {
          if (event.currentTarget === event.target) setIsInfoOpen(false);
        }}>
          <aside className="theme-sidebar h-full w-full max-w-sm overflow-y-auto p-5 shadow-2xl">
            <div className="theme-border flex items-center justify-between border-b pb-5">
              <h2 id="info-title" className="text-xl font-semibold">Informations LexIA</h2>
              <button type="button" onClick={() => setIsInfoOpen(false)} className="theme-card theme-border grid h-9 w-9 place-items-center rounded-full border text-xl" aria-label="Fermer">×</button>
            </div>
            <details className="theme-card theme-border group mt-5 rounded-xl border p-3">
              <summary className="cursor-pointer list-none text-sm font-semibold marker:hidden">Domaines couverts <span className="float-right">⌄</span></summary>
              <div className="mt-3"><CoveredDomainsPanel /></div>
            </details>
            <details className="theme-card theme-border group mt-3 rounded-xl border p-3">
              <summary className="cursor-pointer list-none text-sm font-semibold marker:hidden">Statistiques <span className="float-right">⌄</span></summary>
              <div className="mt-3"><StatsPanel stats={stats} error={statsError} /></div>
            </details>
          </aside>
        </div>
      )}

      <section className="grid min-h-screen w-full gap-0 lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="theme-sidebar sticky top-0 hidden h-screen flex-col p-3 lg:flex">
          <div className="flex items-center gap-3 px-2 py-2">
            <img src={lexiaIcon} alt="Logo LexIA" className="h-9 w-9 rounded-xl" />
            <div>
              <p className="text-xl font-semibold">LexIA</p>
              <p className="theme-muted-2 text-[9px] uppercase tracking-[0.16em]">Droit marocain</p>
            </div>
          </div>

          <button type="button" onClick={startNewConversation} className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-accent-500 px-3 py-2.5 text-sm font-semibold text-white transition hover:bg-accent-600">
            <span className="text-lg">＋</span> Nouvelle consultation
          </button>
          <button type="button" onClick={openLocalHistory} className="theme-muted mt-2 flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm transition surface-hover">
            <span>Historique local</span>
            <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs">{historyItems.length}</span>
          </button>

          <details className="theme-border group mt-3 border-t px-2 py-3">
            <summary className="theme-muted cursor-pointer list-none text-sm font-medium marker:hidden">Domaines couverts <span className="theme-muted-2 float-right transition group-open:rotate-180">⌄</span></summary>
            <div className="mt-3"><CoveredDomainsPanel /></div>
          </details>
          <details className="theme-border group border-t px-2 py-3">
            <summary className="theme-muted cursor-pointer list-none text-sm font-medium marker:hidden">Statistiques <span className="theme-muted-2 float-right transition group-open:rotate-180">⌄</span></summary>
            <div className="mt-3"><StatsPanel stats={stats} error={statsError} /></div>
          </details>

          <div className="mt-5 min-h-0 flex-1 overflow-y-auto">
            <p className="theme-muted-2 px-2 text-[10px] font-semibold uppercase tracking-[0.14em]">Consultations récentes</p>
            <div className="mt-3 space-y-1">
              {historyItems.length === 0 && <p className="theme-muted-2 px-2 py-4 text-xs leading-5">Vos conversations récentes apparaîtront ici.</p>}
              {historyItems.slice(0, 6).map((item) => (
                <button key={item.id} type="button" onClick={() => void openConversation(item.id)} className={`block w-full truncate rounded-lg px-3 py-2 text-left text-[13px] transition ${conversationId === item.id ? "theme-active-history" : "theme-muted surface-hover"}`} title={item.title}>
                  {item.title}
                </button>
              ))}
            </div>
          </div>

          <div className="theme-border theme-muted-2 border-t px-2 pt-4 text-[11px]">LexIA · Assistant juridique marocain</div>
        </aside>

        <section className="theme-page relative mx-auto flex h-[calc(100vh-54px)] w-full max-w-[820px] flex-col lg:h-screen">
          <div className="absolute right-4 top-3 z-30 flex items-center gap-2 sm:right-6">
            <label className="flex items-center gap-2 text-xs font-medium">
              <span className="sr-only">Langue de la consultation</span>
              <select
                value={language}
                onChange={(event) => setLanguage(event.target.value as ChatLanguage)}
                disabled={isLoading}
                className="theme-select max-w-[86px] rounded-full px-2.5 py-1.5 text-xs font-medium disabled:opacity-50 sm:max-w-none sm:px-3"
              >
                <option value="fr">Français</option>
                <option value="darija">Darija</option>
                <option value="ar">العربية</option>
              </select>
            </label>
            <label>
              <span className="sr-only">Thème</span>
              <select
                value={themePreference}
                onChange={(event) => changeTheme(event.target.value as ThemeChoice)}
                className="theme-select max-w-[76px] rounded-full px-2.5 py-1.5 text-xs sm:max-w-none"
                aria-label="Thème d’affichage"
              >
                <option value="system">Système</option>
                <option value="light">Clair</option>
                <option value="dark">Sombre</option>
              </select>
            </label>
          </div>

          <div className="flex-1 space-y-7 overflow-y-auto px-4 pb-8 pt-16 sm:px-7 lg:px-8">
            {messages.length === 0 && (
              <div className="mx-auto flex max-w-xl flex-col items-center py-12 text-center sm:py-24">
                <img src={lexiaIcon} alt="" className="h-12 w-12" />
                <h1 className="theme-text mt-5 text-2xl font-medium tracking-tight sm:text-[28px]">Comment puis-je vous orienter juridiquement ?</h1>
                <p className="theme-muted mt-3 max-w-lg text-sm leading-6">Posez une question sur la fiscalité, les sociétés, la famille, le travail, le pénal ou d’autres domaines du droit marocain.</p>
                <div className="mt-7 flex w-full flex-wrap justify-center gap-2.5">
                  {(language === "ar" ? arabicSuggestions : language === "darija" ? darijaSuggestions : frenchSuggestions).map((suggestion) => (
                    <button key={suggestion.label} type="button" onClick={() => void sendQuestion(suggestion.question)} disabled={isLoading} className="theme-chip rounded-full border px-4 py-2 text-sm transition disabled:opacity-50">{suggestion.label}</button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((message, messageIndex) => (
              <article key={message.id} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[88%] sm:max-w-[76%] ${message.role === "user" ? "rounded-[1.25rem_1.25rem_0.35rem_1.25rem] bg-[var(--user-bubble)] px-4 py-2.5 text-white" : "assistant-message w-full sm:max-w-full"}`}>
                  {message.role === "assistant" && (
                    <div className="theme-muted mb-3 flex items-center gap-2 text-xs font-medium">
                      <img src={lexiaIcon} alt="" className="h-7 w-7 rounded-lg" />
                      LexIA
                    </div>
                  )}
                  <p dir={language === "ar" ? "rtl" : "ltr"} className={`whitespace-pre-wrap text-sm leading-7 sm:text-[15px] ${message.role === "assistant" ? "theme-text" : "text-white"}`}>{message.content}</p>
                  {message.role === "assistant" && message.retrievalMethod === "hybrid" && (
                    <p className="theme-muted-2 mt-2 text-xs">RAG · confiance {message.confidence === "high" ? "élevée" : "moyenne"}{message.latencyMs !== undefined ? ` · ${(message.latencyMs / 1000).toFixed(1)} s` : ""}</p>
                  )}

                  {message.role === "assistant" && message.sources && message.sources.length > 0 && (
                    <div className="mt-4 space-y-2">
                      <p className="theme-muted-2 text-xs font-medium">Sources consultées</p>
                      {message.sources.map((source, index) => (
                        <details key={`${source.document_title}-${source.article_number}-${index}`} className="theme-source theme-border group rounded-xl border transition">
                          <summary className="theme-text flex cursor-pointer list-none items-center gap-2.5 px-3 py-2.5 text-sm marker:hidden">
                            <span className="source-rank grid h-6 w-6 shrink-0 place-items-center rounded-full text-[10px] font-semibold">{index + 1}</span>
                            <span className="min-w-0 flex-1">
                              <span className="block font-semibold">{source.article_number || "Article non précisé"}</span>
                              <span dir={language === "ar" ? "rtl" : "ltr"} className="theme-muted mt-0.5 block truncate text-[11px] font-normal">{source.document_title}</span>
                            </span>
                            <span aria-hidden="true" className="text-lg text-accent-500 transition-transform duration-200 group-open:rotate-180">⌄</span>
                          </summary>
                          <div className="theme-border border-t px-3 pb-3 pt-3 sm:pl-12">
                            <div className="flex flex-wrap gap-2 text-xs">
                              <span className="source-meta rounded-full px-2.5 py-1">{source.category}</span>
                              {source.page_start !== null && <span className="source-meta rounded-full px-2.5 py-1">Page début : {source.page_start}</span>}
                              {source.page_end !== null && <span className="source-meta rounded-full px-2.5 py-1">Page fin : {source.page_end}</span>}
                            </div>
                            <p className="theme-muted mt-2 max-h-40 overflow-y-auto text-xs leading-5">{source.excerpt}</p>
                          </div>
                        </details>
                      ))}
                    </div>
                  )}

                  {message.role === "assistant" && (
                    <>
                      {message.legalWarning && (
                        <p dir={language === "ar" ? "rtl" : "ltr"} className="theme-warning mt-4 rounded-lg border px-3 py-2 text-[11px] leading-5"><span aria-hidden="true">ⓘ</span> {message.legalWarning}</p>
                      )}
                      <div className="theme-muted-2 mt-2.5 flex flex-wrap items-center gap-1">
                        <button
                          type="button"
                          onClick={() => void submitFeedback(message, "positive")}
                          disabled={message.feedbackStatus === "loading" || message.feedbackStatus === "success"}
                          aria-label="Marquer la réponse comme utile"
                          className={`action-button rounded-lg px-2 py-1 text-sm transition disabled:cursor-not-allowed ${message.feedbackRating === "positive" && message.feedbackStatus === "success" ? "theme-active-history" : ""}`}
                        >
                          👍
                        </button>
                        <button
                          type="button"
                          onClick={() => void submitFeedback(message, "negative")}
                          disabled={message.feedbackStatus === "loading" || message.feedbackStatus === "success"}
                          aria-label="Marquer la réponse comme peu utile"
                          className={`action-button rounded-lg px-2 py-1 text-sm transition disabled:cursor-not-allowed ${message.feedbackRating === "negative" && message.feedbackStatus === "success" ? "theme-active-history" : ""}`}
                        >
                          👎
                        </button>
                        <span className="theme-divider mx-1 h-3 w-px" aria-hidden="true" />
                        <button
                          type="button"
                          onClick={() => {
                            const previousUserMessage = messages
                              .slice(0, messageIndex)
                              .reverse()
                              .find((item) => item.role === "user");
                            void createConsultationPdf(
                              conversationId,
                              message,
                              previousUserMessage?.content ?? "",
                            );
                          }}
                          className="action-button rounded-lg px-2 py-1 text-xs font-medium transition"
                        >
                          ⇩ Exporter PDF
                        </button>
                      </div>
                      {message.feedbackStatus === "loading" && <p className="theme-muted-2 mt-2 text-xs">Envoi de votre retour…</p>}
                      {message.feedbackStatus === "success" && <p className="mt-2 text-xs font-medium text-accent-700">Merci pour votre retour.</p>}
                      {message.feedbackStatus === "error" && <p className="mt-2 text-xs font-medium text-red-600">Impossible d’envoyer votre retour. Veuillez réessayer.</p>}
                    </>
                  )}
                </div>
              </article>
            ))}

            {isLoading && (
              <div className="theme-muted flex items-center gap-3 text-sm">
                <span className="flex gap-1">
                  <i className="h-2 w-2 animate-bounce rounded-full bg-accent-500 [animation-delay:-0.3s]" />
                  <i className="h-2 w-2 animate-bounce rounded-full bg-accent-500 [animation-delay:-0.15s]" />
                  <i className="h-2 w-2 animate-bounce rounded-full bg-accent-500" />
                </span>
                LexIA consulte la base juridique…
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="theme-composer-zone sticky bottom-0 z-20 px-4 pb-3 pt-4 sm:px-7 sm:pb-4">
            {error && <p className="mb-3 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
            <form onSubmit={handleSubmit} className="theme-composer flex items-end gap-2 rounded-[1.5rem] border p-2">
              <textarea dir={language === "ar" ? "rtl" : "ltr"} ref={questionInputRef} value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={handleKeyDown} rows={1} maxLength={2000} placeholder={language === "ar" ? "اطرح سؤالك القانوني..." : language === "darija" ? "Sowel 3la chi mas2ala qanouniya..." : "Posez votre question juridique..."} aria-label="Question juridique" className="theme-composer-textarea max-h-36 min-h-11 flex-1 resize-none border-0 bg-transparent px-3 py-2.5 text-sm leading-6 shadow-none outline-none focus:border-transparent focus:outline-none focus:ring-0" />
              <button type="submit" disabled={!question.trim() || isLoading} className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-accent-500 text-lg text-white transition hover:bg-accent-600 disabled:cursor-not-allowed disabled:opacity-35" aria-label="Envoyer la question">↑</button>
            </form>
            <p className="theme-muted-2 mt-2 text-center text-[11px]">Entrée pour envoyer · Maj + Entrée pour une nouvelle ligne</p>
          </div>
        </section>
      </section>

    </main>
  );
}

export default App;
