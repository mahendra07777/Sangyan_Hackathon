import { CheckCircle2, AlertTriangle, XCircle, ArrowRight, ArrowLeft, Info } from "lucide-react";
import { Button } from "../ui/Button";
import type { CompatibilityReport, CompatibilityStatus } from "../../lib/compareApi";
import { getTranslation, type SupportedLanguage } from "../../lib/translations";

interface CompatibilityViewProps {
  report: CompatibilityReport;
  onProceed: () => void;
  onBackToMetadata: () => void;
  language: SupportedLanguage;
}

export function CompatibilityView({
  report,
  onProceed,
  onBackToMetadata,
  language,
}: CompatibilityViewProps) {
  const t = (key: string) => getTranslation(key, language);

  const getStatusBadge = (status: CompatibilityStatus) => {
    switch (status) {
      case "COMPATIBLE":
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-success-50 text-success-700 border border-success-200">
            <CheckCircle2 className="w-4 h-4" />
            {t("compare.compat.status.COMPATIBLE")}
          </span>
        );
      case "COMPATIBLE_WITH_WARNINGS":
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-warning-50 text-warning-800 border border-warning-200">
            <AlertTriangle className="w-4 h-4 text-warning-600" />
            {t("compare.compat.status.COMPATIBLE_WITH_WARNINGS")}
          </span>
        );
      case "PARTIALLY_COMPATIBLE":
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-50 text-amber-800 border border-amber-200">
            <Info className="w-4 h-4 text-amber-600" />
            {t("compare.compat.status.PARTIALLY_COMPATIBLE")}
          </span>
        );
      case "BLOCKED":
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-error-50 text-error-700 border border-error-200">
            <XCircle className="w-4 h-4" />
            {t("compare.compat.status.BLOCKED")}
          </span>
        );
    }
  };

  const blockers = report.findings.filter((f) => f.severity === "BLOCKER");
  const warnings = report.findings.filter((f) => f.severity === "WARNING");

  const canProceed = report.is_comparable && report.overall_status !== "BLOCKED";

  return (
    <div className="max-w-4xl mx-auto py-8 px-4 sm:px-6 space-y-8 animate-fade-in font-sans">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-neutral-200 pb-5">
        <div>
          <span className="text-xs font-bold text-accent-700 uppercase tracking-widest">
            {t("compare.compat.title")}
          </span>
          <h2 className="text-2xl font-extrabold text-neutral-900 mt-1 font-heading">
            {t("compare.compat.title")}
          </h2>
          <p className="text-xs sm:text-sm text-neutral-600 mt-1">
            {t("compare.compat.sub")}
          </p>
        </div>

        <div>{getStatusBadge(report.overall_status)}</div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
          <p className="text-[11px] font-bold text-neutral-500 uppercase tracking-wider">{t("compare.compat.summary_status")}</p>
          <p className="text-base font-extrabold text-neutral-900 mt-1">{report.overall_status.replace(/_/g, " ")}</p>
        </div>
        <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
          <p className="text-[11px] font-bold text-neutral-500 uppercase tracking-wider">{t("compare.compat.summary_blockers")}</p>
          <p className={`text-base font-extrabold mt-1 ${report.blocker_count > 0 ? "text-error-600" : "text-neutral-900"}`}>
            {report.blocker_count}
          </p>
        </div>
        <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
          <p className="text-[11px] font-bold text-neutral-500 uppercase tracking-wider">{t("compare.compat.summary_warnings")}</p>
          <p className={`text-base font-extrabold mt-1 ${report.warning_count > 0 ? "text-warning-600" : "text-neutral-900"}`}>
            {report.warning_count}
          </p>
        </div>
      </div>

      {/* Blockers Section */}
      {blockers.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-xs font-bold text-error-700 uppercase tracking-wider flex items-center gap-1.5">
            <XCircle className="w-4 h-4" />
            {t("compare.compat.blockers")}
          </h3>

          <div className="space-y-3">
            {blockers.map((b) => (
              <div
                key={b.finding_id}
                className="bg-error-50 border border-error-200 rounded-xl p-4 text-xs space-y-2 text-error-900"
              >
                <div className="flex items-center justify-between">
                  <span className="font-extrabold font-mono text-[11px] bg-error-100 text-error-800 px-2 py-0.5 rounded">
                    {b.code}
                  </span>
                  <span className="font-medium text-neutral-600">
                    {t("compare.compat.affects_prefix")} {b.affected_document_ids.map((id) => id.toUpperCase()).join(", ")}
                  </span>
                </div>
                <p className="font-bold text-sm text-error-900">{b.title}</p>
                <p className="text-neutral-700">{b.description}</p>
                {b.remediation_hint && (
                  <div className="pt-2 border-t border-error-200/60 text-[11px]">
                    <span className="font-bold text-error-800">{t("compare.compat.remediation")} </span>
                    <span className="text-neutral-700">{b.remediation_hint}</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Warnings Section */}
      {warnings.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-xs font-bold text-warning-800 uppercase tracking-wider flex items-center gap-1.5">
            <AlertTriangle className="w-4 h-4 text-warning-600" />
            {t("compare.compat.warnings")}
          </h3>

          <div className="space-y-3">
            {warnings.map((w) => (
              <div
                key={w.finding_id}
                className="bg-warning-50/70 border border-warning-200 rounded-xl p-4 text-xs space-y-2 text-neutral-900"
              >
                <div className="flex items-center justify-between">
                  <span className="font-extrabold font-mono text-[11px] bg-warning-100 text-warning-900 px-2 py-0.5 rounded">
                    {w.code}
                  </span>
                  <span className="font-medium text-neutral-500">
                    {t("compare.compat.affects_prefix")} {w.affected_document_ids.map((id) => id.toUpperCase()).join(", ")}
                  </span>
                </div>
                <p className="font-bold text-sm text-neutral-900">{w.title}</p>
                <p className="text-neutral-700">{w.description}</p>
                {w.remediation_hint && (
                  <div className="pt-2 border-t border-warning-200/60 text-[11px]">
                    <span className="font-bold text-warning-900">{t("compare.compat.remediation")} </span>
                    <span className="text-neutral-700">{w.remediation_hint}</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* All Compatible State */}
      {report.findings.length === 0 && (
        <div className="bg-success-50 border border-success-200 rounded-xl p-6 text-center space-y-2">
          <CheckCircle2 className="w-8 h-8 text-success-600 mx-auto" />
          <p className="text-sm font-bold text-success-900">{t("compare.compat.zero_issues_title")}</p>
          <p className="text-xs text-neutral-600">
            {t("compare.compat.zero_issues_desc")}
          </p>
        </div>
      )}

      {/* Bottom Actions */}
      <div className="flex items-center justify-between pt-4 border-t border-neutral-200">
        <Button variant="ghost" size="sm" onClick={onBackToMetadata} className="text-xs font-semibold">
          <ArrowLeft className="w-4 h-4 mr-1.5" />
          {t("compare.compat.back_metadata_btn")}
        </Button>

        {canProceed ? (
          <Button size="md" onClick={onProceed} className="font-bold text-xs bg-primary-900 text-white px-6">
            {t("compare.compat.proceed_btn")}
            <ArrowRight className="w-4 h-4 ml-2" />
          </Button>
        ) : (
          <div className="text-right space-y-1">
            <Button size="md" disabled className="font-bold text-xs bg-neutral-300 text-neutral-500 cursor-not-allowed">
              {t("compare.compat.blocked_btn")}
            </Button>
            <p className="text-[11px] text-error-600 font-medium">
              {t("compare.compat.blocked_guidance")}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
