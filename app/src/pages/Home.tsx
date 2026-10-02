import { useState, useRef } from "react";
import { Upload, Loader2, AlertCircle, Mic, ArrowRight } from "lucide-react";
import { Button } from "../components/ui/Button";
import { uploadDocument } from "../lib/api";
import { getTranslation } from "../lib/translations";
import type { SupportedLanguage } from "../lib/translations";
import type { ProcessedDocument } from "../lib/api";

interface HomeProps {
  onDocumentReady: (doc: ProcessedDocument) => void;
  language: string;
}

export function Home({ onDocumentReady, language }: HomeProps) {
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const t = (key: string) => getTranslation(key, language as SupportedLanguage);

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setError(null);
    try {
      const result = await uploadDocument(file, language);
      onDocumentReady(result.document);
    } catch (err: any) {
      setError(err.message || t("error.failed"));
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <div className="flex flex-col items-center min-h-full py-8 md:py-12 px-4 sm:px-8 bg-neutral-100 bg-grid-pattern-subtle font-sans text-neutral-900 selection:bg-accent-500 selection:text-white relative">
      
      {/* 1. HERO SECTION & LIVE PREVIEW */}
      <section className="max-w-6xl w-full grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-20 items-center min-h-[65vh]">
        
        {/* LEFT: Text & Upload */}
        <div className="space-y-8 animate-fade-in">
          <div className="space-y-4">
            <p className="text-[11px] font-bold text-accent-600 tracking-[0.2em] uppercase">
              {t("home.eyebrow")}
            </p>
            <h1 className="text-[36px] sm:text-[44px] font-extrabold tracking-tight leading-[1.15] text-primary-900 font-heading">
              {t("home.hero.title")}
            </h1>
            <p className="text-[15px] text-neutral-600 font-medium leading-relaxed max-w-md">
              {t("home.hero.subtitle")}
            </p>
          </div>

          <div className="bg-neutral-50 border border-neutral-200 rounded-[8px] p-5 shadow-sm max-w-md relative hover:border-accent-500/50 transition-colors">
            <input 
              type="file" 
              ref={fileInputRef} 
              className="hidden" 
              accept=".pdf,image/png,image/jpeg,text/plain"
              onChange={handleFileChange}
            />
            
            <div className="flex flex-col items-center justify-center text-center space-y-4 border-2 border-dashed border-neutral-200 rounded-[4px] p-6 hover:bg-white transition-colors cursor-pointer group" onClick={() => fileInputRef.current?.click()}>
              {!isUploading && <Upload className="w-6 h-6 text-neutral-400 group-hover:text-accent-500 transition-colors" />}
              {isUploading && <Loader2 className="w-6 h-6 animate-spin text-accent-500" />}
              
              <div className="space-y-1">
                <p className="text-[14px] font-bold text-primary-900">
                  {isUploading ? t("home.upload.processing") : t("home.upload.drop")}
                </p>
                <p className="text-[11px] font-bold text-neutral-400 uppercase tracking-widest">
                  {t("home.upload.formats")}
                </p>
              </div>

              <Button 
                size="sm" 
                className="bg-primary-900 hover:bg-primary-800 text-white font-bold px-6 py-2 text-[13px] rounded-[6px] transition-colors shadow-sm"
                disabled={isUploading}
                onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click(); }}
              >
                {t("home.upload.button")}
              </Button>
            </div>
            
            {error && (
              <div className="mt-4 flex items-start gap-2 text-[13px] text-error-700 bg-error-50 p-3 rounded-[4px] border border-error-200">
                <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                <p className="font-medium">{error}</p>
              </div>
            )}
          </div>
        </div>

        {/* RIGHT: Live Product Preview */}
        <div className="relative animate-slide-up lg:mt-0 mt-8">
          <div className="relative bg-white rounded-[12px] border border-neutral-200 shadow-xl overflow-hidden flex flex-col">
            <div className="px-5 py-3 border-b border-neutral-100 flex items-center justify-between bg-neutral-50/50">
              <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest">{t("home.live_preview")}</span>
              <span className="text-[10px] font-bold text-primary-900 bg-neutral-100 px-2 py-1 rounded">{t("home.q1_results")}</span>
            </div>
            
            <div className="p-6 md:p-8 space-y-6">
              <div className="space-y-1 pb-4 border-b border-neutral-100">
                <p className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest">{t("home.revenue")}</p>
                <div className="flex items-baseline gap-2">
                  <span className="text-[28px] font-extrabold text-primary-900 tracking-tight font-heading">₹722,750</span>
                  <span className="text-[13px] font-bold text-neutral-400">Mn</span>
                </div>
                <div className="flex items-center gap-1.5 mt-1">
                  <div className="w-1.5 h-1.5 rounded-full bg-success-600"></div>
                  <span className="text-[12px] font-bold text-success-600">+13.9% YoY</span>
                </div>
              </div>

              <div className="relative pl-5 border-l-2 border-neutral-200 space-y-5">
                <div className="relative">
                  <div className="absolute -left-[25.5px] top-1.5 w-2.5 h-2.5 bg-neutral-100 border-2 border-neutral-300 rounded-full"></div>
                  <p className="text-[10px] font-bold text-accent-600 uppercase tracking-widest mb-1">{t("home.bharat_explains")}</p>
                  <p className="text-[14px] font-medium text-primary-900">
                    Revenue increased 13.9% year over year.
                  </p>
                </div>
                
                <div className="relative">
                  <div className="absolute -left-[25.5px] top-1.5 w-2.5 h-2.5 bg-neutral-100 border-2 border-neutral-300 rounded-full"></div>
                  <p className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest mb-1">{t("home.why_it_matters")}</p>
                  <p className="text-[13px] font-medium text-neutral-600">
                    Revenue describes the scale of business activity.
                  </p>
                </div>

                <div className="relative pt-1">
                  <div className="absolute -left-[25.5px] top-3.5 w-2.5 h-2.5 bg-white border-2 border-accent-500 rounded-full"></div>
                  <span className="inline-flex items-center text-[10px] font-bold uppercase tracking-widest text-primary-900 border border-neutral-200 px-2.5 py-1 rounded bg-neutral-50">
                    {t("home.source_page")}
                  </span>
                </div>
              </div>
            </div>

            {/* Small Ask Bharat Moment */}
            <div className="bg-neutral-50 p-4 border-t border-neutral-100 flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-primary-900 uppercase tracking-widest">{t("home.ask_bharat")}</span>
                <span className="text-[12px] font-medium text-neutral-500 italic">{t("home.explain_hindi")}</span>
              </div>
              <div className="bg-white border border-neutral-200 rounded p-3 text-[13px] font-medium text-primary-900 shadow-sm">
                <span className="text-accent-600 font-bold mr-2">↳</span>
                Revenue ka simple matlab hai ki company ne is quarter mein kitna paisa kamaya hai.
              </div>
            </div>
          </div>
        </div>

      </section>

      {/* 2. INTELLIGENCE PATH */}
      <section className="max-w-4xl w-full mt-16 md:mt-24 mb-20 relative before:absolute before:inset-[-64px] before:bg-grid-pattern before:opacity-50 before:-z-10 before:rounded-[24px] before:pointer-events-none">
        <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between relative px-2">
          {/* Connector line (desktop) */}
          <div className="hidden md:block absolute top-[14px] left-[8%] right-[8%] h-[2px] bg-neutral-200"></div>
          {/* Connector line (mobile) */}
          <div className="md:hidden absolute left-[15px] top-2 bottom-2 w-[2px] bg-neutral-200"></div>

          {[
            { step: "01", label: t("home.path.01"), sub: t("home.path.01.sub") },
            { step: "02", label: t("home.path.02"), sub: t("home.path.02.sub") },
            { step: "03", label: t("home.path.03"), sub: t("home.path.03.sub") },
            { step: "04", label: t("home.path.04"), sub: t("home.path.04.sub") },
            { step: "05", label: t("home.path.05"), sub: t("home.path.05.sub") },
            { step: "06", label: t("home.path.06"), sub: t("home.path.06.sub") }
          ].map((item, idx) => (
            <div key={idx} className="relative flex md:flex-col items-center md:items-center gap-4 md:gap-3 mb-6 md:mb-0 z-10">
              <div className="w-8 h-8 bg-neutral-100 border-2 border-neutral-300 rounded-full flex items-center justify-center text-[10px] font-bold text-neutral-400">
                {item.step}
              </div>
              <div className="md:text-center">
                <p className="text-[11px] font-bold text-primary-900 uppercase tracking-widest leading-none">{item.label}</p>
                <p className="text-[12px] font-medium text-neutral-500 mt-1">{item.sub}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* 3. WHY THIS IS DIFFERENT */}
      <section className="max-w-5xl w-full mb-24 py-12 border-t border-b border-neutral-200">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 md:gap-0">
          <div className="md:border-r border-neutral-200 md:pr-10">
            <h3 className="text-[12px] font-bold text-accent-600 uppercase tracking-widest mb-3">{t("home.diff.understand")}</h3>
            <p className="text-[15px] font-medium text-primary-900">{t("home.diff.understand.sub")}</p>
          </div>
          <div className="md:border-r border-neutral-200 md:px-10">
            <h3 className="text-[12px] font-bold text-accent-600 uppercase tracking-widest mb-3">{t("home.diff.learn")}</h3>
            <p className="text-[15px] font-medium text-primary-900">{t("home.diff.learn.sub")}</p>
          </div>
          <div className="md:pl-10">
            <h3 className="text-[12px] font-bold text-accent-600 uppercase tracking-widest mb-3">{t("home.diff.verify")}</h3>
            <p className="text-[15px] font-medium text-primary-900">{t("home.diff.verify.sub")}</p>
          </div>
        </div>
      </section>

      {/* 4. LANGUAGE / VOICE & BHARAT SPECIFIC MOMENT */}
      <section className="max-w-4xl w-full mb-24 flex flex-col md:flex-row items-start md:items-stretch gap-8">
        
        {/* Language Moment */}
        <div className="flex-1 bg-white border border-neutral-200 rounded-[8px] p-8">
          <h3 className="text-[11px] font-bold text-neutral-400 uppercase tracking-widest mb-4">{t("home.lang.title")}</h3>
          <p className="text-[18px] font-bold text-primary-900 mb-6">{t("home.lang.heading")}</p>
          <div className="flex items-center gap-3 mb-6">
            <span className="text-[11px] font-bold bg-neutral-100 text-neutral-500 px-3 py-1.5 rounded-[4px] uppercase tracking-widest border border-neutral-200">English</span>
            <span className="text-[11px] font-bold bg-primary-900 text-white px-3 py-1.5 rounded-[4px] uppercase tracking-widest shadow-sm">हिंदी</span>
            <span className="text-[11px] font-bold bg-neutral-100 text-neutral-500 px-3 py-1.5 rounded-[4px] uppercase tracking-widest border border-neutral-200">Hinglish</span>
          </div>
          <div className="bg-neutral-50 p-4 border border-neutral-200 rounded-[4px]">
            <p className="text-[14px] font-medium text-primary-900 italic">"Revenue ka simple matlab kya hai?"</p>
          </div>
        </div>

        {/* Voice Moment */}
        <div className="flex-1 bg-white border border-neutral-200 rounded-[8px] p-8">
          <h3 className="text-[11px] font-bold text-neutral-400 uppercase tracking-widest mb-4">{t("home.voice.title")}</h3>
          <p className="text-[18px] font-bold text-primary-900 mb-6">{t("home.voice.heading")}</p>
          
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-full bg-neutral-100 border border-neutral-200 flex items-center justify-center text-primary-900">
              <Mic className="w-4 h-4" />
            </div>
            <p className="text-[14px] font-medium text-primary-900 italic">"Revenue ka simple meaning kya hai?"</p>
          </div>
          
          <p className="text-[14px] font-medium text-neutral-600">
            {t("home.voice.sub")}
          </p>
        </div>

      </section>

      {/* 5. FINAL UPLOAD CTA */}
      <section className="text-center pb-12">
        <Button 
          variant="outline"
          className="border-primary-900 text-primary-900 hover:bg-primary-900 hover:text-white font-bold px-8 py-3 rounded-[6px] transition-colors uppercase tracking-widest text-[12px]"
          onClick={() => fileInputRef.current?.click()}
          disabled={isUploading}
        >
          {t("home.cta.upload")} <ArrowRight className="ml-2 w-4 h-4" />
        </Button>
      </section>
      
    </div>
  );
}
