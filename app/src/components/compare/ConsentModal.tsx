import { useState, useEffect, useRef } from "react";
import { Sparkles, AlertCircle, X, Check, Lock, Info, ShieldCheck, Eye, EyeOff } from "lucide-react";
import { Button } from "../ui/Button";
import {
  getConsentTerms,
  grantConsent,
  withdrawConsent,
  getTransmissionPreview,
  type ConsentResponse,
  type TransmissionPreview,
} from "../../lib/compareApi";
import { getTranslation, type SupportedLanguage } from "../../lib/translations";

interface ConsentModalProps {
  sessionId: string;
  sessionToken: string;
  isOpen: boolean;
  onClose: () => void;
  onConfirmLocal: () => void;
  onConfirmAi: () => void;
  language: SupportedLanguage;
}

export function ConsentModal({
  sessionId,
  sessionToken,
  isOpen,
  onClose,
  onConfirmLocal,
  onConfirmAi,
  language,
}: ConsentModalProps) {
  const [selectedMode, setSelectedMode] = useState<"LOCAL" | "AI">("LOCAL");
  const [consentGranted, setConsentGranted] = useState(false);
  const [checkboxChecked, setCheckboxChecked] = useState(false);
  const [termsData, setTermsData] = useState<ConsentResponse | null>(null);
  const [previewData, setPreviewData] = useState<TransmissionPreview | null>(null);
  const [showRawPreview, setShowRawPreview] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const t = (key: string) => getTranslation(key, language);

  const modalRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const previousActiveElement = useRef<HTMLElement | null>(null);

  // Focus trap, initial focus, escape handling, and focus restoration
  useEffect(() => {
    if (isOpen) {
      previousActiveElement.current = document.activeElement as HTMLElement | null;

      // Initial focus on close button
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

          if (e.shiftKey) {
            if (document.activeElement === firstElement || !modalRef.current.contains(document.activeElement)) {
              e.preventDefault();
              lastElement.focus();
            }
          } else {
            if (document.activeElement === lastElement || !modalRef.current.contains(document.activeElement)) {
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
    }
  }, [isOpen, onClose]);

  useEffect(() => {
    if (isOpen) {
      setIsLoading(true);
      setError(null);
      getConsentTerms(sessionId, sessionToken)
        .then((res) => {
          setTermsData(res);
          setConsentGranted(res.consent_granted);
        })
        .catch((err) => {
          setError(err.message || t("compare.consent.err_expired"));
        })
        .finally(() => {
          setIsLoading(false);
        });

      setLoadingPreview(true);
      getTransmissionPreview(sessionId, sessionToken)
        .then((prev) => {
          setPreviewData(prev);
        })
        .catch((_err) => {
          // Non-blocking if documents not yet parsed
        })
        .finally(() => {
          setLoadingPreview(false);
        });
    }
  }, [isOpen, sessionId, sessionToken]);

  if (!isOpen) return null;

  const handleGrantConsentAndProceed = async () => {
    if (!checkboxChecked && !consentGranted) {
      setError(t("compare.consent.err_network"));
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      if (!consentGranted) {
        await grantConsent(sessionId, sessionToken, previewData?.payload_hash || null);
      }
      onConfirmAi();
    } catch (err: any) {
      setError(err.message || t("compare.consent.err_network"));
    } finally {
      setIsLoading(false);
    }
  };

  const handleWithdrawConsent = async () => {
    setIsLoading(true);
    setError(null);
    try {
      await withdrawConsent(sessionId, sessionToken);
      setConsentGranted(false);
      setCheckboxChecked(false);
      setSelectedMode("LOCAL");
    } catch (err: any) {
      setError(err.message || t("compare.consent.err_declining"));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs font-sans animate-fade-in" role="dialog" aria-modal="true" aria-labelledby="consent-modal-title">
      <div ref={modalRef} className="bg-white rounded-2xl max-w-2xl w-full p-6 sm:p-8 shadow-2xl border border-neutral-200 relative max-h-[90vh] overflow-y-auto space-y-6">
        {/* Close Button */}
        <button
          ref={closeButtonRef}
          onClick={onClose}
          className="absolute top-5 right-5 text-neutral-400 hover:text-neutral-700 p-1 rounded focus:outline-none focus:ring-2 focus:ring-accent-500"
          aria-label={t("compare.evidence.close")}
        >
          <X className="w-5 h-5" />
        </button>

        {/* Modal Header */}
        <div>
          <span className="text-xs font-bold text-accent-700 uppercase tracking-widest">
            {t("compare.consent.title")}
          </span>
          <h2 id="consent-modal-title" className="text-xl sm:text-2xl font-extrabold text-neutral-900 mt-1 font-heading">
            {t("compare.consent.modal_title")}
          </h2>
          <p className="text-xs text-neutral-600 mt-1">
            {t("compare.consent.modal_subtitle")}
          </p>
        </div>

        {/* Mode Selector Options */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Local Mode Card */}
          <div
            onClick={() => setSelectedMode("LOCAL")}
            className={`border-2 rounded-xl p-5 cursor-pointer transition-all space-y-3 ${
              selectedMode === "LOCAL"
                ? "border-primary-900 bg-primary-50/20 shadow-xs"
                : "border-neutral-200 hover:border-neutral-300"
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="w-9 h-9 rounded-lg bg-neutral-900 text-white flex items-center justify-center">
                <Lock className="w-4 h-4" />
              </div>
              <span className="text-[10px] font-extrabold uppercase bg-neutral-100 text-neutral-800 px-2.5 py-0.5 rounded-full">
                {t("compare.consent.mode_local_badge")}
              </span>
            </div>
            <div>
              <h3 className="text-sm font-bold text-neutral-900">{t("compare.consent.local_title")}</h3>
              <p className="text-xs text-neutral-600 mt-1.5 leading-relaxed">
                {t("compare.consent.local_desc")}
              </p>
            </div>
          </div>

          {/* AI-Assisted Mode Card */}
          <div
            onClick={() => setSelectedMode("AI")}
            className={`border-2 rounded-xl p-5 cursor-pointer transition-all space-y-3 ${
              selectedMode === "AI"
                ? "border-accent-600 bg-accent-50/20 shadow-xs"
                : "border-neutral-200 hover:border-neutral-300"
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="w-9 h-9 rounded-lg bg-accent-600 text-white flex items-center justify-center">
                <Sparkles className="w-4 h-4" />
              </div>
              <span className="text-[10px] font-extrabold uppercase bg-accent-100 text-accent-800 px-2.5 py-0.5 rounded-full">
                {t("compare.consent.mode_ai_badge")}
              </span>
            </div>
            <div>
              <h3 className="text-sm font-bold text-neutral-900">{t("compare.consent.ai_title")}</h3>
              <p className="text-xs text-neutral-600 mt-1.5 leading-relaxed">
                {t("compare.consent.ai_desc")}
              </p>
            </div>
          </div>
        </div>

        {/* AI Pre-Transmission Preview & Consent Details */}
        {selectedMode === "AI" && (
          <div className="bg-neutral-50 border border-neutral-200 rounded-xl p-5 space-y-4 text-xs animate-fade-in">
            {/* Pre-Transmission Itemization Box */}
            <div className="bg-white rounded-lg p-4 border border-neutral-200 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-neutral-900 font-bold text-xs">
                  <ShieldCheck className="w-4 h-4 text-accent-600" />
                  <span>{t("compare.consent.preview_heading")}</span>
                </div>
                {previewData?.payload_hash && (
                  <span className="font-mono text-[10px] bg-neutral-100 px-2 py-0.5 rounded text-neutral-600">
                    SHA: {previewData.payload_hash.slice(0, 10)}...
                  </span>
                )}
              </div>

              {loadingPreview ? (
                <p className="text-neutral-500 italic text-xs">{t("compare.consent.preview_loading")}</p>
              ) : previewData ? (
                <div className="space-y-2 text-[11px] text-neutral-700">
                  <div className="flex justify-between border-b border-neutral-100 pb-1.5">
                    <span className="font-semibold text-neutral-500">{t("compare.consent.target_filings")}</span>
                    <span className="font-medium text-neutral-900 text-right">
                      {previewData.document_names.join(" vs. ")}
                    </span>
                  </div>
                  <div className="flex justify-between border-b border-neutral-100 pb-1.5">
                    <span className="font-semibold text-neutral-500">{t("compare.consent.trans_scope")}</span>
                    <span className="font-medium text-neutral-900 text-right">
                      Selective Line Items ({previewData.selected_sections_and_pages.length} Excerpts · Zero Raw Files)
                    </span>
                  </div>
                  <div className="flex justify-between border-b border-neutral-100 pb-1.5">
                    <span className="font-semibold text-neutral-500">{t("compare.consent.ai_service")}</span>
                    <span className="font-medium text-neutral-900">{previewData.ai_service_provider}</span>
                  </div>
                  <div className="flex items-center justify-between border-b border-neutral-100 pb-1.5">
                    <span className="font-semibold text-neutral-500">{t("compare.consent.pii_sanitization")}</span>
                    <span
                      className={`font-semibold px-2 py-0.5 rounded text-[10px] ${
                        previewData.total_pii_redacted_count > 0
                          ? "bg-amber-100 text-amber-800"
                          : "bg-success-100 text-success-800"
                      }`}
                    >
                      {previewData.total_pii_redacted_count > 0
                        ? `${previewData.total_pii_redacted_count} ${t("compare.consent.pii_masked_count")}`
                        : t("compare.consent.pii_zero_detected")}
                    </span>
                  </div>

                  {/* Imperfect Redaction Amber Disclosure */}
                  <div className="flex items-start gap-2 bg-amber-50/80 border border-amber-200/80 rounded-lg p-2.5 text-[11px] text-amber-900">
                    <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                    <p className="leading-relaxed">
                      {previewData.redaction_disclaimer}
                    </p>
                  </div>

                  {/* Inspect Sanitized Text Excerpt Toggle */}
                  <div className="pt-1">
                    <button
                      type="button"
                      onClick={() => setShowRawPreview(!showRawPreview)}
                      className="text-[11px] text-accent-700 font-semibold hover:underline flex items-center gap-1.5"
                    >
                      {showRawPreview ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                      {showRawPreview ? t("compare.consent.hide_payload") : t("compare.consent.inspect_payload")}
                    </button>
                    {showRawPreview && (
                      <div className="mt-2 p-3 bg-neutral-900 text-neutral-100 rounded text-[10px] font-mono whitespace-pre-line max-h-48 overflow-y-auto leading-normal">
                        {previewData.sanitized_payload_preview}
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <p className="text-neutral-500 text-xs italic">{t("compare.consent.preview_ready_notice")}</p>
              )}
            </div>

            {/* Google Terms Notice */}
            <div className="flex items-start gap-2.5">
              <Info className="w-4 h-4 text-accent-600 shrink-0 mt-0.5" />
              <div className="space-y-1">
                <p className="font-bold text-neutral-900">{t("compare.consent.terms_header")}</p>
                <div className="text-[11px] text-neutral-600 leading-relaxed space-y-1 whitespace-pre-line font-mono bg-white p-3 rounded border border-neutral-200/80 max-h-32 overflow-y-auto">
                  {termsData?.terms_disclosure || "Loading disclosure terms from backend..."}
                </div>
              </div>
            </div>

            {termsData?.withdrawal_limitations && (
              <p className="text-[11px] text-neutral-500 italic">
                {termsData.withdrawal_limitations}
              </p>
            )}

            {/* Checkbox */}
            <label className="flex items-start gap-3 cursor-pointer pt-2 border-t border-neutral-200">
              <input
                type="checkbox"
                checked={checkboxChecked || consentGranted}
                disabled={consentGranted}
                onChange={(e) => setCheckboxChecked(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-neutral-300 text-accent-600 focus:ring-accent-500"
              />
              <span className="text-[11px] text-neutral-800 font-medium">
                {t("compare.consent.checkbox")}
              </span>
            </label>

            {consentGranted && (
              <div className="flex items-center justify-between pt-2">
                <span className="text-xs font-bold text-success-700 flex items-center gap-1.5">
                  <Check className="w-4 h-4" /> {t("compare.consent.active_consent_notice")}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleWithdrawConsent}
                  disabled={isLoading}
                  className="text-xs text-error-600 hover:bg-error-50"
                >
                  {t("compare.consent.withdraw")}
                </Button>
              </div>
            )}
          </div>
        )}

        {/* Error message */}
        {error && (
          <div className="flex items-start gap-2 p-3 bg-error-50 border border-error-200 rounded-lg text-error-700 text-xs">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <p className="font-medium">{error}</p>
          </div>
        )}

        {/* Modal Actions with Explicit Allow & Decline Controls */}
        <div className="flex items-center justify-between pt-2 border-t border-neutral-100">
          <Button variant="ghost" size="sm" onClick={onClose} className="text-xs font-semibold">
            {t("compare.consent.cancel_btn")}
          </Button>

          <div className="flex items-center gap-3">
            {selectedMode === "AI" && (
              <Button
                variant="outline"
                size="md"
                onClick={onConfirmLocal}
                disabled={isLoading}
                className="text-xs font-semibold text-neutral-700 border-neutral-300 hover:bg-neutral-50"
              >
                {t("compare.consent.decline_btn")}
              </Button>
            )}

            {selectedMode === "LOCAL" ? (
              <Button
                size="md"
                onClick={onConfirmLocal}
                disabled={isLoading}
                className="bg-primary-900 text-white font-bold text-xs px-6"
              >
                {t("compare.consent.start_local")}
              </Button>
            ) : (
              <Button
                size="md"
                onClick={handleGrantConsentAndProceed}
                disabled={isLoading || (!checkboxChecked && !consentGranted)}
                className="bg-accent-600 hover:bg-accent-700 text-white font-bold text-xs px-6"
              >
                {isLoading ? t("compare.consent.recording_consent") : t("compare.consent.allow_transmit_btn")}
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
