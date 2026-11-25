import { Loader2, CheckCircle2, StopCircle } from "lucide-react";
import { Button } from "../ui/Button";
import type { ProcessingStatusResponse, ProcessingStage } from "../../lib/compareApi";
import { getTranslation, type SupportedLanguage } from "../../lib/translations";

interface ProcessingViewProps {
  status: ProcessingStatusResponse | null;
  onCancel: () => Promise<void>;
  isCancelling: boolean;
  language: SupportedLanguage;
}

const STAGES: { key: ProcessingStage; labelKey: string }[] = [
  { key: "INITIALIZED", labelKey: "compare.process.stage.INITIALIZED" },
  { key: "IDENTIFYING_METADATA", labelKey: "compare.process.stage.IDENTIFYING_METADATA" },
  { key: "VALIDATING_COMPATIBILITY", labelKey: "compare.process.stage.VALIDATING_COMPATIBILITY" },
  { key: "EXTRACTING_FINANCIAL_DATA", labelKey: "compare.process.stage.EXTRACTING_FINANCIAL_DATA" },
  { key: "RESOLVING_CONFLICTS", labelKey: "compare.process.stage.RESOLVING_CONFLICTS" },
  { key: "COMPUTING_CALCULATIONS", labelKey: "compare.process.stage.COMPUTING_CALCULATIONS" },
  { key: "SYNTHESIZING_REPORT", labelKey: "compare.process.stage.SYNTHESIZING_REPORT" },
  { key: "COMPLETED", labelKey: "compare.process.stage.COMPLETED" },
];

export function ProcessingView({
  status,
  onCancel,
  isCancelling,
  language,
}: ProcessingViewProps) {
  const t = (key: string) => getTranslation(key, language);

  const currentStage = status?.current_stage || "INITIALIZED";
  const completedStages = new Set(status?.completed_stages || []);

  const currentIndex = STAGES.findIndex((s) => s.key === currentStage);
  const progressPercent = Math.min(100, Math.max(10, ((currentIndex + 1) / STAGES.length) * 100));

  return (
    <div className="max-w-2xl mx-auto py-16 px-4 text-center space-y-8 animate-fade-in font-sans">
      <div className="space-y-3">
        <div className="w-16 h-16 rounded-2xl bg-primary-50 text-primary-900 border border-primary-200 flex items-center justify-center mx-auto shadow-sm">
          <Loader2 className="w-8 h-8 animate-spin text-primary-900" />
        </div>
        <h2 className="text-2xl font-extrabold text-neutral-900 font-heading">
          {t("compare.process.title")}
        </h2>
        <p className="text-sm font-medium text-neutral-600 max-w-md mx-auto">
          {status?.stage_message || t("compare.process.stage.IDENTIFYING_METADATA")}
        </p>
      </div>

      {/* Progress Bar */}
      <div className="w-full bg-neutral-200 h-2.5 rounded-full overflow-hidden">
        <div
          className="bg-primary-900 h-2.5 rounded-full transition-all duration-500 ease-out"
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      {/* Stage List */}
      <div className="bg-white border border-neutral-200 rounded-xl p-6 shadow-sm text-left space-y-3">
        {STAGES.filter((s) => s.key !== "INITIALIZED").map((s, idx) => {
          const isDone = completedStages.has(s.key) || currentIndex > idx + 1;
          const isCurrent = currentStage === s.key;

          return (
            <div key={s.key} className="flex items-center justify-between text-xs py-1">
              <span
                className={`flex items-center gap-2.5 font-semibold ${
                  isDone
                    ? "text-success-700"
                    : isCurrent
                    ? "text-primary-900 font-bold"
                    : "text-neutral-400"
                }`}
              >
                {isDone ? (
                  <CheckCircle2 className="w-4 h-4 text-success-600 shrink-0" />
                ) : isCurrent ? (
                  <Loader2 className="w-4 h-4 text-primary-900 animate-spin shrink-0" />
                ) : (
                  <span className="w-4 h-4 rounded-full border border-neutral-300 inline-block shrink-0" />
                )}
                {t(s.labelKey)}
              </span>

              <span className="text-[11px] font-mono text-neutral-400">
                {isDone ? t("compare.processing.status_done") : isCurrent ? t("compare.processing.status_in_progress") : t("compare.processing.status_pending")}
              </span>
            </div>
          );
        })}
      </div>

      {/* Cancel Button */}
      <div className="pt-2">
        <Button
          variant="outline"
          size="sm"
          onClick={onCancel}
          disabled={isCancelling}
          className="text-xs text-error-700 hover:bg-error-50 border-error-200 font-bold"
        >
          <StopCircle className="w-4 h-4 mr-1.5" />
          {isCancelling ? t("compare.processing.cancelling") : t("compare.process.cancel_btn")}
        </Button>
      </div>
    </div>
  );
}
