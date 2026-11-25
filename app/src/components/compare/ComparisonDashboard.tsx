import { useState, useEffect } from "react";
import {
  ShieldCheck,
  Sparkles,
  AlertTriangle,
  ArrowLeft,
  FileText,
  Table,
  BarChart3,
  AlertCircle,
  MessageSquare,
  TrendingUp,
  TrendingDown,
  Minus,
  HelpCircle,
  Send,
  Loader2,
  Info,
  FileDown,
  FileSpreadsheet,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Layers,
  Pencil,
  RotateCcw,
  Edit3,
} from "lucide-react";
import { Button } from "../ui/Button";
import { Badge } from "../ui/Badge";
import { CompareSvgCharts } from "./CompareSvgCharts";
import { EvidenceViewer, type CandidateInfo } from "./EvidenceViewer";
import type {
  ComparisonResult,
  EvidenceReference,
  ComparisonChatMessage,
  FinancialValue,
  CalculationResult,
  CompatibilityFinding,
} from "../../lib/compareApi";
import {
  sendCompareChat,
  exportComparePdf,
  exportCompareXlsx,
  downloadBlob,
  correctFinancialValue,
  undoFinancialCorrection,
} from "../../lib/compareApi";
import { getTranslation, type SupportedLanguage } from "../../lib/translations";

interface ComparisonDashboardProps {
  result: ComparisonResult;
  sessionToken: string;
  onNewComparison: () => void;
  language: SupportedLanguage;
}

type DashboardTab = "summary" | "matrix" | "charts" | "risks" | "chat";

const METRIC_ROWS = [
  { key: "REVENUE", labelKey: "compare.metric.revenue" },
  { key: "PAT", labelKey: "compare.metric.pat" },
  { key: "EBITDA", labelKey: "compare.metric.ebitda" },
  { key: "TOTAL_ASSETS", labelKey: "compare.metric.assets" },
  { key: "TOTAL_LIABILITIES", labelKey: "compare.metric.liabilities" },
  { key: "TOTAL_DEBT", labelKey: "compare.metric.debt" },
  { key: "CASH_EQUIVALENTS", labelKey: "compare.metric.cash" },
  { key: "EPS", labelKey: "compare.metric.eps" },
  { key: "OPERATING_CASH_FLOW", labelKey: "compare.metric.ocf" },
];

const CORE_METRIC_KEYS = new Set([
  "REVENUE",
  "revenue",
  "PAT",
  "pat",
  "EBITDA",
  "ebitda",
  "TOTAL_ASSETS",
  "total_assets",
  "TOTAL_LIABILITIES",
  "total_liabilities",
  "TOTAL_DEBT",
  "total_debt",
  "CASH_EQUIVALENTS",
  "cash_equivalents",
  "EPS",
  "eps",
  "basic_eps",
  "BASIC_EPS",
  "OPERATING_CASH_FLOW",
  "operating_cash_flow",
]);

export function ComparisonDashboard({
  result,
  sessionToken,
  onNewComparison,
  language,
}: ComparisonDashboardProps) {
  const [activeResult, setActiveResult] = useState<ComparisonResult>(result);

  useEffect(() => {
    setActiveResult(result);
  }, [result]);

  const docs = activeResult.documents;
  const docA = docs[0];
  const docB = docs[1];

  const [activeTab, setActiveTab] = useState<DashboardTab>("matrix");
  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceReference | null>(null);
  const [selectedCandidates, setSelectedCandidates] = useState<CandidateInfo[]>([]);

  // Multi-document baseline and comparison selection
  const [baselineDocId, setBaselineDocId] = useState<string>(docs[0]?.doc_id || "");
  const [comparisonDocId, setComparisonDocId] = useState<string>(docs[1]?.doc_id || "");

  // Compatibility and additional metrics expand/collapse state
  const [compatBannerExpanded, setCompatBannerExpanded] = useState<boolean>(false);
  const [additionalMetricsExpanded, setAdditionalMetricsExpanded] = useState<boolean>(true);

  // Manual Financial Corrections State
  const [editingMetric, setEditingMetric] = useState<{
    docId: string;
    metricKey: string;
    currentVal?: FinancialValue | null;
  } | null>(null);
  const [correctedAmountInput, setCorrectedAmountInput] = useState<string>("");
  const [correctionReasonInput, setCorrectionReasonInput] = useState<string>("");
  const [isSubmittingCorrection, setIsSubmittingCorrection] = useState<boolean>(false);
  const [isUndoingCorrection, setIsUndoingCorrection] = useState<boolean>(false);
  const [correctionError, setCorrectionError] = useState<string | null>(null);
  const [correctionSuccess, setCorrectionSuccess] = useState<string | null>(null);

  // Active corrections count
  const activeCorrectionsCount = Object.values(activeResult.financial_values || {}).reduce(
    (acc, docMap) => acc + Object.values(docMap || {}).filter((v) => v?.is_user_corrected).length,
    0
  );

  // Chat State
  const [chatMessages, setChatMessages] = useState<ComparisonChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [isSendingChat, setIsSendingChat] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);

  // Export State
  const [isExportingPdf, setIsExportingPdf] = useState(false);
  const [isExportingXlsx, setIsExportingXlsx] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exportSuccess, setExportSuccess] = useState<string | null>(null);

  const t = (key: string) => getTranslation(key, language);

  const handleOpenValueEvidence = (val?: FinancialValue | null) => {
    if (!val?.evidence) return;
    const cands: CandidateInfo[] = [];
    if (val.conflict_info && val.conflict_info.all_candidates) {
      for (const c of val.conflict_info.all_candidates) {
        cands.push({
          candidate_id: c.candidate_id,
          raw_label: c.raw_label,
          raw_text_value: c.raw_text_value,
          normalized_amount: c.normalized_amount ? Number(c.normalized_amount) : null,
          statement_type: c.statement_type,
          is_selected: c.candidate_id === val.selected_candidate_id,
          resolution_reason: val.conflict_info.resolution_reason,
          evidence: c.evidence,
        });
      }
    }
    setSelectedCandidates(cands);
    setSelectedEvidence(val.evidence);
  };

  const handleOpenEditModal = (docId: string, metricKey: string, currentVal?: FinancialValue | null) => {
    setEditingMetric({ docId, metricKey, currentVal });
    setCorrectedAmountInput(
      currentVal?.amount !== null && currentVal?.amount !== undefined
        ? String(currentVal.amount)
        : ""
    );
    setCorrectionReasonInput(currentVal?.correction_reason || "");
    setCorrectionError(null);
    setCorrectionSuccess(null);
  };

  const handleApplyCorrection = async () => {
    if (!editingMetric || isSubmittingCorrection) return;
    const trimmed = correctedAmountInput.trim();
    if (!trimmed || isNaN(Number(trimmed))) {
      setCorrectionError(t("compare.correction.invalid_amount"));
      return;
    }

    const numVal = Number(trimmed);
    if (!isFinite(numVal)) {
      setCorrectionError(t("compare.correction.invalid_amount"));
      return;
    }

    // Total assets cannot be negative
    if (editingMetric.metricKey.toUpperCase() === "TOTAL_ASSETS" && numVal < 0) {
      setCorrectionError(t("compare.correction.assets_negative"));
      return;
    }

    setIsSubmittingCorrection(true);
    setCorrectionError(null);
    try {
      const resp = await correctFinancialValue(
        activeResult.session_id,
        sessionToken,
        editingMetric.docId,
        editingMetric.metricKey,
        numVal,
        correctionReasonInput.trim() || undefined
      );
      setActiveResult(resp.comparison_result);
      setEditingMetric(null);
      setCorrectedAmountInput("");
      setCorrectionReasonInput("");
      setCorrectionSuccess(t("compare.correction.success"));
      setTimeout(() => setCorrectionSuccess(null), 4000);
    } catch (err: any) {
      setCorrectionError(err.message || "Failed to apply correction.");
    } finally {
      setIsSubmittingCorrection(false);
    }
  };

  const handleUndoCorrection = async () => {
    if (isUndoingCorrection) return;
    setIsUndoingCorrection(true);
    setCorrectionError(null);
    try {
      const resp = await undoFinancialCorrection(activeResult.session_id, sessionToken);
      setActiveResult(resp.comparison_result);
      setCorrectionSuccess(t("compare.correction.undo_success"));
      setTimeout(() => setCorrectionSuccess(null), 4000);
    } catch (err: any) {
      setCorrectionError(err.message || t("compare.correction.no_corrections"));
    } finally {
      setIsUndoingCorrection(false);
    }
  };

  const handleExportPdf = async () => {
    if (isExportingPdf || isExportingXlsx) return;
    setIsExportingPdf(true);
    setExportError(null);
    setExportSuccess(null);
    try {
      const blob = await exportComparePdf(activeResult.session_id, sessionToken);
      const filename = `BharatInvestorCopilot_Comparison_${activeResult.session_id.slice(0, 8)}.pdf`;
      downloadBlob(blob, filename);
      setExportSuccess(t("compare.export.download_success"));
      setTimeout(() => setExportSuccess(null), 4000);
    } catch (err: any) {
      setExportError(err.message || t("compare.export.error_failed"));
    } finally {
      setIsExportingPdf(false);
    }
  };

  const handleExportXlsx = async () => {
    if (isExportingPdf || isExportingXlsx) return;
    setIsExportingXlsx(true);
    setExportError(null);
    setExportSuccess(null);
    try {
      const blob = await exportCompareXlsx(activeResult.session_id, sessionToken);
      const filename = `BharatInvestorCopilot_Comparison_${activeResult.session_id.slice(0, 8)}.xlsx`;
      downloadBlob(blob, filename);
      setExportSuccess(t("compare.export.download_success"));
      setTimeout(() => setExportSuccess(null), 4000);
    } catch (err: any) {
      setExportError(err.message || t("compare.export.error_failed"));
    } finally {
      setIsExportingXlsx(false);
    }
  };

  const getDocVal = (docId: string, metricKey: string): FinancialValue | undefined => {
    return (
      activeResult.financial_values[metricKey]?.[docId] ||
      activeResult.financial_values[metricKey.toLowerCase()]?.[docId] ||
      activeResult.financial_values[metricKey.toUpperCase()]?.[docId]
    );
  };

  // Helper to get pairwise variance between selected baseline and comparison documents
  const getPairwiseVariance = (metricKey: string, baseId: string, compId: string): CalculationResult | undefined => {
    const keyLower = metricKey.toLowerCase();
    const keyUpper = metricKey.toUpperCase();
    const direct = activeResult.variances.find(
      (v) =>
        (v.metric_key === metricKey || v.metric_key === keyLower || v.metric_key === keyUpper) &&
        v.base_doc_id === baseId &&
        v.comparison_doc_id === compId
    );
    if (direct) return direct;

    const reverse = activeResult.variances.find(
      (v) =>
        (v.metric_key === metricKey || v.metric_key === keyLower || v.metric_key === keyUpper) &&
        v.base_doc_id === compId &&
        v.comparison_doc_id === baseId
    );
    if (reverse && reverse.absolute_variance !== null && reverse.absolute_variance !== undefined) {
      const valBase = reverse.comparison_value !== null && reverse.comparison_value !== undefined ? Number(reverse.comparison_value) : null;
      const valComp = reverse.base_value !== null && reverse.base_value !== undefined ? Number(reverse.base_value) : null;
      const invAbs = -reverse.absolute_variance;

      let invPct: number | null = null;
      let dispPct: string | null = null;
      let status: any = reverse.status;
      let dirExpl = invAbs > 0 ? t("compare.trend.increase") : invAbs < 0 ? t("compare.trend.decrease") : t("compare.trend.flat");

      if (valBase !== null && valComp !== null) {
        if (valBase === 0) {
          invPct = null;
          dispPct = "N/A (Base Zero)";
          status = "DIV_BY_ZERO";
          dirExpl = valComp === 0 ? "Zero in both periods (no change)." : "Base value was zero; expanded (percentage undefined).";
        } else if (valBase < 0) {
          invPct = null;
          dispPct = "N/A (Loss Base)";
          status = "NON_POSITIVE_BASE";
          if (valComp > 0) {
            dirExpl = "Turnaround: shifted from net loss to net profit.";
          } else if (valComp < 0) {
            dirExpl = valComp > valBase ? "Loss reduction: net loss narrowed." : "Loss expansion: net loss widened.";
          } else {
            dirExpl = "Loss eliminated: shifted from net loss to break-even.";
          }
        } else if (valBase > 0 && valComp < 0) {
          invPct = null;
          dispPct = "N/A (Downturn to Loss)";
          status = "NON_POSITIVE_BASE";
          dirExpl = "Downturn: shifted from net profit to net loss.";
        } else if (valBase > 0 && valComp >= 0) {
          // Recalculate using actual reversed base value as denominator (never simply negate)
          invPct = ((valComp - valBase) / valBase) * 100;
          dispPct = invPct > 0 ? `+${invPct.toFixed(2)}%` : `${invPct.toFixed(2)}%`;
          status = "CALCULATED";
        }
      }

      // Append perimeter/duration context warnings if applicable
      const baseMetaRev = activeResult.metadata[baseId];
      const compMetaRev = activeResult.metadata[compId];
      const revWarnings: string[] = [];
      if (baseMetaRev && compMetaRev) {
        const bScope = (baseMetaRev.reporting_scope || "").toUpperCase();
        const cScope = (compMetaRev.reporting_scope || "").toUpperCase();
        if (bScope && cScope && bScope !== "UNKNOWN" && cScope !== "UNKNOWN" && bScope !== "BOTH" && cScope !== "BOTH" && bScope !== cScope) {
          revWarnings.push(`Scope discrepancy: Compares ${bScope} vs ${cScope} perimeters.`);
        }
        const bPeriod = (baseMetaRev.reporting_period || "").toLowerCase();
        const cPeriod = (compMetaRev.reporting_period || "").toLowerCase();
        if (bPeriod && cPeriod && bPeriod !== "unknown" && cPeriod !== "unknown" && bPeriod !== cPeriod) {
          revWarnings.push(`Period duration discrepancy: Compares ${baseMetaRev.reporting_period} vs ${compMetaRev.reporting_period}.`);
        }
      }
      if (revWarnings.length > 0) {
        dirExpl += ` [${revWarnings.join(" | ")}]`;
      }

      return {
        ...reverse,
        base_doc_id: baseId,
        comparison_doc_id: compId,
        base_value: reverse.comparison_value,
        comparison_value: reverse.base_value,
        absolute_variance: invAbs,
        percentage_change: invPct,
        status: status,
        display_absolute_variance: invAbs > 0 ? `+${invAbs.toFixed(2)}` : invAbs.toFixed(2),
        display_percentage_change: dispPct,
        directional_explanation: dirExpl,
      };
    }
    return reverse;
  };

  const getVariance = (metricKey: string): CalculationResult | undefined => {
    const baseId = baselineDocId || docA?.doc_id || "";
    const compId = comparisonDocId || docB?.doc_id || "";
    return getPairwiseVariance(metricKey, baseId, compId);
  };

  const getMetricCompatibilityFinding = (metricKey: string): CompatibilityFinding | undefined => {
    if (!activeResult.compatibility?.findings) return undefined;
    const keyUpper = metricKey.toUpperCase();
    return activeResult.compatibility.findings.find((f) => {
      if (f.relevant_fields?.some((rf) => rf.toUpperCase() === keyUpper)) return true;
      if (f.title.toUpperCase().includes(keyUpper) || f.description.toUpperCase().includes(keyUpper)) return true;
      return false;
    });
  };

  const getScopeMismatchFinding = (): CompatibilityFinding | undefined => {
    if (!activeResult.compatibility?.findings) return undefined;
    const baseId = baselineDocId || docA?.doc_id || "";
    const compId = comparisonDocId || docB?.doc_id || "";
    return activeResult.compatibility.findings.find((f) => {
      const isScope = f.code === "SCOPE_MISMATCH" ||
                      f.finding_id?.toLowerCase().includes("scope") ||
                      f.relevant_fields?.some((rf) => rf.toLowerCase().includes("scope")) ||
                      f.title?.toLowerCase().includes("scope");
      if (!isScope) return false;
      if (f.affected_document_ids && f.affected_document_ids.length >= 2) {
        return f.affected_document_ids.includes(baseId) && f.affected_document_ids.includes(compId);
      }
      return true;
    });
  };

  const getPeriodDurationMismatchFinding = (): CompatibilityFinding | undefined => {
    if (!activeResult.compatibility?.findings) return undefined;
    const baseId = baselineDocId || docA?.doc_id || "";
    const compId = comparisonDocId || docB?.doc_id || "";
    return activeResult.compatibility.findings.find((f) => {
      const isPeriod = f.code === "PERIOD_DURATION_MISMATCH" ||
                       f.code === "PERIOD_MISMATCH" ||
                       f.finding_id?.toLowerCase().includes("period") ||
                       f.relevant_fields?.some((rf) => rf.toLowerCase().includes("period")) ||
                       f.title?.toLowerCase().includes("duration") ||
                       f.title?.toLowerCase().includes("period");
      if (!isPeriod) return false;
      if (f.affected_document_ids && f.affected_document_ids.length >= 2) {
        return f.affected_document_ids.includes(baseId) && f.affected_document_ids.includes(compId);
      }
      return true;
    });
  };

  // Helper to format financial unit suffix cleanly
  const formatUnitSuffix = (unit?: string, metricKey?: string): string => {
    const keyUpper = (metricKey || "").toUpperCase();
    if (keyUpper === "EPS" || keyUpper === "BASIC_EPS" || (unit || "").endsWith("/share")) {
      return ` ${t("compare.unit.per_share")}`;
    }
    const u = (unit || "").toUpperCase();
    if (u === "INR_CRORE" || u === "CRORE") return ` ${t("compare.unit.crore")}`;
    if (u === "INR_LAKH" || u === "LAKH") return ` ${t("compare.unit.lakh")}`;
    if (u.includes("THOUSAND")) return ` ${t("compare.unit.thousand")}`;
    if (u.includes("MILLION")) return ` ${t("compare.unit.million")}`;
    if (u.includes("UNITS")) return ` ${t("compare.unit.units")}`;
    return "";
  };

  const getCurrencyPrefix = (currency?: string, unit?: string): string => {
    const curr = currency || (unit?.startsWith("USD") ? "USD" : unit?.startsWith("EUR") ? "EUR" : unit?.startsWith("GBP") ? "GBP" : "INR");
    if (curr === "INR") return "₹";
    if (curr === "USD") return "$";
    if (curr === "EUR") return "€";
    if (curr === "GBP") return "£";
    return `${curr} `;
  };

  // Helper to format financial amount text
  const formatAmountText = (fVal?: FinancialValue | null) => {
    if (!fVal || fVal.status !== "REPORTED" || fVal.amount === null || fVal.amount === undefined) {
      if (fVal?.status === "UNCERTAIN") {
        return fVal.display_amount || t("compare.matrix.uncertain");
      }
      if (fVal?.status === "AMBIGUOUS") {
        return t("compare.matrix.ambiguous");
      }
      if (fVal?.status === "EXTRACTION_UNAVAILABLE") {
        return t("compare.matrix.extraction_unavailable");
      }
      return t("compare.matrix.not_disclosed_filing");
    }
    if (fVal.display_amount) {
      return fVal.display_amount;
    }
    const prefix = getCurrencyPrefix(fVal.currency, fVal.unit);
    const unitLabel = formatUnitSuffix(fVal.unit, fVal.metric_key);
    return `${prefix}${fVal.amount.toLocaleString()}${unitLabel}`.trim();
  };

  // Helper to render interactive financial amount with evidence viewer, user-entered tag and edit trigger
  const renderInteractiveAmount = (
    fVal?: FinancialValue | null,
    docId?: string,
    metricKey?: string,
    allowEdit: boolean = true
  ) => {
    const isUserCorrected = !!fVal?.is_user_corrected;
    const prefix = getCurrencyPrefix(fVal?.currency, fVal?.unit);
    const unitSuffix = formatUnitSuffix(fVal?.unit, metricKey);
    const originalText =
      fVal?.original_amount !== null && fVal?.original_amount !== undefined
        ? `${prefix}${fVal.original_amount.toLocaleString()}${unitSuffix}`.trim()
        : null;

    let valueDisplay = null;
    if (!fVal || fVal.status !== "REPORTED" || fVal.amount === null || fVal.amount === undefined) {
      if (fVal?.status === "UNCERTAIN") {
        valueDisplay = (
          <span className="text-amber-800 italic font-medium text-xs bg-amber-50/70 px-1.5 py-0.5 rounded border border-amber-200" title={t("compare.dash.unverified_period_title")}>
            {fVal.display_amount || t("compare.matrix.uncertain")}
          </span>
        );
      } else if (fVal?.status === "AMBIGUOUS") {
        valueDisplay = (
          <span className="text-orange-800 italic font-medium text-xs bg-orange-50 px-1.5 py-0.5 rounded border border-orange-200" title={t("compare.matrix.ambiguous")}>
            {t("compare.matrix.ambiguous")}
          </span>
        );
      } else if (fVal?.status === "EXTRACTION_UNAVAILABLE") {
        valueDisplay = (
          <span className="text-neutral-500 italic font-medium text-xs bg-neutral-100 px-1.5 py-0.5 rounded border border-neutral-200" title={t("compare.matrix.extraction_unavailable")}>
            {t("compare.matrix.extraction_unavailable")}
          </span>
        );
      } else {
        valueDisplay = (
          <span className="text-neutral-400 italic font-normal text-xs">
            {t("compare.matrix.not_disclosed_filing")}
          </span>
        );
      }
    } else {
      const text = formatAmountText(fVal);
      const amountColorClass = fVal.amount < 0 ? "text-error-600" : "text-neutral-900";

      if (fVal.evidence) {
        valueDisplay = (
          <button
            type="button"
            onClick={() => handleOpenValueEvidence(fVal)}
            className={`font-mono font-bold text-left hover:underline hover:text-accent-700 transition-colors cursor-pointer inline-flex items-center gap-1 group ${amountColorClass}`}
            title="Click to inspect verbatim source evidence in document viewer"
            aria-label={t("compare.dash.inspect_evidence_title")}
          >
            <span>{text}</span>
            <FileText className="w-3 h-3 text-neutral-400 group-hover:text-accent-600 shrink-0" />
          </button>
        );
      } else {
        valueDisplay = <span className={`font-mono font-bold ${amountColorClass}`}>{text}</span>;
      }
    }

    return (
      <div className="inline-flex items-center gap-1.5 flex-wrap">
        {valueDisplay}

        {/* User-entered badge */}
        {isUserCorrected && (
          <span
            className="inline-flex items-center gap-0.5 px-1.5 py-0.2 rounded text-[10px] font-bold bg-amber-100 text-amber-900 border border-amber-300"
            title={originalText ? `${t("compare.correction.original_extracted")}: ${originalText}` : t("compare.correction.user_entered")}
            data-testid="user-entered-badge"
          >
            <Edit3 className="w-2.5 h-2.5 text-amber-700" />
            <span>{t("compare.correction.user_entered")}</span>
          </span>
        )}

        {/* Edit Button */}
        {allowEdit && docId && metricKey && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              handleOpenEditModal(docId, metricKey, fVal);
            }}
            className="p-1 text-neutral-400 hover:text-accent-700 hover:bg-neutral-100 rounded transition-colors"
            title={t("compare.correction.edit_btn")}
            aria-label={t("compare.correction.edit_btn")}
            data-testid={`edit-btn-${metricKey.toLowerCase()}-${docId}`}
          >
            <Pencil className="w-3 h-3" />
          </button>
        )}
      </div>
    );
  };

  const handleSendChat = async (questionText?: string) => {
    const q = (questionText || chatInput).trim();
    if (!q || isSendingChat) return;

    setChatError(null);
    setIsSendingChat(true);

    const userMsg: ComparisonChatMessage = {
      message_id: `user_${Date.now()}`,
      role: "user",
      content: q,
      cited_evidence: [],
      safety_disclaimer: "",
      timestamp: new Date().toISOString(),
    };
    setChatMessages((prev) => [...prev, userMsg]);
    if (!questionText) setChatInput("");

    try {
      const resp = await sendCompareChat(activeResult.session_id, sessionToken, q, language);
      setChatMessages((prev) => [...prev, resp]);
    } catch (err: any) {
      setChatError(err.message || t("compare.dash.chat_err_failed"));
    } finally {
      setIsSendingChat(false);
    }
  };

  // Additional Disclosed Metrics
  const additionalMetricKeys = Object.keys(activeResult.financial_values).filter(
    (k) =>
      !CORE_METRIC_KEYS.has(k) &&
      !CORE_METRIC_KEYS.has(k.toUpperCase()) &&
      !CORE_METRIC_KEYS.has(k.toLowerCase())
  );

  // 1. Compatibility Banner Component
  const renderCompatibilityBanner = () => {
    const comp = activeResult.compatibility;
    const findings = comp?.findings || [];
    const blockers = findings.filter((f) => f.severity === "BLOCKER");
    const warnings = findings.filter((f) => f.severity === "WARNING" || f.severity === "INFORMATION");

    if (findings.length === 0 && comp?.overall_status === "COMPATIBLE") {
      return (
        <div className="bg-emerald-50/80 border border-emerald-200 text-emerald-900 rounded-xl p-3 px-4 shadow-2xs flex items-center justify-between text-xs">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span className="font-semibold">{t("compare.compat.all_compatible")}</span>
          </div>
          <span className="text-[10px] bg-emerald-100 text-emerald-800 font-bold px-2 py-0.5 rounded">
            {t("compare.dash.all_compatible_badge")}
          </span>
        </div>
      );
    }

    if (findings.length === 0) return null;

    const hasBlockers = blockers.length > 0;

    return (
      <div
        className={`rounded-xl border shadow-2xs transition-all ${
          hasBlockers
            ? "bg-red-50/70 border-red-300 text-red-950"
            : "bg-amber-50/70 border-amber-300 text-amber-950"
        }`}
        data-testid="compatibility-warnings-banner"
      >
        <div className="p-3.5 px-4 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5 flex-wrap">
            {hasBlockers ? (
              <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
            )}
            <span className="text-xs font-bold">
              {t("compare.compat.banner_title")}
            </span>
            <div className="flex items-center gap-1.5">
              {blockers.length > 0 && (
                <span className="bg-red-200 text-red-900 font-extrabold text-[10px] px-2 py-0.5 rounded-full border border-red-300">
                  {blockers.length} {t("compare.compat.blocker_title")}
                </span>
              )}
              {warnings.length > 0 && (
                <span className="bg-amber-200 text-amber-900 font-bold text-[10px] px-2 py-0.5 rounded-full border border-amber-300">
                  {warnings.length} {t("compare.compat.warning_title")}
                </span>
              )}
            </div>
          </div>

          <button
            type="button"
            onClick={() => setCompatBannerExpanded(!compatBannerExpanded)}
            className="text-xs font-bold text-neutral-700 hover:text-neutral-900 inline-flex items-center gap-1 shrink-0 p-1 rounded hover:bg-neutral-200/50"
            aria-expanded={compatBannerExpanded}
          >
            <span>
              {compatBannerExpanded
                ? t("compare.compat.collapse")
                : t("compare.compat.expand")}
            </span>
            {compatBannerExpanded ? (
              <ChevronUp className="w-3.5 h-3.5" />
            ) : (
              <ChevronDown className="w-3.5 h-3.5" />
            )}
          </button>
        </div>

        {compatBannerExpanded && (
          <div className="px-4 pb-4 pt-1 border-t border-neutral-200/50 space-y-2.5">
            {findings.map((f, idx) => (
              <div
                key={f.finding_id || idx}
                className="bg-white/90 rounded-lg p-3 border border-neutral-200 text-xs space-y-1.5"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-[10px] font-extrabold px-1.5 py-0.5 rounded uppercase ${
                        f.severity === "BLOCKER"
                          ? "bg-red-100 text-red-800 border border-red-300"
                          : "bg-amber-100 text-amber-800 border border-amber-300"
                      }`}
                    >
                      {f.severity}
                    </span>
                    <span className="font-bold text-neutral-900">{f.title}</span>
                  </div>
                  {f.affected_document_ids && f.affected_document_ids.length > 0 && (
                    <div className="flex items-center gap-1">
                      {f.affected_document_ids.map((id) => {
                        const doc = docs.find((d) => d.doc_id === id);
                        const meta = activeResult.metadata[id];
                        return (
                          <span
                            key={id}
                            className="bg-neutral-100 text-neutral-700 text-[10px] px-1.5 py-0.5 rounded font-mono"
                            title={meta?.company_name || id}
                          >
                            {doc?.slot.toUpperCase().replace("DOC_", "") || id.slice(0, 4)}
                          </span>
                        );
                      })}
                    </div>
                  )}
                </div>

                <p className="text-neutral-700 leading-relaxed">{f.description}</p>

                {f.remediation_hint && (
                  <div className="text-[11px] text-neutral-600 bg-neutral-50 p-2 rounded border border-neutral-200">
                    <span className="font-bold text-neutral-800">
                      {t("compare.compat.remediation")}{" "}
                    </span>
                    <span>{f.remediation_hint}</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  // 2. Key Financial Cards Grid Component
  const renderKeyFinancialCards = () => {
    return (
      <div className="space-y-4" data-testid="key-financial-cards-grid">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-extrabold text-neutral-900 uppercase tracking-wider">
              {t("compare.cards.title")}
            </h3>
            <p className="text-xs text-neutral-500 mt-0.5">
              {t("compare.cards.subtitle")}
            </p>
          </div>
          <span className="text-[11px] font-semibold text-neutral-600 bg-neutral-100 px-2.5 py-1 rounded-full border border-neutral-200">
            {t("compare.dash.core_indicators_badge")}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {METRIC_ROWS.map((row) => {
            const variance = getVariance(row.key);
            const compatFinding = getMetricCompatibilityFinding(row.key);
            const scopeFinding = getScopeMismatchFinding();
            const periodFinding = getPeriodDurationMismatchFinding();
            const currentBaseMeta = activeResult.metadata[baselineDocId || docA?.doc_id || ""];
            const currentCompMeta = activeResult.metadata[comparisonDocId || docB?.doc_id || ""];
            const hasScopeMismatch = Boolean(
              scopeFinding ||
              (currentBaseMeta && currentCompMeta &&
               currentBaseMeta.reporting_scope && currentCompMeta.reporting_scope &&
               currentBaseMeta.reporting_scope !== "UNKNOWN" && currentCompMeta.reporting_scope !== "UNKNOWN" &&
               currentBaseMeta.reporting_scope !== "BOTH" && currentCompMeta.reporting_scope !== "BOTH" &&
               currentBaseMeta.reporting_scope !== currentCompMeta.reporting_scope)
            );
            const hasPeriodMismatch = Boolean(
              periodFinding ||
              (currentBaseMeta && currentCompMeta &&
               currentBaseMeta.reporting_period && currentCompMeta.reporting_period &&
               currentBaseMeta.reporting_period !== "Unknown" && currentCompMeta.reporting_period !== "Unknown" &&
               currentBaseMeta.reporting_period.toLowerCase() !== currentCompMeta.reporting_period.toLowerCase())
            );

            // Find if any document has evidence for this metric
            const valWithEv = docs
              .map((d) => getDocVal(d.doc_id, row.key))
              .find((v) => v?.evidence);

            return (
              <div
                key={row.key}
                data-testid={`card-${row.key.toLowerCase()}`}
                className="bg-white border border-neutral-200 rounded-xl p-4 shadow-xs hover:border-neutral-300 transition-all flex flex-col justify-between space-y-3"
              >
                <div className="space-y-2">
                  {/* Metric Header */}
                  <div className="flex items-start justify-between gap-2 border-b border-neutral-100 pb-2">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="font-bold text-xs text-neutral-900">
                        {t(row.labelKey)}
                      </span>
                      {hasScopeMismatch && (
                        <span
                          className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-amber-100 text-amber-800 border border-amber-300"
                          title={scopeFinding?.description || "Scope Mismatch: Standalone vs Consolidated perimeter difference."}
                        >
                          ⚠ {t("compare.warn.scope_mismatch")}
                        </span>
                      )}
                      {hasPeriodMismatch && (
                        <span
                          className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-blue-100 text-blue-800 border border-blue-300"
                          title={periodFinding?.description || "Period Duration Discrepancy: Compares different reporting period durations."}
                        >
                          ⚠ {t("compare.warn.period_duration")}
                        </span>
                      )}
                      {compatFinding && !hasScopeMismatch && !hasPeriodMismatch && (
                        <span
                          className="px-1.5 py-0.2 rounded text-[9px] font-semibold bg-amber-100 text-amber-800 border border-amber-300"
                          title={compatFinding.description}
                        >
                          ⚠ {t("compare.warn.context")}
                        </span>
                      )}
                    </div>
                    {/* Neutral Variance Pill */}
                    {variance?.display_percentage_change ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-neutral-100 text-neutral-900 border border-neutral-300 shrink-0">
                        {variance.percentage_change && variance.percentage_change > 0 ? (
                          <span>↑</span>
                        ) : variance.percentage_change && variance.percentage_change < 0 ? (
                          <span>↓</span>
                        ) : (
                          <span>—</span>
                        )}
                        <span>{variance.display_percentage_change}</span>
                      </span>
                    ) : (
                      <span className="text-[10px] text-neutral-400 font-mono italic shrink-0">—</span>
                    )}
                  </div>

                  {/* Document Values Grid */}
                  <div className="space-y-2 pt-1">
                    {docs.map((doc) => {
                      const meta = activeResult.metadata[doc.doc_id];
                      const val = getDocVal(doc.doc_id, row.key);
                      const isBase = doc.doc_id === (baselineDocId || docA?.doc_id);

                      return (
                        <div
                          key={doc.doc_id}
                          className={`p-2 rounded-lg border text-xs flex items-center justify-between ${
                            isBase
                              ? "bg-neutral-50/80 border-neutral-200"
                              : "bg-white border-neutral-100"
                          }`}
                        >
                          <div className="flex flex-col min-w-0 pr-2">
                            <div className="flex items-center gap-1.5">
                              <span className="w-3.5 h-3.5 rounded bg-neutral-800 text-white font-bold text-[9px] flex items-center justify-center shrink-0">
                                {doc.slot.toUpperCase().replace("DOC_", "")}
                              </span>
                              <span className="font-medium text-neutral-800 truncate text-[11px]">
                                {meta?.company_name || doc.original_filename}
                              </span>
                            </div>
                            <span className="text-[10px] text-neutral-400 mt-0.5">
                              {meta?.financial_year || "FY"} · {meta?.reporting_period || "Annual"}
                            </span>
                          </div>

                          <div className="text-right shrink-0">
                            {renderInteractiveAmount(val, doc.doc_id, row.key)}
                            <span className="block text-[9px] text-neutral-400 font-mono">
                              {val?.currency || meta?.currency || "INR"}
                              {formatUnitSuffix(val?.unit || meta?.reporting_scale, row.key) ? ` · ${formatUnitSuffix(val?.unit || meta?.reporting_scale, row.key).trim()}` : ""}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Card Footer: Directional explanation & Evidence button */}
                <div className="pt-2 border-t border-neutral-100 flex items-center justify-between text-[11px]">
                  {variance?.directional_explanation ? (
                    <span
                      className="text-neutral-600 font-medium truncate max-w-[200px] sm:max-w-xs hover:text-neutral-900 cursor-help"
                      title={variance.directional_explanation}
                    >
                      {variance.directional_explanation}
                    </span>
                  ) : (
                    <span className="text-neutral-400 italic">
                      {variance?.status === "CALCULATED" ? t("compare.trend.flat") : "—"}
                    </span>
                  )}

                  {valWithEv?.evidence ? (
                    <button
                      type="button"
                      onClick={() => handleOpenValueEvidence(valWithEv)}
                      className="text-accent-700 hover:text-accent-900 font-semibold inline-flex items-center gap-1 hover:underline cursor-pointer"
                      title={t("compare.cards.view_evidence")}
                    >
                      <FileText className="w-3 h-3 text-accent-600" />
                      <span>{t("compare.cards.view_evidence")}</span>
                    </button>
                  ) : (
                    <span className="text-neutral-400 text-[10px] italic">
                      {t("compare.cards.no_evidence")}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8 space-y-6 animate-fade-in font-sans">
      {/* 1. SEBI Educational Non-Advisory Notice Banner */}
      <div className="bg-neutral-900 text-white rounded-xl p-3.5 px-5 shadow-sm flex items-start gap-3 border border-neutral-800">
        <Info className="w-4 h-4 text-accent-400 shrink-0 mt-0.5" />
        <p className="text-xs font-medium text-neutral-200 leading-relaxed">
          {t("compare.dash.disclaimer")}
        </p>
      </div>

      {/* 2. Top Bar & Filing Provenance */}
      <div className="bg-white border border-neutral-200 rounded-xl p-5 shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="space-y-1.5">
          <div className="flex items-center gap-3">
            <span className="text-xs font-extrabold text-accent-700 uppercase tracking-widest">
              {t("compare.dash.title")}
            </span>
            {/* Mode Badge */}
            {activeResult.mode === "LOCAL_MODE" && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-extrabold bg-neutral-100 text-neutral-800 border border-neutral-300">
                <ShieldCheck className="w-3.5 h-3.5 text-neutral-600" />
                {t("compare.dash.mode.LOCAL_MODE")}
              </span>
            )}
            {activeResult.mode === "AI_ASSISTED" && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-extrabold bg-accent-50 text-accent-700 border border-accent-200">
                <Sparkles className="w-3.5 h-3.5 text-accent-600" />
                {t("compare.dash.mode.AI_ASSISTED")}
              </span>
            )}
            {activeResult.mode === "LOCAL_MODE_FALLBACK" && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-extrabold bg-warning-50 text-warning-800 border border-warning-200">
                <AlertTriangle className="w-3.5 h-3.5 text-warning-600" />
                {t("compare.dash.mode.LOCAL_MODE_FALLBACK")}
              </span>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2 pt-1">
            {docs.map((doc) => {
              const meta = activeResult.metadata[doc.doc_id];
              return (
                <div
                  key={doc.doc_id}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-neutral-100 text-neutral-800 text-xs font-semibold"
                >
                  <span className="w-4 h-4 rounded bg-neutral-900 text-white font-bold text-[10px] flex items-center justify-center">
                    {doc.slot.toUpperCase().replace("DOC_", "")}
                  </span>
                  <span>{meta?.company_name || doc.original_filename}</span>
                  <span className="text-neutral-400 font-normal">({meta?.financial_year || "FY"})</span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 shrink-0">
          {/* Export PDF Button */}
          <Button
            variant="outline"
            size="sm"
            onClick={handleExportPdf}
            disabled={isExportingPdf || isExportingXlsx}
            className="text-xs font-bold border-neutral-300 hover:bg-neutral-100"
            title={t("compare.export.pdf_button")}
          >
            {isExportingPdf ? (
              <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin text-neutral-600" />
            ) : (
              <FileDown className="w-3.5 h-3.5 mr-1.5 text-rose-600" />
            )}
            {isExportingPdf ? t("compare.export.generating_pdf") : t("compare.export.pdf_button")}
          </Button>

          {/* Export Excel Button */}
          <Button
            variant="outline"
            size="sm"
            onClick={handleExportXlsx}
            disabled={isExportingPdf || isExportingXlsx}
            className="text-xs font-bold border-neutral-300 hover:bg-neutral-100"
            title={t("compare.export.xlsx_button")}
          >
            {isExportingXlsx ? (
              <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin text-neutral-600" />
            ) : (
              <FileSpreadsheet className="w-3.5 h-3.5 mr-1.5 text-emerald-600" />
            )}
            {isExportingXlsx ? t("compare.export.generating_xlsx") : t("compare.export.xlsx_button")}
          </Button>

          <Button
            variant="ghost"
            size="sm"
            onClick={onNewComparison}
            className="text-xs font-bold text-neutral-600 hover:text-neutral-900"
          >
            <ArrowLeft className="w-3.5 h-3.5 mr-1.5" />
            {t("compare.dash.new_comparison")}
          </Button>
        </div>
      </div>

      {/* Export & Action Notifications */}
      {exportError && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-2.5 rounded-lg text-xs font-medium flex items-center justify-between">
          <span>{exportError}</span>
          <button onClick={() => setExportError(null)} className="text-red-500 hover:text-red-700 font-bold ml-2" aria-label={t("compare.dash.dismiss_error_aria")}>✕</button>
        </div>
      )}
      {exportSuccess && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 px-4 py-2.5 rounded-lg text-xs font-medium flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{exportSuccess}</span>
        </div>
      )}
      {correctionSuccess && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 px-4 py-2.5 rounded-lg text-xs font-medium flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{correctionSuccess}</span>
        </div>
      )}

      {/* 3. Consolidated Compatibility Warnings Banner */}
      {renderCompatibilityBanner()}

      {/* 4. Active Corrections Banner */}
      {activeCorrectionsCount > 0 && (
        <div
          className="bg-amber-50 border border-amber-300 text-amber-950 rounded-xl p-3 px-4 shadow-2xs flex flex-wrap items-center justify-between gap-3 text-xs"
          data-testid="active-corrections-banner"
        >
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
            <span className="font-bold">
              {activeCorrectionsCount} {t("compare.correction.active_banner")}
            </span>
            <span className="text-amber-800 text-[11px]">
              {t("compare.dash.active_corrections_subtitle")}
            </span>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={handleUndoCorrection}
            disabled={isUndoingCorrection}
            className="text-xs font-bold border-amber-400 bg-white hover:bg-amber-100 text-amber-900 shadow-2xs"
            data-testid="undo-correction-btn"
          >
            {isUndoingCorrection ? (
              <Loader2 className="w-3 h-3 mr-1.5 animate-spin text-amber-700" />
            ) : (
              <RotateCcw className="w-3 h-3 mr-1.5 text-amber-700" />
            )}
            {isUndoingCorrection
              ? t("compare.correction.undoing")
              : t("compare.correction.undo_btn")}
          </Button>
        </div>
      )}

      {/* 5. Navigation Tabs */}
      <div className="flex border-b border-neutral-200 overflow-x-auto space-x-1 sm:space-x-4">
        {[
          { key: "matrix", label: t("compare.dash.tabs.matrix"), icon: Table },
          { key: "charts", label: t("compare.dash.tabs.charts"), icon: BarChart3 },
          { key: "summary", label: t("compare.dash.tabs.summary"), icon: FileText },
          { key: "risks", label: t("compare.dash.tabs.risks"), icon: AlertCircle },
          { key: "chat", label: t("compare.dash.tabs.chat"), icon: MessageSquare },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key as DashboardTab)}
              className={`flex items-center gap-2 py-3 px-4 border-b-2 font-bold text-xs transition-colors shrink-0 ${
                isActive
                  ? "border-primary-900 text-primary-900"
                  : "border-transparent text-neutral-500 hover:text-neutral-900 hover:border-neutral-300"
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* 6. Tab Content */}
      <div className="space-y-6">
        {/* TAB 1: FINANCIAL MATRIX */}
        {activeTab === "matrix" && (
          <div className="space-y-4">
            {/* Multi-Document Baseline Selector Bar */}
            <div className="flex flex-wrap items-center justify-between gap-3 bg-neutral-50 p-3 rounded-xl border border-neutral-200">
              <div className="flex flex-wrap items-center gap-4">
                <div className="flex items-center gap-2">
                  <label htmlFor="baseline-selector" className="text-xs font-bold text-neutral-700">
                    {t("compare.matrix.baseline_selector")}
                  </label>
                  <select
                    id="baseline-selector"
                    value={baselineDocId}
                    onChange={(e) => {
                      const newBase = e.target.value;
                      setBaselineDocId(newBase);
                      if (newBase === comparisonDocId) {
                        const nextComp = docs.find((d) => d.doc_id !== newBase)?.doc_id || "";
                        setComparisonDocId(nextComp);
                      }
                    }}
                    className="text-xs font-semibold bg-white border border-neutral-300 rounded px-2.5 py-1 text-neutral-800 focus:outline-none focus:ring-1 focus:ring-accent-500"
                    data-testid="baseline-doc-selector"
                  >
                    {docs.map((d) => {
                      const meta = activeResult.metadata[d.doc_id];
                      return (
                        <option key={d.doc_id} value={d.doc_id}>
                          {meta?.company_name || d.original_filename} ({meta?.financial_year || d.slot})
                        </option>
                      );
                    })}
                  </select>
                </div>

                {docs.length > 2 && (
                  <div className="flex items-center gap-2">
                    <label htmlFor="comparison-selector" className="text-xs font-bold text-neutral-700">
                      {t("compare.dash.compare_selector")}
                    </label>
                    <select
                      id="comparison-selector"
                      value={comparisonDocId}
                      onChange={(e) => setComparisonDocId(e.target.value)}
                      className="text-xs font-semibold bg-white border border-neutral-300 rounded px-2.5 py-1 text-neutral-800 focus:outline-none focus:ring-1 focus:ring-accent-500"
                      data-testid="comparison-doc-selector"
                    >
                      {docs
                        .filter((d) => d.doc_id !== baselineDocId)
                        .map((d) => {
                          const meta = activeResult.metadata[d.doc_id];
                          return (
                            <option key={d.doc_id} value={d.doc_id}>
                              {meta?.company_name || d.original_filename} ({meta?.financial_year || d.slot})
                            </option>
                          );
                        })}
                    </select>
                  </div>
                )}
              </div>

              <span className="text-[11px] text-neutral-500 italic">
                {t("compare.matrix.click_evidence_hint")}
              </span>
            </div>

            {/* Core Financial Matrix Table */}
            <div className="bg-white border border-neutral-200 rounded-xl overflow-hidden shadow-sm">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="bg-neutral-50/80 border-b border-neutral-200 text-neutral-600 font-bold uppercase tracking-wider text-[11px]">
                      <th className="py-3 px-4">{t("compare.matrix.col.metric")}</th>
                      {docs.map((doc) => {
                        const meta = activeResult.metadata[doc.doc_id];
                        const isBase = doc.doc_id === (baselineDocId || docA?.doc_id);
                        return (
                          <th key={doc.doc_id} className={`py-3 px-4 ${isBase ? "bg-neutral-100/70" : ""}`}>
                            <div className="flex items-center gap-1.5">
                              <span className="w-4 h-4 rounded bg-neutral-900 text-white text-[10px] flex items-center justify-center font-bold">
                                {doc.slot.toUpperCase().replace("DOC_", "")}
                              </span>
                              <span className="truncate max-w-[140px] text-neutral-900">
                                {meta?.company_name || doc.original_filename}
                              </span>
                              {isBase && (
                                <span className="text-[9px] bg-neutral-800 text-white px-1 rounded font-normal normal-case">
                                  {t("compare.dash.base_badge")}
                                </span>
                              )}
                            </div>
                            <span className="text-[10px] text-neutral-400 font-medium normal-case block mt-0.5">
                              {meta?.financial_year} · {meta?.reporting_period}
                            </span>
                          </th>
                        );
                      })}
                      <th className="py-3 px-4 text-neutral-900">{t("compare.matrix.col.abs")}</th>
                      <th className="py-3 px-4 text-neutral-900">{t("compare.matrix.col.pct")}</th>
                      <th className="py-3 px-4 text-neutral-900">{t("compare.matrix.col.trend")}</th>
                    </tr>
                  </thead>

                  <tbody className="divide-y divide-neutral-100">
                    {METRIC_ROWS.map((row) => {
                      const variance = getVariance(row.key);
                      const compatFinding = getMetricCompatibilityFinding(row.key);
                      const scopeFinding = getScopeMismatchFinding();
                      const periodFinding = getPeriodDurationMismatchFinding();
                      const currentBaseMeta = activeResult.metadata[baselineDocId || docA?.doc_id || ""];
                      const currentCompMeta = activeResult.metadata[comparisonDocId || docB?.doc_id || ""];
                      const hasScopeMismatch = Boolean(
                        scopeFinding ||
                        (currentBaseMeta && currentCompMeta &&
                         currentBaseMeta.reporting_scope && currentCompMeta.reporting_scope &&
                         currentBaseMeta.reporting_scope !== "UNKNOWN" && currentCompMeta.reporting_scope !== "UNKNOWN" &&
                         currentBaseMeta.reporting_scope !== "BOTH" && currentCompMeta.reporting_scope !== "BOTH" &&
                         currentBaseMeta.reporting_scope !== currentCompMeta.reporting_scope)
                      );
                      const hasPeriodMismatch = Boolean(
                        periodFinding ||
                        (currentBaseMeta && currentCompMeta &&
                         currentBaseMeta.reporting_period && currentCompMeta.reporting_period &&
                         currentBaseMeta.reporting_period !== "Unknown" && currentCompMeta.reporting_period !== "Unknown" &&
                         currentBaseMeta.reporting_period.toLowerCase() !== currentCompMeta.reporting_period.toLowerCase())
                      );

                      return (
                        <tr key={row.key} className="hover:bg-neutral-50/50 transition-colors">
                          {/* Metric Name */}
                          <td className="py-3 px-4 font-bold text-neutral-900">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <span>{t(row.labelKey)}</span>
                              {hasScopeMismatch && (
                                <span
                                  className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-semibold bg-amber-100 text-amber-800 border border-amber-300"
                                  title={scopeFinding?.description || "Scope Mismatch: Standalone vs Consolidated perimeter difference."}
                                >
                                  ⚠ {t("compare.warn.scope_mismatch")}
                                </span>
                              )}
                              {hasPeriodMismatch && (
                                <span
                                  className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-semibold bg-blue-100 text-blue-800 border border-blue-300"
                                  title={periodFinding?.description || "Period Duration Discrepancy: Compares different reporting period durations."}
                                >
                                  ⚠ {t("compare.warn.period_duration")}
                                </span>
                              )}
                              {compatFinding && !hasScopeMismatch && !hasPeriodMismatch && (
                                <span
                                  className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-semibold bg-amber-100 text-amber-800 border border-amber-300"
                                  title={`${compatFinding.title}: ${compatFinding.description}`}
                                >
                                  ⚠ {t("compare.warn.context")}
                                </span>
                              )}
                            </div>
                          </td>

                          {/* Value for each Doc */}
                          {docs.map((doc) => {
                            const val = getDocVal(doc.doc_id, row.key);
                            const isBase = doc.doc_id === (baselineDocId || docA?.doc_id);
                            return (
                              <td key={doc.doc_id} className={`py-3 px-4 ${isBase ? "bg-neutral-50/50" : ""}`}>
                                {renderInteractiveAmount(val, doc.doc_id, row.key)}
                              </td>
                            );
                          })}

                          {/* Absolute Variance */}
                          <td className="py-3 px-4 font-mono font-bold">
                            {variance?.display_absolute_variance ? (
                              <span className="text-neutral-900">
                                {variance.display_absolute_variance}
                              </span>
                            ) : (
                              <span className="text-neutral-400 font-normal italic">—</span>
                            )}
                          </td>

                          {/* % Change - Neutral trend styling (no green/red good/bad signals) */}
                          <td className="py-3 px-4 font-mono font-bold">
                            {variance?.display_percentage_change ? (
                              <span className="inline-flex items-center gap-1 text-neutral-900 bg-neutral-100 px-2 py-0.5 rounded text-xs border border-neutral-200">
                                {variance.percentage_change && variance.percentage_change > 0 ? (
                                  <span>↑</span>
                                ) : variance.percentage_change && variance.percentage_change < 0 ? (
                                  <span>↓</span>
                                ) : (
                                  <span>—</span>
                                )}
                                <span>{variance.display_percentage_change}</span>
                              </span>
                            ) : (
                              <span className="text-neutral-400 font-normal italic">—</span>
                            )}
                          </td>

                          {/* Directional Explanation / Classification */}
                          <td className="py-3 px-4">
                            {variance?.directional_explanation ? (
                              <span className="text-[11px] font-semibold text-neutral-700 bg-neutral-100 px-2 py-0.5 rounded border border-neutral-200">
                                {variance.directional_explanation}
                              </span>
                            ) : variance?.status === "CALCULATED" ? (
                              <span className="text-[11px] text-neutral-500">
                                {t("compare.dash.standard_variance")}
                              </span>
                            ) : (
                              <span className="text-[11px] text-neutral-400 italic">
                                {variance?.status.replace(/_/g, " ") || t("compare.dash.no_variance")}
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Additional Disclosed Metrics Section */}
            <div className="bg-white border border-neutral-200 rounded-xl overflow-hidden shadow-sm" data-testid="additional-metrics-section">
              <button
                type="button"
                onClick={() => setAdditionalMetricsExpanded(!additionalMetricsExpanded)}
                className="w-full py-3 px-4 bg-neutral-50 hover:bg-neutral-100/80 transition-colors flex items-center justify-between text-left text-xs font-bold text-neutral-800"
                aria-expanded={additionalMetricsExpanded}
              >
                <div className="flex items-center gap-2">
                  <Layers className="w-4 h-4 text-neutral-600" />
                  <span>{t("compare.matrix.additional_metrics")}</span>
                  <span className="bg-neutral-200 text-neutral-700 px-2 py-0.2 rounded-full text-[10px] font-mono">
                    {additionalMetricKeys.length}
                  </span>
                </div>
                {additionalMetricsExpanded ? (
                  <ChevronUp className="w-4 h-4 text-neutral-500" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-neutral-500" />
                )}
              </button>

              {additionalMetricsExpanded && (
                <div className="border-t border-neutral-200">
                  {additionalMetricKeys.length > 0 ? (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left border-collapse text-xs">
                        <thead>
                          <tr className="bg-neutral-50/50 border-b border-neutral-200 text-neutral-500 font-semibold uppercase tracking-wider text-[10px]">
                            <th className="py-2.5 px-4">{t("compare.matrix.col.metric")}</th>
                            {docs.map((doc) => {
                              const meta = activeResult.metadata[doc.doc_id];
                              return (
                                <th key={doc.doc_id} className="py-2.5 px-4">
                                  {meta?.company_name || doc.original_filename}
                                </th>
                              );
                            })}
                            <th className="py-2.5 px-4">{t("compare.matrix.col.abs")}</th>
                            <th className="py-2.5 px-4">{t("compare.matrix.col.pct")}</th>
                            <th className="py-2.5 px-4">{t("compare.matrix.col.trend")}</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-neutral-100">
                          {additionalMetricKeys.map((key) => {
                            const variance = getVariance(key);
                            // Prettify metric label
                            const sampleVal = docs.map((d) => getDocVal(d.doc_id, key)).find(Boolean);
                            const label = sampleVal?.label || key.replace(/_/g, " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());

                            return (
                              <tr key={key} className="hover:bg-neutral-50/40 transition-colors">
                                <td className="py-2.5 px-4 font-semibold text-neutral-800">
                                  {label}
                                </td>
                                {docs.map((doc) => {
                                  const val = getDocVal(doc.doc_id, key);
                                  return (
                                    <td key={doc.doc_id} className="py-2.5 px-4">
                                      {renderInteractiveAmount(val, doc.doc_id, key)}
                                    </td>
                                  );
                                })}
                                <td className="py-2.5 px-4 font-mono font-medium text-neutral-800">
                                  {variance?.display_absolute_variance || "—"}
                                </td>
                                <td className="py-2.5 px-4 font-mono font-medium text-neutral-800">
                                  {variance?.display_percentage_change ? (
                                    <span className="inline-flex items-center gap-1 bg-neutral-100 px-1.5 py-0.5 rounded text-[11px]">
                                      {variance.display_percentage_change}
                                    </span>
                                  ) : (
                                    "—"
                                  )}
                                </td>
                                <td className="py-2.5 px-4 text-[11px] text-neutral-600">
                                  {variance?.directional_explanation || (variance?.status === "CALCULATED" ? t("compare.trend.flat") : "—")}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="p-4 text-center text-xs text-neutral-400 italic">
                      {t("compare.matrix.no_additional")}
                    </div>
                  )}
                </div>
              )}
            </div>

            <p className="text-xs text-neutral-500 italic px-2">
              {t("compare.dash.missing_metrics_notice")}
            </p>
          </div>
        )}

        {/* TAB 2: VISUAL CHARTS */}
        {activeTab === "charts" && (
          <CompareSvgCharts
            documents={activeResult.documents}
            financialValues={activeResult.financial_values}
            metadata={activeResult.metadata}
            compatibility={activeResult.compatibility}
            language={language}
          />
        )}

        {/* TAB 3: EXECUTIVE SUMMARY */}
        {activeTab === "summary" && (
          <div className="space-y-6">
            {/* Overview Story */}
            {activeResult.executive_summary && (
              <div className="bg-white border border-neutral-200 rounded-xl p-6 shadow-sm space-y-3">
                <div className="flex items-center justify-between border-b border-neutral-100 pb-3">
                  <h3 className="text-sm font-extrabold text-neutral-900 uppercase tracking-wider">
                    {t("compare.dash.comparative_story_title")}
                  </h3>
                  <span className="text-[10px] font-bold bg-neutral-100 text-neutral-600 px-2 py-0.5 rounded">
                    {t(`compare.fact.${activeResult.executive_summary.fact_classification}`) || activeResult.executive_summary.fact_classification}
                  </span>
                </div>
                <p className="text-sm text-neutral-800 leading-relaxed font-medium">
                  {activeResult.executive_summary.overview_story}
                </p>
              </div>
            )}

            {/* Key Financial Cards Grid */}
            {renderKeyFinancialCards()}

            {/* Narrative Cards Grid */}
            {activeResult.executive_summary && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Positive Improvements */}
                <div className="bg-white border-l-4 border-l-success-600 border border-neutral-200 rounded-xl p-5 shadow-sm space-y-3">
                  <h4 className="text-xs font-bold text-success-800 uppercase tracking-wider flex items-center gap-1.5">
                    <TrendingUp className="w-4 h-4" />
                    {t("compare.dash.pos_changes_title")}
                  </h4>
                  <ul className="space-y-2 text-xs text-neutral-700 list-disc pl-4">
                    {activeResult.executive_summary.core_positive_changes.length > 0 ? (
                      activeResult.executive_summary.core_positive_changes.map((item, i) => (
                        <li key={i}>{item}</li>
                      ))
                    ) : (
                      <li className="italic text-neutral-400 list-none">{t("compare.dash.pos_changes_empty")}</li>
                    )}
                  </ul>
                </div>

                {/* Negative Pressure */}
                <div className="bg-white border-l-4 border-l-error-500 border border-neutral-200 rounded-xl p-5 shadow-sm space-y-3">
                  <h4 className="text-xs font-bold text-error-800 uppercase tracking-wider flex items-center gap-1.5">
                    <TrendingDown className="w-4 h-4" />
                    {t("compare.dash.pressures_title")}
                  </h4>
                  <ul className="space-y-2 text-xs text-neutral-700 list-disc pl-4">
                    {activeResult.executive_summary.core_negative_changes.length > 0 ? (
                      activeResult.executive_summary.core_negative_changes.map((item, i) => (
                        <li key={i}>{item}</li>
                      ))
                    ) : (
                      <li className="italic text-neutral-400 list-none">{t("compare.dash.pressures_empty")}</li>
                    )}
                  </ul>
                </div>

                {/* Neutral Observations */}
                <div className="bg-white border-l-4 border-l-neutral-400 border border-neutral-200 rounded-xl p-5 shadow-sm space-y-3">
                  <h4 className="text-xs font-bold text-neutral-700 uppercase tracking-wider flex items-center gap-1.5">
                    <Minus className="w-4 h-4" />
                    {t("compare.dash.neutral_shifts_title")}
                  </h4>
                  <ul className="space-y-2 text-xs text-neutral-700 list-disc pl-4">
                    {activeResult.executive_summary.neutral_observations.length > 0 ? (
                      activeResult.executive_summary.neutral_observations.map((item, i) => (
                        <li key={i}>{item}</li>
                      ))
                    ) : (
                      <li className="italic text-neutral-400 list-none">{t("compare.dash.neutral_shifts_empty")}</li>
                    )}
                  </ul>
                </div>

                {/* Uncertain Findings */}
                <div className="bg-white border-l-4 border-l-purple-500 border border-neutral-200 rounded-xl p-5 shadow-sm space-y-3">
                  <h4 className="text-xs font-bold text-purple-800 uppercase tracking-wider flex items-center gap-1.5">
                    <HelpCircle className="w-4 h-4" />
                    {t("compare.dash.uncertain_title")}
                  </h4>
                  <ul className="space-y-2 text-xs text-neutral-700 list-disc pl-4">
                    {activeResult.executive_summary.uncertain_findings.length > 0 ? (
                      activeResult.executive_summary.uncertain_findings.map((item, i) => (
                        <li key={i}>{item}</li>
                      ))
                    ) : (
                      <li className="italic text-neutral-400 list-none">{t("compare.dash.uncertain_empty")}</li>
                    )}
                  </ul>
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 4: RISKS & ACCOUNTING DIFFERENCES */}
        {activeTab === "risks" && (
          <div className="space-y-6">
            {/* Disclosed Risks */}
            <div className="bg-white border border-neutral-200 rounded-xl p-6 shadow-sm space-y-4">
              <div className="border-b border-neutral-100 pb-3">
                <h3 className="text-sm font-extrabold text-neutral-900 uppercase tracking-wider">
                  {t("compare.dash.disclosed_risks_title")}
                </h3>
                <p className="text-xs text-neutral-500 mt-0.5">
                  {t("compare.dash.disclosed_risks_sub")}
                </p>
              </div>

              {activeResult.risks.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {activeResult.risks.map((risk) => (
                    <div
                      key={risk.risk_id}
                      className="border border-neutral-200 rounded-lg p-4 bg-neutral-50/50 space-y-2 text-xs"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-neutral-900">{risk.title}</span>
                        <Badge
                          variant={risk.severity === "HIGH" ? "error" : "warning"}
                          className="text-[10px]"
                        >
                          {risk.severity} {t("compare.dash.risk_badge_suffix")}
                        </Badge>
                      </div>
                      <p className="text-neutral-600 leading-relaxed">{risk.disclosure_text}</p>
                      {risk.evidence && (
                        <button
                          onClick={() => setSelectedEvidence(risk.evidence)}
                          className="text-accent-600 hover:underline text-[11px] font-semibold flex items-center gap-1 pt-1"
                        >
                          <FileText className="w-3 h-3" /> {t("compare.dash.source_quote_prefix")} ({risk.evidence.document_name})
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-neutral-500 italic">{t("compare.dash.disclosed_risks_empty")}</p>
              )}
            </div>

            {/* Accounting Differences */}
            <div className="bg-white border border-neutral-200 rounded-xl p-6 shadow-sm space-y-4">
              <div className="border-b border-neutral-100 pb-3">
                <h3 className="text-sm font-extrabold text-neutral-900 uppercase tracking-wider">
                  {t("compare.dash.accounting_diff_title")}
                </h3>
                <p className="text-xs text-neutral-500 mt-0.5">
                  {t("compare.dash.accounting_diff_sub")}
                </p>
              </div>

              {activeResult.accounting_differences.length > 0 ? (
                <div className="space-y-3">
                  {activeResult.accounting_differences.map((diff, diffIdx) => (
                    <div
                      key={diff.difference_id}
                      className="border border-neutral-200 rounded-lg p-4 bg-neutral-50/50 space-y-2 text-xs"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-neutral-900">{diff.topic}</span>
                        <span className="text-[10px] font-medium text-neutral-500 bg-neutral-100 px-2 py-0.5 rounded">
                          {t("compare.dash.accounting_diff_item")} #{diffIdx + 1}
                        </span>
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-neutral-700 pt-1">
                        <div className="bg-white p-2.5 rounded border border-neutral-200 space-y-1">
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-neutral-900 block text-[11px]">{t("compare.dash.doc_a_policy")}</span>
                            {diff.evidence_a && (
                              <button
                                onClick={() => setSelectedEvidence(diff.evidence_a)}
                                className="text-[10px] text-accent-700 font-bold hover:underline flex items-center gap-1"
                              >
                                <FileText className="w-3 h-3" /> {t("compare.dash.view_source_btn")}
                              </button>
                            )}
                          </div>
                          <p>{diff.doc_a_policy}</p>
                        </div>
                        <div className="bg-white p-2.5 rounded border border-neutral-200 space-y-1">
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-neutral-900 block text-[11px]">{t("compare.dash.doc_b_policy")}</span>
                            {diff.evidence_b && (
                              <button
                                onClick={() => setSelectedEvidence(diff.evidence_b)}
                                className="text-[10px] text-accent-700 font-bold hover:underline flex items-center gap-1"
                              >
                                <FileText className="w-3 h-3" /> {t("compare.dash.view_source_btn")}
                              </button>
                            )}
                          </div>
                          <p>{diff.doc_b_policy}</p>
                        </div>
                      </div>
                      <p className="text-neutral-700 font-medium pt-1">
                        <span className="font-bold">{t("compare.dash.impact_summary")} </span>
                        {diff.impact_summary}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-neutral-500 italic">{t("compare.dash.accounting_diff_empty")}</p>
              )}
            </div>
          </div>
        )}

        {/* TAB 5: COMPARATIVE GROUNDED CHAT */}
        {activeTab === "chat" && (
          <div className="bg-white border border-neutral-200 rounded-xl p-6 shadow-sm space-y-6">
            <div className="border-b border-neutral-100 pb-3">
              <h3 className="text-sm font-extrabold text-neutral-900 uppercase tracking-wider">
                {t("compare.chat.title")}
              </h3>
              <p className="text-xs text-neutral-500 mt-0.5">
                {t("compare.dash.chat_sub")}
              </p>
            </div>

            {/* Suggested Prompts */}
            <div className="flex flex-wrap gap-2">
              {[
                t("compare.chat.suggested.1"),
                t("compare.chat.suggested.2"),
                t("compare.chat.suggested.3"),
              ].map((q, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSendChat(q)}
                  disabled={isSendingChat}
                  className="text-xs font-semibold bg-neutral-100 hover:bg-neutral-200 text-neutral-800 px-3 py-1.5 rounded-full transition-colors text-left"
                >
                  &ldquo;{q}&rdquo;
                </button>
              ))}
            </div>

            {/* Chat History */}
            <div className="space-y-4 max-h-[420px] overflow-y-auto pr-2">
              {chatMessages.length === 0 && (
                <div className="text-center py-12 text-neutral-400 text-xs">
                  {t("compare.dash.chat_empty")}
                </div>
              )}

              {chatMessages.map((msg) => (
                <div
                  key={msg.message_id}
                  className={`flex flex-col ${
                    msg.role === "user" ? "items-end" : "items-start"
                  }`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl p-4 text-xs space-y-2 ${
                      msg.role === "user"
                        ? "bg-primary-900 text-white rounded-br-none"
                        : "bg-neutral-100 text-neutral-900 rounded-bl-none border border-neutral-200"
                    }`}
                  >
                    <p className="leading-relaxed whitespace-pre-line">{msg.content}</p>

                    {/* Cited Evidence */}
                    {msg.cited_evidence && msg.cited_evidence.length > 0 && (
                      <div className="pt-2 border-t border-neutral-200/80 space-y-1.5">
                        <span className="text-[10px] font-bold text-accent-700 uppercase tracking-wider block">
                          {t("compare.chat.evidence_badge")}
                        </span>
                        <div className="space-y-1">
                          {msg.cited_evidence.map((ev) => (
                            <div
                              key={ev.evidence_id}
                              onClick={() => setSelectedEvidence(ev)}
                              className="text-[11px] bg-white p-2 rounded border border-neutral-200 text-neutral-800 cursor-pointer hover:border-accent-500 hover:shadow-2xs transition-all"
                              title={t("compare.dash.inspect_evidence_title")}
                            >
                              <div className="flex items-center justify-between">
                                <span className="font-bold text-neutral-900">{ev.document_name}</span>
                                {ev.page_number && (
                                  <span className="text-[10px] text-accent-700 font-mono font-bold">
                                    Page {ev.page_number} →
                                  </span>
                                )}
                              </div>
                              <p className="italic text-neutral-600 mt-0.5">&ldquo;{ev.verbatim_snippet}&rdquo;</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {isSendingChat && (
                <div className="flex items-center gap-2 text-xs text-neutral-500 font-medium">
                  <Loader2 className="w-4 h-4 animate-spin text-accent-600" />
                  {t("compare.dash.chat_analyzing")}
                </div>
              )}
            </div>

            {chatError && (
              <div className="p-3 bg-error-50 text-error-700 text-xs rounded-lg border border-error-200">
                {chatError}
              </div>
            )}

            {/* Chat Input */}
            <div className="flex items-center gap-2 pt-2">
              <input
                type="text"
                placeholder={t("compare.chat.placeholder")}
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleSendChat();
                }}
                disabled={isSendingChat}
                className="flex-1 px-4 py-2.5 border border-neutral-300 rounded-xl text-xs focus:ring-1 focus:ring-accent-500"
              />
              <Button
                onClick={() => handleSendChat()}
                disabled={isSendingChat || !chatInput.trim()}
                className="bg-primary-900 text-white px-5 py-2.5 rounded-xl font-bold text-xs"
              >
                <Send className="w-3.5 h-3.5 mr-1.5" />
                {t("compare.chat.send")}
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* 7. Manual Financial Correction Modal */}
      {editingMetric && (
        <div
          className="fixed inset-0 z-50 bg-neutral-900/60 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto"
          role="dialog"
          aria-modal="true"
          aria-labelledby="correction-modal-title"
          data-testid="financial-correction-modal"
        >
          <div className="bg-white rounded-2xl max-w-lg w-full border border-neutral-200 shadow-2xl p-6 space-y-5 animate-scale-in">
            {/* Modal Header */}
            <div className="flex items-start justify-between border-b border-neutral-100 pb-3">
              <div>
                <h3 id="correction-modal-title" className="text-sm font-extrabold text-neutral-900 uppercase tracking-wider flex items-center gap-2">
                  <Edit3 className="w-4 h-4 text-accent-600" />
                  {t("compare.correction.modal_title")}
                </h3>
                <p className="text-xs text-neutral-500 mt-1">
                  {t("compare.correction.modal_subtitle")}
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  if (!isSubmittingCorrection) {
                    setEditingMetric(null);
                    setCorrectionError(null);
                  }
                }}
                disabled={isSubmittingCorrection}
                className="text-neutral-400 hover:text-neutral-700 font-bold text-base p-1 rounded hover:bg-neutral-100"
                aria-label={t("compare.correction.close_aria")}
              >
                ✕
              </button>
            </div>

            {/* Context Info */}
            <div className="bg-neutral-50 rounded-xl p-3.5 border border-neutral-200 space-y-2 text-xs">
              <div className="flex justify-between items-center">
                <span className="font-semibold text-neutral-500">{t("compare.correction.doc_label")}:</span>
                <span className="font-bold text-neutral-900">
                  {activeResult.metadata[editingMetric.docId]?.company_name || editingMetric.docId} (
                  {activeResult.documents.find((d) => d.doc_id === editingMetric.docId)?.slot.toUpperCase().replace("DOC_", "") || "Doc"}
                  )
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="font-semibold text-neutral-500">{t("compare.correction.metric_label")}:</span>
                <span className="font-mono font-bold text-neutral-900">
                  {METRIC_ROWS.find((r) => r.key === editingMetric.metricKey)?.labelKey
                    ? t(METRIC_ROWS.find((r) => r.key === editingMetric.metricKey)!.labelKey)
                    : editingMetric.metricKey} ({editingMetric.metricKey})
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="font-semibold text-neutral-500">{t("compare.correction.current_val")}:</span>
                <span className="font-mono font-bold text-neutral-800">
                  {formatAmountText(editingMetric.currentVal)}
                  {editingMetric.currentVal?.is_user_corrected && (
                    <span className="ml-1.5 text-[10px] text-amber-800 bg-amber-100 px-1 py-0.5 rounded font-bold">
                      ({t("compare.correction.user_entered")})
                    </span>
                  )}
                </span>
              </div>
              {editingMetric.currentVal?.original_amount !== null &&
                editingMetric.currentVal?.original_amount !== undefined &&
                editingMetric.currentVal?.is_user_corrected && (
                  <div className="flex justify-between items-center text-[11px] text-neutral-500">
                    <span>{t("compare.correction.original_extracted")}:</span>
                    <span className="font-mono">
                      ₹{editingMetric.currentVal.original_amount.toLocaleString()}{" "}
                      {editingMetric.currentVal.unit === "INR_CRORE" ? "Cr" : ""}
                    </span>
                  </div>
                )}
            </div>

            {/* Inputs */}
            <div className="space-y-4 text-xs">
              <div>
                <label htmlFor="corrected-amount-input" className="block font-bold text-neutral-800 mb-1">
                  {t("compare.correction.new_amount_label")} <span className="text-red-500">*</span>
                </label>
                <input
                  id="corrected-amount-input"
                  type="number"
                  step="any"
                  value={correctedAmountInput}
                  onChange={(e) => setCorrectedAmountInput(e.target.value)}
                  placeholder={t("compare.correction.amount_placeholder")}
                  disabled={isSubmittingCorrection}
                  className="w-full px-3.5 py-2.5 bg-white border border-neutral-300 rounded-xl font-mono text-sm text-neutral-900 focus:outline-none focus:ring-2 focus:ring-accent-500"
                  data-testid="corrected-amount-input"
                  autoFocus
                />
                <span className="text-[11px] text-neutral-500 mt-1 block">
                  {editingMetric.metricKey.toUpperCase() === "EPS"
                    ? t("compare.dash.eps_scale_hint")
                    : t("compare.dash.crores_scale_hint")}
                </span>
              </div>

              <div>
                <label htmlFor="correction-reason-input" className="block font-bold text-neutral-800 mb-1">
                  {t("compare.correction.reason_label")}
                </label>
                <input
                  id="correction-reason-input"
                  type="text"
                  value={correctionReasonInput}
                  onChange={(e) => setCorrectionReasonInput(e.target.value)}
                  placeholder={t("compare.correction.reason_placeholder")}
                  disabled={isSubmittingCorrection}
                  className="w-full px-3.5 py-2 bg-white border border-neutral-300 rounded-xl text-xs text-neutral-900 focus:outline-none focus:ring-2 focus:ring-accent-500"
                  data-testid="correction-reason-input"
                />
              </div>

              {/* Educational Notice */}
              <p className="text-[11px] text-neutral-500 bg-neutral-50 p-2.5 rounded-lg border border-neutral-200 leading-relaxed">
                {t("compare.correction.evidence_notice")}
              </p>

              {/* Error Message */}
              {correctionError && (
                <div
                  className="p-3 bg-red-50 text-red-700 text-xs rounded-lg border border-red-200 font-medium"
                  data-testid="correction-error-message"
                >
                  {correctionError}
                </div>
              )}
            </div>

            {/* Modal Actions */}
            <div className="flex items-center justify-end gap-3 pt-2 border-t border-neutral-100">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setEditingMetric(null);
                  setCorrectionError(null);
                }}
                disabled={isSubmittingCorrection}
                className="text-xs font-bold text-neutral-600"
              >
                {t("compare.correction.cancel_btn")}
              </Button>

              <Button
                size="sm"
                onClick={handleApplyCorrection}
                disabled={isSubmittingCorrection || !correctedAmountInput.trim()}
                className="bg-primary-900 text-white text-xs font-bold px-4 shadow-sm"
                data-testid="apply-correction-btn"
              >
                {isSubmittingCorrection ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                    {t("compare.correction.saving")}
                  </>
                ) : (
                  t("compare.correction.save_btn")
                )}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* 8. Interactive Evidence Viewer */}
      {selectedEvidence && (
        <EvidenceViewer
          isOpen={!!selectedEvidence}
          evidence={selectedEvidence}
          document={activeResult.documents.find((d) => d.doc_id === selectedEvidence.doc_id)}
          allDocuments={activeResult.documents}
          candidates={selectedCandidates}
          sessionId={activeResult.session_id}
          sessionToken={sessionToken}
          onClose={() => {
            setSelectedEvidence(null);
            setSelectedCandidates([]);
          }}
          onSelectDocument={(docId) => {
            const doc = activeResult.documents.find((d) => d.doc_id === docId);
            if (doc && selectedEvidence) {
              setSelectedEvidence({
                ...selectedEvidence,
                doc_id: doc.doc_id,
                document_name: doc.original_filename,
              });
            }
          }}
          language={language}
        />
      )}
    </div>
  );
}
