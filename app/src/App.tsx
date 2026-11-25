import { useState, useEffect, useRef } from 'react';
import { Layers } from 'lucide-react';

import { Home } from './pages/Home';
import { Workspace } from './pages/Workspace';
import { CompareWorkflow } from './components/compare/CompareWorkflow';
import { SingleDocConsentModal } from './components/workspace/SingleDocConsentModal';
import {
  translateIntelligence,
  requestAiAnalysis,
  disableAiSession,
  getAiSessionStatus,
  type ProcessedDocument,
  type DocumentIntelligence,
  type AISessionCredentials,
} from './lib/api';
import type { SupportedLanguage } from './lib/translations';

const LANGUAGES: SupportedLanguage[] = ['English', 'Hindi', 'Hinglish'];
const AI_SESSION_STORAGE_KEY = 'bharatAiSession';

function App() {
  const [view, setView] = useState<'home' | 'workspace' | 'compare'>('home');
  const [document, setDocument] = useState<ProcessedDocument | null>(null);
  const [language, setLanguage] = useState<SupportedLanguage>(() => {
    return (localStorage.getItem('appLanguage') as SupportedLanguage) || 'English';
  });

  const [intelligenceCache, setIntelligenceCache] = useState<Partial<Record<SupportedLanguage, DocumentIntelligence>>>({});
  const [baseIntelligence, setBaseIntelligence] = useState<DocumentIntelligence | null>(null);
  const [isTranslating, setIsTranslating] = useState(false);
  const [translatingLanguage, setTranslatingLanguage] = useState<SupportedLanguage | null>(null);

  const [aiSession, setAiSession] = useState<AISessionCredentials | null>(null);
  const [isActivationModalOpen, setIsActivationModalOpen] = useState(false);
  const [hasPromptedActivation, setHasPromptedActivation] = useState(false);
  const [isAiExplaining, setIsAiExplaining] = useState(false);

  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const timeoutRef = useRef<number | null>(null);
  const activeDocIdRef = useRef<string | null>(null);
  const langRequestIdRef = useRef<number>(0);

  useEffect(() => {
    localStorage.setItem('appLanguage', language);
  }, [language]);

  // Verify stored session credentials against backend on startup (never trust client storage alone)
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(AI_SESSION_STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw) as AISessionCredentials;
      if (!parsed?.aiSessionId || !parsed?.aiSessionToken) {
        sessionStorage.removeItem(AI_SESSION_STORAGE_KEY);
        return;
      }
      getAiSessionStatus(parsed.aiSessionId, parsed.aiSessionToken)
        .then((status) => {
          if (status.active) {
            setAiSession(parsed);
            setHasPromptedActivation(true);
          } else {
            sessionStorage.removeItem(AI_SESSION_STORAGE_KEY);
          }
        })
        .catch(() => {
          sessionStorage.removeItem(AI_SESSION_STORAGE_KEY);
        });
    } catch {
      sessionStorage.removeItem(AI_SESSION_STORAGE_KEY);
    }
  }, []);

  const showSuccess = (lang: SupportedLanguage) => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);

    let msg = "Switched to English";
    if (lang === "Hindi") msg = "हिंदी में बदल दिया";
    if (lang === "Hinglish") msg = "Hinglish mein switch ho gaya";

    setSuccessMsg(msg);
    timeoutRef.current = window.setTimeout(() => setSuccessMsg(null), 2000);
  };

  const handleWorkspaceIntelligenceUpdate = (
    newIntel: DocumentIntelligence,
    targetLanguage?: SupportedLanguage
  ) => {
    langRequestIdRef.current += 1;
    setIsTranslating(false);
    setTranslatingLanguage(null);

    const effectiveLang = targetLanguage || language;
    if (targetLanguage && targetLanguage !== language) {
      setLanguage(targetLanguage);
    }

    setDocument(prev => (prev && prev.id === activeDocIdRef.current ? { ...prev, intelligence: newIntel } : prev));
    setIntelligenceCache(prev => {
      if (newIntel.mode === "AI_CONSENTED" && !targetLanguage) {
        return { [effectiveLang]: newIntel };
      }
      return { ...prev, [effectiveLang]: newIntel };
    });
  };

  const runAutoAiExplain = async (docId: string, lang: SupportedLanguage, creds: AISessionCredentials) => {
    if (activeDocIdRef.current !== docId) return;
    setIsAiExplaining(true);
    try {
      const aiIntel = await requestAiAnalysis(docId, undefined, undefined, lang, creds);
      if (activeDocIdRef.current === docId) {
        handleWorkspaceIntelligenceUpdate(aiIntel);
      }
    } catch {
      // Preserve local facts cleanly if backend rejects/errors
    } finally {
      if (activeDocIdRef.current === docId) {
        setIsAiExplaining(false);
      }
    }
  };

  const handleLanguageChange = async (newLang: SupportedLanguage) => {
    if (newLang === language) return;

    setLanguage(newLang);

    if (document && document.intelligence) {
      const cached = intelligenceCache[newLang];
      // Use cache when mode matches (or AI isn't active to upgrade a local cache entry)
      if (cached && (!aiSession || cached.mode === "AI_CONSENTED")) {
        setDocument(prev => prev ? { ...prev, intelligence: cached } : null);
        showSuccess(newLang);
        return;
      }

      const requestDocId = document.id;
      const requestId = ++langRequestIdRef.current;
      setIsTranslating(true);
      setTranslatingLanguage(newLang);
      try {
        const sourceIntel = intelligenceCache['English'] || document.intelligence;
        const newIntel = await translateIntelligence(
          sourceIntel,
          newLang,
          aiSession ? "ai" : "local",
          document.id,
          undefined,
          undefined,
          aiSession
        );

        if (activeDocIdRef.current !== requestDocId || langRequestIdRef.current !== requestId) {
          return;
        }

        setIntelligenceCache(prev => ({ ...prev, [newLang]: newIntel }));

        setLanguage(currentLang => {
          if (currentLang === newLang && activeDocIdRef.current === requestDocId) {
            setDocument(prev => prev ? { ...prev, intelligence: newIntel } : null);
            showSuccess(newLang);
          }
          return currentLang;
        });
      } catch (error) {
        console.error("Failed to translate document intelligence:", error);
      } finally {
        if (langRequestIdRef.current === requestId) {
          setIsTranslating(false);
          setTranslatingLanguage(null);
        }
      }
    } else {
      showSuccess(newLang);
    }
  };

  const handleDocumentReady = (doc: ProcessedDocument) => {
    activeDocIdRef.current = doc.id;
    langRequestIdRef.current += 1;
    setDocument(doc);
    setBaseIntelligence(doc.intelligence || null);
    if (doc.intelligence) {
      setIntelligenceCache({ [language]: doc.intelligence });
    } else {
      setIntelligenceCache({});
    }
    setView('workspace');

    // Prompt once per session before first external AI transmission
    if (!aiSession && !hasPromptedActivation) {
      setHasPromptedActivation(true);
      setIsActivationModalOpen(true);
    }
  };

  const handleAiActivated = async (creds: AISessionCredentials) => {
    setAiSession(creds);
    setHasPromptedActivation(true);
    setIsActivationModalOpen(false);
    try {
      sessionStorage.setItem(AI_SESSION_STORAGE_KEY, JSON.stringify(creds));
    } catch {
      // ignore storage failure
    }

    if (view === 'workspace' && document) {
      await runAutoAiExplain(document.id, language, creds);
    }
  };

  const handleDisableAi = async () => {
    const current = aiSession;
    setAiSession(null);
    setHasPromptedActivation(true);
    try {
      sessionStorage.removeItem(AI_SESSION_STORAGE_KEY);
    } catch {
      // ignore
    }
    if (current) {
      await disableAiSession(current.aiSessionId, current.aiSessionToken);
    }
    if (document && baseIntelligence) {
      const localReset: DocumentIntelligence = {
        ...baseIntelligence,
        mode: "LOCAL_MODE",
        fallback_triggered: false,
        fallback_reason: undefined,
        fallback_message: undefined,
      };
      setDocument(prev => prev ? { ...prev, intelligence: localReset } : null);
      setIntelligenceCache({ [language]: localReset });
    }
  };

  const handleBack = () => {
    activeDocIdRef.current = null;
    langRequestIdRef.current += 1;
    setDocument(null);
    setBaseIntelligence(null);
    setIntelligenceCache({});
    setIsAiExplaining(false);
    setView('home');
  };

  const getTranslatingText = () => {
    if (translatingLanguage === 'Hindi') return "हिंदी में समझाया जा रहा है…";
    if (translatingLanguage === 'Hinglish') return "Hindi mein explain ho raha hai…";
    return "Preparing English explanation…";
  };

  const activeIndex = LANGUAGES.indexOf(language);

  return (
    <div className="h-screen w-full bg-neutral-100 font-sans flex flex-col overflow-hidden">
      <SingleDocConsentModal
        isOpen={isActivationModalOpen}
        language={language}
        onClose={() => {
          setHasPromptedActivation(true);
          setIsActivationModalOpen(false);
        }}
        onActivated={handleAiActivated}
      />

      {/* Clean Header */}
      <header className="h-16 shrink-0 bg-neutral-50 border-b border-neutral-200 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-8 h-full flex items-center justify-between">
          <div className="flex items-center gap-3 cursor-pointer group" onClick={handleBack}>
            <div className="w-8 h-8 bg-primary-900 rounded-[6px] flex items-center justify-center shadow-sm">
              <span className="text-white font-extrabold text-[16px] font-heading leading-none mt-[1px]">B</span>
            </div>
            <span className="font-extrabold text-[15px] text-primary-900 tracking-wider font-heading leading-tight pt-[1px]">
              BHARAT INVESTOR COPILOT
            </span>
          </div>

          <div className="flex items-center gap-4">
            {view !== 'compare' && (
              <button
                onClick={() => setView('compare')}
                className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1 rounded-[6px] text-xs font-bold text-accent-700 bg-accent-50 hover:bg-accent-100 border border-accent-200 transition-colors shadow-2xs cursor-pointer"
              >
                <Layers className="w-3.5 h-3.5" />
                Compare Filings
              </button>
            )}

            <div className="flex flex-col items-end h-[20px] justify-center overflow-hidden">
              <div className={`transition-all duration-300 transform ${isTranslating ? 'translate-y-0 opacity-100' : 'translate-y-4 opacity-0 hidden'}`}>
                 <span className="text-[11px] font-bold text-accent-600 flex items-center gap-1.5">
                   <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-accent-500"></span>
                  </span>
                   {getTranslatingText()}
                 </span>
              </div>
              <div className={`transition-all duration-300 transform ${successMsg && !isTranslating ? 'translate-y-0 opacity-100' : '-translate-y-4 opacity-0 hidden'}`}>
                 <span className="text-[11px] font-bold text-success-600">
                   {successMsg}
                 </span>
              </div>
            </div>

            {/* Animated Language Selector */}
            <div className="relative bg-neutral-100 border border-neutral-200 rounded-[6px] p-1 flex items-center shadow-inner h-[32px]">
              <div
                className="absolute top-1 bottom-1 bg-white shadow border border-neutral-200/50 rounded-[4px] transition-all duration-300 ease-out"
                style={{
                  left: `calc(${activeIndex * (100 / 3)}% + 4px)`,
                  width: 'calc(33.33% - 8px)',
                  zIndex: 1
                }}
              />

              {LANGUAGES.map((lang) => (
                <button
                  key={lang}
                  onClick={() => handleLanguageChange(lang)}
                  className={`relative z-10 w-[72px] text-center text-[10px] sm:text-[11px] font-bold uppercase tracking-widest rounded-[4px] transition-colors duration-300 h-full ${
                    language === lang
                      ? 'text-primary-900'
                      : 'text-neutral-400 hover:text-primary-900'
                  }`}
                >
                  {lang === 'Hindi' ? 'हिंदी' : lang}
                </button>
              ))}
            </div>
          </div>
        </div>
      </header>

      <main className="flex-1 flex flex-col w-full mx-auto overflow-hidden bg-neutral-100 relative">
        <div key={language} className="absolute inset-0 animate-fade-in pointer-events-none z-0" style={{ animationDuration: '300ms' }}></div>
        {view === 'compare' ? (
          <div className="h-full w-full overflow-y-auto hide-scrollbar relative z-10">
            <CompareWorkflow onBackToHome={handleBack} language={language} />
          </div>
        ) : view === 'home' || !document ? (
          <div className="h-full w-full overflow-y-auto hide-scrollbar relative z-10">
            <Home
              onDocumentReady={handleDocumentReady}
              onOpenCompare={() => setView('compare')}
              language={language}
              aiSession={aiSession}
            />
          </div>
        ) : (
          <Workspace
            document={document}
            onBack={handleBack}
            language={language}
            isTranslating={isTranslating}
            isAiExplaining={isAiExplaining}
            aiSession={aiSession}
            onEnableAi={() => setIsActivationModalOpen(true)}
            onDisableAi={handleDisableAi}
          />
        )}
      </main>
    </div>
  );
}

export default App;
