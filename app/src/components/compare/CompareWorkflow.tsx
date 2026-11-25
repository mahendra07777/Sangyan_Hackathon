import { useState, useEffect, useRef } from "react";
import { ArrowLeft } from "lucide-react";
import { CompareUpload } from "./CompareUpload";
import { MetadataReview } from "./MetadataReview";
import { CompatibilityView } from "./CompatibilityView";
import { ConsentModal } from "./ConsentModal";
import { ProcessingView } from "./ProcessingView";
import { ComparisonDashboard } from "./ComparisonDashboard";
import {
  createCompareSession,
  deleteCompareSession,
  uploadCompareDocuments,
  getCompareMetadata,
  updateCompareMetadata,
  getCompareCompatibility,
  startCompareProcessing,
  getCompareStatus,
  cancelCompareProcessing,
  getCompareResults,
  type ComparisonMode,
  type ComparisonDocument,
  type DocumentMetadata,
  type MetadataUpdateRequest,
  type CompatibilityReport,
  type ProcessingStatusResponse,
  type ComparisonResult,
} from "../../lib/compareApi";
import { getTranslation, type SupportedLanguage } from "../../lib/translations";

interface CompareWorkflowProps {
  onBackToHome: () => void;
  language: SupportedLanguage;
}

type WorkflowStep = "upload" | "metadata" | "compatibility" | "processing" | "dashboard";

export function CompareWorkflow({ onBackToHome, language }: CompareWorkflowProps) {
  const [step, setStep] = useState<WorkflowStep>("upload");

  // Session State
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionToken, setSessionToken] = useState<string | null>(null);
  const [documents, setDocuments] = useState<ComparisonDocument[]>([]);
  const [metadata, setMetadata] = useState<Record<string, DocumentMetadata>>({});
  const [compatibility, setCompatibility] = useState<CompatibilityReport | null>(null);
  const [processingStatus, setProcessingStatus] = useState<ProcessingStatusResponse | null>(null);
  const [comparisonResult, setComparisonResult] = useState<ComparisonResult | null>(null);

  // Loading & Modals
  const [isUploading, setIsUploading] = useState(false);
  const [isConsentModalOpen, setIsConsentModalOpen] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);

  const pollTimerRef = useRef<number | null>(null);
  const t = (key: string) => getTranslation(key, language);

  // Cleanup on unmount or session reset
  const cleanupSession = async () => {
    if (pollTimerRef.current) {
      window.clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    if (sessionId && sessionToken) {
      try {
        await deleteCompareSession(sessionId, sessionToken);
      } catch {
        // ignore
      }
    }
    setSessionId(null);
    setSessionToken(null);
    setDocuments([]);
    setMetadata({});
    setCompatibility(null);
    setProcessingStatus(null);
    setComparisonResult(null);
    setStep("upload");
  };

  useEffect(() => {
    return () => {
      if (pollTimerRef.current) {
        window.clearInterval(pollTimerRef.current);
      }
    };
  }, []);

  // STEP 1: Upload Documents & Detect Metadata
  const handleStartUpload = async (files: File[], mode: ComparisonMode) => {
    setIsUploading(true);
    setGlobalError(null);
    try {
      // 1. Initialize session
      const sessionResp = await createCompareSession(mode);
      const newSessionId = sessionResp.session_id;
      const newToken = sessionResp.session_token;
      setSessionId(newSessionId);
      setSessionToken(newToken);

      // 2. Upload files
      const uploadedDocs = await uploadCompareDocuments(newSessionId, newToken, files);
      setDocuments(uploadedDocs);

      // 3. Fetch initial metadata
      const detectedMetadata = await getCompareMetadata(newSessionId, newToken);
      setMetadata(detectedMetadata);

      setStep("metadata");
    } catch (err: any) {
      setGlobalError(err.message || "Failed to initialize comparison session.");
      throw err;
    } finally {
      setIsUploading(false);
    }
  };

  // STEP 2: Update Metadata for single document
  const handleUpdateMetadata = async (docId: string, updates: MetadataUpdateRequest) => {
    if (!sessionId || !sessionToken) return;
    const updated = await updateCompareMetadata(sessionId, sessionToken, docId, updates);
    setMetadata((prev) => ({ ...prev, [docId]: updated }));
  };

  // Check Compatibility and advance
  const handleProceedToCompatibility = async () => {
    if (!sessionId || !sessionToken) return;
    setGlobalError(null);
    try {
      const compatReport = await getCompareCompatibility(sessionId, sessionToken);
      setCompatibility(compatReport);
      setStep("compatibility");
    } catch (err: any) {
      setGlobalError(err.message || "Failed to evaluate compatibility matrix.");
    }
  };

  // STEP 3: Prompt Consent Modal
  const handleOpenConsentModal = () => {
    setIsConsentModalOpen(true);
  };

  // STEP 4: Start Processing (Local or AI)
  const handleStartProcessing = async () => {
    if (!sessionId || !sessionToken) return;
    setIsConsentModalOpen(false);
    setStep("processing");
    setGlobalError(null);

    try {
      const initialStatus = await startCompareProcessing(sessionId, sessionToken, language);
      setProcessingStatus(initialStatus);

      // Start Polling status
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
      pollTimerRef.current = window.setInterval(async () => {
        try {
          const s = await getCompareStatus(sessionId, sessionToken);
          setProcessingStatus(s);

          if (s.is_completed || s.current_stage === "COMPLETED") {
            if (pollTimerRef.current) clearInterval(pollTimerRef.current);
            // Fetch final result
            const result = await getCompareResults(sessionId, sessionToken);
            setComparisonResult(result);
            setStep("dashboard");
          } else if (s.is_cancelled || s.current_stage === "CANCELLED") {
            if (pollTimerRef.current) clearInterval(pollTimerRef.current);
            setStep("compatibility");
          } else if (s.current_stage === "FAILED") {
            if (pollTimerRef.current) clearInterval(pollTimerRef.current);
            setGlobalError(s.error || "Comparison analysis failed.");
            setStep("compatibility");
          }
        } catch (pollErr: any) {
          if (pollTimerRef.current) clearInterval(pollTimerRef.current);
          setGlobalError(pollErr.message || "Lost connection to processing worker.");
        }
      }, 1000);
    } catch (err: any) {
      setGlobalError(err.message || "Failed to trigger processing pipeline.");
      setStep("compatibility");
    }
  };

  // Cancel in-flight processing
  const handleCancelProcessing = async () => {
    if (!sessionId || !sessionToken) return;
    setIsCancelling(true);
    try {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
      await cancelCompareProcessing(sessionId, sessionToken);
      setStep("compatibility");
    } catch (err: any) {
      setGlobalError(err.message || "Failed to cancel processing.");
    } finally {
      setIsCancelling(false);
    }
  };

  // Exit back to home
  const handleBackToHome = async () => {
    await cleanupSession();
    onBackToHome();
  };

  return (
    <div className="min-h-full flex flex-col font-sans">
      {/* Top Breadcrumb Navigation */}
      <div className="h-12 border-b border-neutral-200 bg-white/70 px-4 sm:px-8 flex items-center justify-between shrink-0">
        <button
          onClick={handleBackToHome}
          className="text-xs font-semibold text-neutral-600 hover:text-neutral-900 flex items-center gap-1.5 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          {t("compare.back")}
        </button>

        {step !== "upload" && (
          <div className="hidden sm:flex items-center gap-2 text-xs font-bold text-neutral-400">
            <span className="text-neutral-500">{t("compare.wizard.step.upload")}</span>
            <span>→</span>
            <span className={step === "metadata" ? "text-primary-900" : ""}>{t("compare.wizard.step.metadata")}</span>
            <span>→</span>
            <span className={step === "compatibility" ? "text-primary-900" : ""}>{t("compare.wizard.step.compatibility")}</span>
            <span>→</span>
            <span className={step === "processing" ? "text-primary-900" : ""}>{t("compare.wizard.step.processing")}</span>
            <span>→</span>
            <span className={step === "dashboard" ? "text-primary-900 font-extrabold" : ""}>{t("compare.wizard.step.results")}</span>
          </div>
        )}

        <div className="text-[11px] font-mono text-neutral-400">
          {sessionId ? `Session: ${sessionId.slice(0, 8)}…` : t("compare.workflow.ephemeral_session")}
        </div>
      </div>

      {/* Global Error Alert */}
      {globalError && (
        <div className="max-w-4xl mx-auto mt-4 px-4 w-full">
          <div className="p-3 bg-error-50 text-error-700 text-xs rounded-lg border border-error-200 flex items-center justify-between">
            <span>{globalError}</span>
            <button onClick={() => setGlobalError(null)} className="font-bold text-xs" aria-label={t("compare.workflow.dismiss_error_aria")}>
              ✕
            </button>
          </div>
        </div>
      )}

      {/* Main Step Views */}
      <div className="flex-1 overflow-y-auto">
        {step === "upload" && (
          <CompareUpload
            onStartUpload={handleStartUpload}
            isLoading={isUploading}
            language={language}
          />
        )}

        {step === "metadata" && (
          <MetadataReview
            documents={documents}
            metadata={metadata}
            onUpdateMetadata={handleUpdateMetadata}
            onProceed={handleProceedToCompatibility}
            onBack={() => setStep("upload")}
            language={language}
          />
        )}

        {step === "compatibility" && compatibility && (
          <CompatibilityView
            report={compatibility}
            onProceed={handleOpenConsentModal}
            onBackToMetadata={() => setStep("metadata")}
            language={language}
          />
        )}

        {step === "processing" && (
          <ProcessingView
            status={processingStatus}
            onCancel={handleCancelProcessing}
            isCancelling={isCancelling}
            language={language}
          />
        )}

        {step === "dashboard" && comparisonResult && sessionToken && (
          <ComparisonDashboard
            result={comparisonResult}
            sessionToken={sessionToken}
            onNewComparison={cleanupSession}
            language={language}
          />
        )}
      </div>

      {/* Consent & Mode Modal */}
      {sessionId && sessionToken && (
        <ConsentModal
          sessionId={sessionId}
          sessionToken={sessionToken}
          isOpen={isConsentModalOpen}
          onClose={() => setIsConsentModalOpen(false)}
          onConfirmLocal={handleStartProcessing}
          onConfirmAi={handleStartProcessing}
          language={language}
        />
      )}
    </div>
  );
}
