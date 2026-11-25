import { useState } from "react";
import { ArrowRight, Save, Building2, Calendar, Check } from "lucide-react";
import { Button } from "../ui/Button";
import { Badge } from "../ui/Badge";
import type { ComparisonDocument, DocumentMetadata, MetadataUpdateRequest } from "../../lib/compareApi";
import { getTranslation, type SupportedLanguage } from "../../lib/translations";

interface MetadataReviewProps {
  documents: ComparisonDocument[];
  metadata: Record<string, DocumentMetadata>;
  onUpdateMetadata: (docId: string, updates: MetadataUpdateRequest) => Promise<void>;
  onProceed: () => void;
  onBack: () => void;
  language: SupportedLanguage;
}

export function MetadataReview({
  documents,
  metadata,
  onUpdateMetadata,
  onProceed,
  onBack,
  language,
}: MetadataReviewProps) {
  const [formData, setFormData] = useState<Record<string, MetadataUpdateRequest>>(() => {
    const initial: Record<string, MetadataUpdateRequest> = {};
    for (const doc of documents) {
      const m = metadata[doc.doc_id];
      if (m) {
        initial[doc.doc_id] = {
          company_name: m.company_name,
          company_identifier: m.company_identifier || "",
          industry: m.industry,
          document_type: m.document_type,
          financial_year: m.financial_year,
          reporting_period: m.reporting_period,
          quarter: m.quarter || "",
          currency: m.currency,
          reporting_scale: m.reporting_scale,
          reporting_scope: m.reporting_scope as any,
          audit_status: m.audit_status as any,
        };
      }
    }
    return initial;
  });

  const [savingDocId, setSavingDocId] = useState<string | null>(null);
  const [savedSuccess, setSavedSuccess] = useState<Record<string, boolean>>({});

  const t = (key: string) => getTranslation(key, language);

  const handleFieldChange = (docId: string, field: keyof MetadataUpdateRequest, value: any) => {
    setFormData((prev) => ({
      ...prev,
      [docId]: {
        ...prev[docId],
        [field]: value,
      },
    }));
    setSavedSuccess((prev) => ({ ...prev, [docId]: false }));
  };

  const handleSaveDoc = async (docId: string) => {
    const updates = formData[docId];
    if (!updates) return;
    setSavingDocId(docId);
    try {
      await onUpdateMetadata(docId, updates);
      setSavedSuccess((prev) => ({ ...prev, [docId]: true }));
      setTimeout(() => {
        setSavedSuccess((prev) => ({ ...prev, [docId]: false }));
      }, 3000);
    } finally {
      setSavingDocId(null);
    }
  };

  return (
    <div className="max-w-5xl mx-auto py-8 px-4 sm:px-6 space-y-8 animate-fade-in font-sans">
      {/* Step Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-neutral-200 pb-5">
        <div>
          <span className="text-xs font-bold text-accent-700 uppercase tracking-widest">
            {t("compare.metadata.title")}
          </span>
          <h2 className="text-2xl font-extrabold text-neutral-900 mt-1 font-heading">
            {t("compare.metadata.subtitle")}
          </h2>
          <p className="text-xs sm:text-sm text-neutral-600 mt-1">
            {t("compare.metadata.sub")}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={onBack} className="text-xs font-semibold">
            {t("compare.metadata.reupload_btn")}
          </Button>
          <Button size="sm" onClick={onProceed} className="text-xs font-bold bg-primary-900 text-white">
            {t("compare.metadata.proceed_btn")}
          </Button>
        </div>
      </div>

      {/* Metadata Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {documents.map((doc) => {
          const docId = doc.doc_id;
          const meta = metadata[docId];
          const form = formData[docId] || {};
          const isSaving = savingDocId === docId;
          const isSaved = savedSuccess[docId];

          return (
            <div
              key={docId}
              className="bg-white border border-neutral-200 rounded-xl p-6 shadow-sm space-y-5 flex flex-col justify-between"
            >
              {/* Card Header */}
              <div className="flex items-center justify-between border-b border-neutral-100 pb-3">
                <div className="flex items-center gap-2">
                  <span className="w-7 h-7 rounded-md bg-neutral-900 text-white font-extrabold text-xs flex items-center justify-center">
                    {doc.slot.toUpperCase().replace("DOC_", "")}
                  </span>
                  <div>
                    <h3 className="text-sm font-bold text-neutral-900 truncate max-w-[220px]" title={doc.original_filename}>
                      {doc.original_filename}
                    </h3>
                    <p className="text-[10px] text-neutral-500 uppercase tracking-wider">
                      {doc.file_format} · {(doc.file_size_bytes / (1024 * 1024)).toFixed(2)} MiB
                    </p>
                  </div>
                </div>

                {meta?.confidence_category && (
                  <Badge
                    variant={
                      meta.confidence_category === "HIGH"
                        ? "success"
                        : meta.confidence_category === "MEDIUM"
                        ? "warning"
                        : "default"
                    }
                    className="text-[10px]"
                  >
                    {meta.confidence_category} {t("compare.metadata.confidence_suffix")}
                  </Badge>
                )}
              </div>

              {/* Form Fields */}
              <div className="space-y-4 text-xs">
                {/* Company Name */}
                <div className="space-y-1">
                  <label className="font-bold text-neutral-700 flex items-center justify-between">
                    <span className="flex items-center gap-1.5">
                      <Building2 className="w-3.5 h-3.5 text-neutral-400" />
                      {t("compare.metadata.company")}
                    </span>
                    {(!form.company_name || form.company_name.trim().toLowerCase() === "unknown") && (
                      <span className="text-[10px] font-normal text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200">
                        {t("compare.metadata.not_detected") || "Not detected"}
                      </span>
                    )}
                  </label>
                  <input
                    type="text"
                    placeholder={t("compare.metadata.company_placeholder") || "e.g. Tata Motors Limited (or enter name)"}
                    value={(!form.company_name || form.company_name.trim().toLowerCase() === "unknown") ? "" : form.company_name}
                    onChange={(e) => handleFieldChange(docId, "company_name", e.target.value)}
                    className="w-full px-3 py-1.5 border border-neutral-300 rounded-md focus:ring-1 focus:ring-accent-500 text-neutral-900 font-semibold"
                  />
                </div>

                {/* CIN / Identifier & Industry */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="font-semibold text-neutral-600">{t("compare.metadata.cin")}</label>
                    <input
                      type="text"
                      placeholder={t("compare.metadata.cin_placeholder")}
                      value={form.company_identifier || ""}
                      onChange={(e) => handleFieldChange(docId, "company_identifier", e.target.value)}
                      className="w-full px-2.5 py-1.5 border border-neutral-300 rounded-md focus:ring-1 focus:ring-accent-500 font-mono text-[11px]"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="font-semibold text-neutral-600 flex items-center justify-between">
                      <span>{t("compare.metadata.industry")}</span>
                      {(!form.industry || form.industry.trim().toUpperCase() === "UNKNOWN") && (
                        <span className="text-[10px] font-normal text-neutral-400">
                          {t("compare.metadata.optional") || "Optional"}
                        </span>
                      )}
                    </label>
                    <input
                      type="text"
                      placeholder={t("compare.metadata.industry_placeholder") || "e.g. Automobiles, IT, Banking"}
                      value={(!form.industry || form.industry.trim().toUpperCase() === "UNKNOWN") ? "" : form.industry}
                      onChange={(e) => handleFieldChange(docId, "industry", e.target.value)}
                      className="w-full px-2.5 py-1.5 border border-neutral-300 rounded-md focus:ring-1 focus:ring-accent-500"
                    />
                  </div>
                </div>

                {/* Document Type & Financial Year */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="font-semibold text-neutral-600">{t("compare.metadata.doc_type")}</label>
                    <input
                      type="text"
                      placeholder={t("compare.metadata.doc_type_placeholder")}
                      value={(!form.document_type || form.document_type.trim().toLowerCase() === "unknown") ? "" : form.document_type}
                      onChange={(e) => handleFieldChange(docId, "document_type", e.target.value)}
                      className="w-full px-2.5 py-1.5 border border-neutral-300 rounded-md focus:ring-1 focus:ring-accent-500"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="font-semibold text-neutral-600 flex items-center justify-between">
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3.5 h-3.5 text-neutral-400" />
                        {t("compare.metadata.fy")}
                      </span>
                      {(!form.financial_year || form.financial_year.trim().toLowerCase() === "unknown") && (
                        <span className="text-[10px] font-normal text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200">
                          {t("compare.metadata.not_detected") || "Not detected"}
                        </span>
                      )}
                    </label>
                    <input
                      type="text"
                      placeholder={t("compare.metadata.fy_placeholder")}
                      value={(!form.financial_year || form.financial_year.trim().toLowerCase() === "unknown") ? "" : form.financial_year}
                      onChange={(e) => handleFieldChange(docId, "financial_year", e.target.value)}
                      className="w-full px-2.5 py-1.5 border border-neutral-300 rounded-md focus:ring-1 focus:ring-accent-500 font-bold"
                    />
                  </div>
                </div>

                {/* Reporting Period & Quarter */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="font-semibold text-neutral-600">{t("compare.metadata.period")}</label>
                    <select
                      value={form.reporting_period || "Unknown"}
                      onChange={(e) => handleFieldChange(docId, "reporting_period", e.target.value)}
                      className="w-full px-2.5 py-1.5 border border-neutral-300 rounded-md focus:ring-1 focus:ring-accent-500 bg-white"
                    >
                      <option value="Annual">{t("compare.metadata.period.annual")}</option>
                      <option value="Quarterly">{t("compare.metadata.period.quarterly")}</option>
                      <option value="Half-Yearly">{t("compare.metadata.period.half_yearly")}</option>
                      <option value="Nine-Month">{t("compare.metadata.period.nine_month")}</option>
                      <option value="Monthly">{t("compare.metadata.period.monthly")}</option>
                      <option value="Other">{t("compare.metadata.period.other")}</option>
                      <option value="Unknown">{t("compare.metadata.period.unknown")}</option>
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="font-semibold text-neutral-600">{t("compare.metadata.quarter")}</label>
                    <select
                      value={form.quarter || ""}
                      onChange={(e) => handleFieldChange(docId, "quarter", e.target.value || undefined)}
                      className="w-full px-2.5 py-1.5 border border-neutral-300 rounded-md focus:ring-1 focus:ring-accent-500 bg-white"
                    >
                      <option value="">{t("compare.metadata.quarter.none")}</option>
                      <option value="Q1">Q1</option>
                      <option value="Q2">Q2</option>
                      <option value="Q3">Q3</option>
                      <option value="Q4">Q4</option>
                    </select>
                  </div>
                </div>

                {/* Scope & Audit Status */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="font-semibold text-neutral-600">{t("compare.metadata.scope")}</label>
                    <select
                      value={form.reporting_scope || "CONSOLIDATED"}
                      onChange={(e) => handleFieldChange(docId, "reporting_scope", e.target.value as any)}
                      className="w-full px-2.5 py-1.5 border border-neutral-300 rounded-md focus:ring-1 focus:ring-accent-500 bg-white"
                    >
                      <option value="CONSOLIDATED">{t("compare.metadata.scope.CONSOLIDATED")}</option>
                      <option value="STANDALONE">{t("compare.metadata.scope.STANDALONE")}</option>
                      <option value="BOTH">{t("compare.metadata.scope.BOTH")}</option>
                      <option value="UNKNOWN">{t("compare.metadata.scope.UNKNOWN")}</option>
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="font-semibold text-neutral-600">{t("compare.metadata.audit")}</label>
                    <select
                      value={form.audit_status || "AUDITED"}
                      onChange={(e) => handleFieldChange(docId, "audit_status", e.target.value as any)}
                      className="w-full px-2.5 py-1.5 border border-neutral-300 rounded-md focus:ring-1 focus:ring-accent-500 bg-white"
                    >
                      <option value="AUDITED">{t("compare.metadata.audit.AUDITED")}</option>
                      <option value="UNAUDITED">{t("compare.metadata.audit.UNAUDITED")}</option>
                      <option value="LIMITED_REVIEW">{t("compare.metadata.audit.LIMITED_REVIEW")}</option>
                      <option value="PROVISIONAL">{t("compare.metadata.audit.PROVISIONAL")}</option>
                      <option value="UNKNOWN">{t("compare.metadata.audit.UNKNOWN")}</option>
                    </select>
                  </div>
                </div>

                {/* Currency & Scale */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="font-semibold text-neutral-600">{t("compare.metadata.currency")}</label>
                    <input
                      type="text"
                      value={form.currency || "INR"}
                      onChange={(e) => handleFieldChange(docId, "currency", e.target.value)}
                      className="w-full px-2.5 py-1.5 border border-neutral-300 rounded-md focus:ring-1 focus:ring-accent-500"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="font-semibold text-neutral-600">{t("compare.metadata.scale")}</label>
                    <select
                      value={form.reporting_scale || "CRORE"}
                      onChange={(e) => handleFieldChange(docId, "reporting_scale", e.target.value)}
                      className="w-full px-2.5 py-1.5 border border-neutral-300 rounded-md focus:ring-1 focus:ring-accent-500 bg-white"
                    >
                      <option value="CRORE">{t("compare.metadata.scale.CRORE")}</option>
                      <option value="LAKH">{t("compare.metadata.scale.LAKH")}</option>
                      <option value="THOUSAND">{t("compare.metadata.scale.THOUSAND")}</option>
                      <option value="MILLION">{t("compare.metadata.scale.MILLION")}</option>
                      <option value="UNITS">{t("compare.metadata.scale.UNITS")}</option>
                      <option value="UNKNOWN">{t("compare.metadata.scale.UNKNOWN")}</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Card Footer: Save Button */}
              <div className="pt-2 border-t border-neutral-100 flex items-center justify-between">
                {isSaved ? (
                  <span className="text-[11px] font-bold text-success-600 flex items-center gap-1">
                    <Check className="w-3.5 h-3.5" /> {t("compare.metadata.corrections_saved")}
                  </span>
                ) : (
                  <span className="text-[10px] text-neutral-400">
                    {meta?.is_user_overridden ? t("compare.metadata.status_overridden") : t("compare.metadata.status_detected")}
                  </span>
                )}

                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleSaveDoc(docId)}
                  disabled={isSaving}
                  className="text-xs font-bold"
                >
                  <Save className="w-3.5 h-3.5 mr-1.5" />
                  {isSaving ? t("compare.metadata.saving") : t("compare.metadata.save_edit")}
                </Button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Bottom Action Bar */}
      <div className="flex items-center justify-between pt-4 border-t border-neutral-200">
        <Button variant="ghost" size="sm" onClick={onBack} className="text-xs">
          {t("compare.metadata.back_upload_btn")}
        </Button>
        <Button size="md" onClick={onProceed} className="font-bold text-xs bg-primary-900 text-white px-6">
          {t("compare.metadata.proceed_btn")}
          <ArrowRight className="w-4 h-4 ml-2" />
        </Button>
      </div>
    </div>
  );
}
