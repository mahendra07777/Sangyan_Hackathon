import { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { ShieldCheck, X, AlertCircle, Loader2, Sparkles, CheckCircle2 } from "lucide-react";
import { Button } from "../ui/Button";
import {
  getAiSessionPreview,
  activateAiSession,
  type AISessionPreviewResponse,
  type AISessionCredentials,
} from "../../lib/api";
import { getTranslation, type SupportedLanguage } from "../../lib/translations";

interface SingleDocConsentModalProps {
  isOpen: boolean;
  language: SupportedLanguage;
  onClose: () => void;
  onActivated: (credentials: AISessionCredentials, expiresInSeconds: number) => void;
}

export function SingleDocConsentModal({
  isOpen,
  language,
  onClose,
  onActivated,
}: SingleDocConsentModalProps) {
  const [preview, setPreview] = useState<AISessionPreviewResponse | null>(null);
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);
  const [isActivating, setIsActivating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const t = (key: string) => getTranslation(key, language);

  const modalRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const previousActiveElement = useRef<HTMLElement | null>(null);

  // Fetch one-time AI activation disclosure preview on open ONLY (never transmits data)
  useEffect(() => {
    if (!isOpen) return;

    let active = true;
    setIsLoadingPreview(true);
    setIsActivating(false);
    setError(null);
    setPreview(null);

    getAiSessionPreview()
      .then((res) => {
        if (active) setPreview(res);
      })
      .catch((err: unknown) => {
        if (active) {
          const message = err instanceof Error ? err.message : t("error.network");
          setError(message);
        }
      })
      .finally(() => {
        if (active) setIsLoadingPreview(false);
      });

    return () => {
      active = false;
    };
  }, [isOpen]);

  // Keyboard accessibility: Escape handling, Tab focus trap, and focus restoration
  useEffect(() => {
    if (!isOpen) return;

    previousActiveElement.current =
      (typeof window !== "undefined" ? window.document.activeElement : null) as HTMLElement | null;

    const timer = setTimeout(() => {
      closeButtonRef.current?.focus();
    }, 50);

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        onClose();
        return;
      }

      if (e.key === "Tab") {
        if (!modalRef.current) return;
        const focusable = modalRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        );
        if (focusable.length === 0) {
          e.preventDefault();
          return;
        }
        const firstElement = focusable[0];
        const lastElement = focusable[focusable.length - 1];
        const activeEl = window.document.activeElement;

        if (e.shiftKey) {
          if (activeEl === firstElement || !modalRef.current.contains(activeEl)) {
            e.preventDefault();
            lastElement.focus();
          }
        } else {
          if (activeEl === lastElement || !modalRef.current.contains(activeEl)) {
            e.preventDefault();
            firstElement.focus();
          }
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      clearTimeout(timer);
      window.removeEventListener("keydown", handleKeyDown);
      if (previousActiveElement.current && typeof previousActiveElement.current.focus === "function") {
        previousActiveElement.current.focus();
      }
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleActivate = async () => {
    if (!preview || isActivating || isLoadingPreview) return;
    setIsActivating(true);
    setError(null);
    try {
      const res = await activateAiSession(preview.activation_id);
      onActivated(
        { aiSessionId: res.ai_session_id, aiSessionToken: res.ai_session_token },
        res.expires_in_seconds
      );
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : t("error.network");
      setError(message);
    } finally {
      setIsActivating(false);
    }
  };

  const modalContent = (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs font-sans animate-fade-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="ai-activation-dialog-title"
    >
      <div
        ref={modalRef}
        className="bg-white rounded-2xl w-full max-w-lg shadow-2xl border border-neutral-200 flex flex-col overflow-hidden max-h-[90vh]"
      >
        {/* Header */}
        <div className="px-5 py-4 border-b border-neutral-200 bg-neutral-50 flex items-start justify-between gap-4 shrink-0">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-lg bg-accent-50 border border-accent-200 text-accent-600 flex items-center justify-center shrink-0 mt-0.5">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h3
                id="ai-activation-dialog-title"
                className="text-sm font-extrabold text-primary-900 tracking-tight"
              >
                {t("ai.activation.title")}
              </h3>
              <p className="text-[12px] text-neutral-600 font-medium mt-0.5 leading-snug">
                {t("ai.activation.subtitle")}
              </p>
            </div>
          </div>

          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            className="w-8 h-8 rounded-lg hover:bg-neutral-200 text-neutral-500 hover:text-neutral-900 flex items-center justify-center transition-colors shrink-0 focus:outline-none focus:ring-2 focus:ring-accent-500"
            aria-label={t("ai.activation.close_aria")}
            title={t("ai.activation.close_aria")}
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="p-5 overflow-y-auto space-y-4 text-xs">
          {error && (
            <div className="p-3 bg-error-50 border border-error-200 rounded-lg text-error-800 flex items-start gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span className="font-medium leading-relaxed">{error}</span>
            </div>
          )}

          {isLoadingPreview ? (
            <div className="py-10 flex flex-col items-center justify-center gap-3 text-neutral-500">
              <Loader2 className="w-6 h-6 animate-spin text-accent-600" />
              <span className="font-semibold">{t("ai.activation.loading")}</span>
            </div>
          ) : preview ? (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 bg-neutral-50 border border-neutral-200 rounded-lg p-3">
                <div>
                  <span className="block text-[10px] font-bold text-neutral-400 uppercase tracking-wider">
                    {t("ai.activation.recipient_label")}
                  </span>
                  <span className="font-bold text-neutral-900">{preview.recipient}</span>
                </div>
                <div>
                  <span className="block text-[10px] font-bold text-neutral-400 uppercase tracking-wider">
                    {t("ai.activation.scope_label")}
                  </span>
                  <span className="font-bold text-neutral-900">{t("ai.activation.scope_value")}</span>
                </div>
                <div className="sm:col-span-2">
                  <span className="block text-[10px] font-bold text-neutral-400 uppercase tracking-wider">
                    {t("ai.activation.purpose_label")}
                  </span>
                  <span className="font-medium text-neutral-800">{preview.purpose}</span>
                </div>
              </div>

              <div className="space-y-2">
                <span className="flex items-center gap-1.5 text-[10px] font-extrabold text-neutral-600 uppercase tracking-wider">
                  <ShieldCheck className="w-3.5 h-3.5 text-accent-600" />
                  {t("ai.activation.disclosure_heading")}
                </span>
                <ul className="space-y-2 bg-neutral-50 border border-neutral-200 rounded-lg p-3.5 text-neutral-700 leading-relaxed">
                  {preview.disclosure_items.map((item, idx) => (
                    <li key={idx} className="flex items-start gap-2">
                      <CheckCircle2 className="w-3.5 h-3.5 text-accent-600 shrink-0 mt-0.5" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="p-3 bg-amber-50/80 border border-amber-200 rounded-lg text-[11px] text-amber-950 leading-relaxed font-medium">
                {t("ai.activation.fallback_note")}
              </div>
            </>
          ) : null}
        </div>

        {/* Footer */}
        <div className="px-5 py-3.5 border-t border-neutral-200 bg-neutral-50 flex flex-col-reverse sm:flex-row sm:items-center sm:justify-end gap-2.5 shrink-0">
          <Button
            variant="outline"
            size="sm"
            onClick={onClose}
            disabled={isActivating}
            data-testid="decline-ai-activation-btn"
            className="text-xs font-bold border-neutral-300 text-neutral-700 hover:bg-neutral-100"
          >
            {t("ai.activation.decline_btn")}
          </Button>
          <Button
            size="sm"
            onClick={handleActivate}
            disabled={!preview || isLoadingPreview || isActivating}
            data-testid="confirm-ai-activation-btn"
            className="text-xs font-bold bg-primary-900 hover:bg-primary-800 text-white shadow-sm disabled:opacity-50"
          >
            {isActivating ? t("ai.activation.activating") : t("ai.activation.enable_btn")}
          </Button>
        </div>
      </div>
    </div>
  );

  return typeof window !== "undefined" ? createPortal(modalContent, window.document.body) : modalContent;
}
