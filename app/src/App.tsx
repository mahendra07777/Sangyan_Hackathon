import { useState, useEffect, useRef } from 'react';

import { Home } from './pages/Home';
import { Workspace } from './pages/Workspace';
import { translateIntelligence } from './lib/api';
import type { ProcessedDocument, DocumentIntelligence } from './lib/api';
import type { SupportedLanguage } from './lib/translations';

const LANGUAGES: SupportedLanguage[] = ['English', 'Hindi', 'Hinglish'];

function App() {
  const [view, setView] = useState<'home' | 'workspace'>('home');
  const [document, setDocument] = useState<ProcessedDocument | null>(null);
  const [language, setLanguage] = useState<SupportedLanguage>(() => {
    return (localStorage.getItem('appLanguage') as SupportedLanguage) || 'English';
  });
  
  const [intelligenceCache, setIntelligenceCache] = useState<Partial<Record<SupportedLanguage, DocumentIntelligence>>>({});
  const [isTranslating, setIsTranslating] = useState(false);
  const [translatingLanguage, setTranslatingLanguage] = useState<SupportedLanguage | null>(null);
  
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const timeoutRef = useRef<number | null>(null);

  useEffect(() => {
    localStorage.setItem('appLanguage', language);
  }, [language]);

  const showSuccess = (lang: SupportedLanguage) => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    
    let msg = "Switched to English";
    if (lang === "Hindi") msg = "हिंदी में बदल दिया";
    if (lang === "Hinglish") msg = "Hinglish mein switch ho gaya";
    
    setSuccessMsg(msg);
    timeoutRef.current = window.setTimeout(() => setSuccessMsg(null), 2000);
  };

  const handleLanguageChange = async (newLang: SupportedLanguage) => {
    if (newLang === language) return;
    
    setLanguage(newLang);
    
    if (document && document.intelligence) {
      if (intelligenceCache[newLang]) {
        // If it's already in cache, update immediately
        setDocument(prev => prev ? { ...prev, intelligence: intelligenceCache[newLang]! } : null);
        showSuccess(newLang);
      } else {
        setIsTranslating(true);
        setTranslatingLanguage(newLang);
        try {
          const newIntel = await translateIntelligence(
            // Try to always translate from English if we have it, for better quality
            intelligenceCache['English'] || document.intelligence, 
            newLang
          );
          
          // Always cache the result
          setIntelligenceCache(prev => ({ ...prev, [newLang]: newIntel }));
          
          // Only update the document if the user hasn't switched to another language while waiting
          setLanguage(currentLang => {
            if (currentLang === newLang) {
              setDocument(prev => prev ? { ...prev, intelligence: newIntel } : null);
              showSuccess(newLang);
            }
            return currentLang; // Don't actually change the language state
          });
          
        } catch (error) {
          console.error("Failed to translate document intelligence:", error);
        } finally {
          setIsTranslating(false);
          setTranslatingLanguage(null);
        }
      }
    } else {
      showSuccess(newLang);
    }
  };

  const handleDocumentReady = (doc: ProcessedDocument) => {
    setDocument(doc);
    if (doc.intelligence) {
      setIntelligenceCache({ [language]: doc.intelligence });
    } else {
      setIntelligenceCache({});
    }
    setView('workspace');
  };

  const handleBack = () => {
    setDocument(null);
    setIntelligenceCache({});
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
              {/* Sliding Indicator */}
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
        {view === 'home' || !document ? (
          <div className="h-full w-full overflow-y-auto hide-scrollbar relative z-10">
            <Home onDocumentReady={handleDocumentReady} language={language} />
          </div>
        ) : (
          <Workspace document={document} onBack={handleBack} language={language} isTranslating={isTranslating} />
        )}
      </main>
    </div>
  );
}

export default App;
