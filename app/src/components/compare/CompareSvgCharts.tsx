import { useState } from "react";
import type { ComparisonDocument, FinancialValue, DocumentMetadata, CompatibilityReport } from "../../lib/compareApi";
import { getTranslation, type SupportedLanguage } from "../../lib/translations";

interface CompareSvgChartsProps {
  documents: ComparisonDocument[];
  financialValues: Record<string, Record<string, FinancialValue>>; // metric_key -> doc_id -> value
  metadata?: Record<string, DocumentMetadata>;
  compatibility?: CompatibilityReport;
  language: SupportedLanguage;
}

type ChartMetric = "revenue" | "pat" | "ebitda" | "debt" | "cash" | "ocf" | "balance_sheet";

export function CompareSvgCharts({
  documents,
  financialValues,
  metadata,
  compatibility,
  language,
}: CompareSvgChartsProps) {
  const [selectedMetric, setSelectedMetric] = useState<ChartMetric>("revenue");
  const t = (key: string) => getTranslation(key, language);

  const formatChartAmount = (val: number, unit?: string, currency?: string, metricKey?: string): string => {
    const keyUpper = (metricKey || "").toUpperCase();
    const isPerShare = keyUpper === "EPS" || keyUpper === "BASIC_EPS" || (unit || "").endsWith("/share");
    const curr = currency || (unit?.startsWith("USD") ? "USD" : unit?.startsWith("EUR") ? "EUR" : unit?.startsWith("GBP") ? "GBP" : "INR");
    const prefix = curr === "INR" ? "₹" : curr === "USD" ? "$" : curr === "EUR" ? "€" : curr === "GBP" ? "£" : `${curr} `;
    if (isPerShare) {
      return `${prefix}${val.toLocaleString()} ${t("compare.unit.per_share")}`.trim();
    }
    const u = (unit || "").toUpperCase();
    let suffix = "";
    if (u === "INR_CRORE" || u === "CRORE") suffix = ` ${t("compare.unit.crore")}`;
    else if (u === "INR_LAKH" || u === "LAKH") suffix = ` ${t("compare.unit.lakh")}`;
    else if (u.includes("THOUSAND")) suffix = ` ${t("compare.unit.thousand")}`;
    else if (u.includes("MILLION")) suffix = ` ${t("compare.unit.million")}`;
    else if (u.includes("UNITS")) suffix = ` ${t("compare.unit.units")}`;
    return `${prefix}${val.toLocaleString()}${suffix}`.trim();
  };

  const getChartStatusLabel = (status?: string): string => {
    if (status === "AMBIGUOUS") return t("compare.matrix.ambiguous");
    if (status === "UNCERTAIN") return t("compare.matrix.uncertain");
    if (status === "EXTRACTION_UNAVAILABLE") return t("compare.matrix.extraction_unavailable");
    return t("compare.matrix.not_disclosed");
  };

  const getMetricData = (key: string) => {
    const keyUpper = key.toUpperCase();
    const keyLower = key.toLowerCase();
    return documents.map((doc) => {
      const meta = metadata?.[doc.doc_id];
      const compName = meta?.company_name || doc.original_filename;
      const periodStr = meta?.financial_year
        ? `${meta.financial_year}${meta.quarter ? ` (${meta.quarter})` : ""}`
        : meta?.reporting_period || "";
      const fVal =
        financialValues[key]?.[doc.doc_id] ||
        financialValues[keyUpper]?.[doc.doc_id] ||
        financialValues[keyLower]?.[doc.doc_id];
      const isReported = fVal && fVal.status === "REPORTED" && fVal.amount !== null && fVal.amount !== undefined;
      return {
        docId: doc.doc_id,
        filename: doc.original_filename,
        companyName: compName,
        period: periodStr,
        slot: doc.slot.toUpperCase().replace("_", " "),
        amount: isReported ? Number(fVal.amount) : null,
        displayAmount: isReported ? (fVal.display_amount || formatChartAmount(Number(fVal.amount), fVal.unit, fVal.currency, keyUpper)) : null,
        unit: fVal?.unit || "INR_CRORE",
        currency: fVal?.currency || meta?.currency || "INR",
        status: fVal?.status || "NOT_DISCLOSED",
      };
    });
  };

  // Chart dimensions
  const width = 640;
  const height = 300;
  const padding = { top: 30, right: 30, bottom: 65, left: 75 };
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;

  // Single metric render logic
  const renderSingleMetricChart = (metricKey: string, metricLabel: string, barColor: string) => {
    const data = getMetricData(metricKey);
    const validAmounts = data.filter((d) => d.amount !== null).map((d) => d.amount as number);

    if (validAmounts.length === 0) {
      return (
        <div className="flex flex-col items-center justify-center h-64 border border-dashed border-neutral-200 rounded-lg p-6 bg-neutral-50/50">
          <p className="text-sm font-medium text-neutral-500">
            {metricLabel}: {t("compare.matrix.not_disclosed")} {t("compare.charts.across_uploaded")}
          </p>
          <p className="text-xs text-neutral-400 mt-1">{t("compare.charts.missing_notice")}</p>
        </div>
      );
    }

    let minVal = Math.min(0, ...validAmounts);
    let maxVal = Math.max(0, ...validAmounts);
    if (minVal === maxVal) {
      maxVal = maxVal > 0 ? maxVal * 1.2 : 100;
    }
    // Add 10% breathing room
    const range = maxVal - minVal;
    maxVal += range * 0.1;
    if (minVal < 0) minVal -= range * 0.1;

    const scaleY = (val: number) => {
      return padding.top + ((maxVal - val) / (maxVal - minVal)) * innerHeight;
    };

    const yZero = scaleY(0);
    const colWidth = innerWidth / data.length;
    const barWidth = Math.min(60, colWidth * 0.6);

    return (
      <div className="w-full overflow-x-auto">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto max-w-2xl mx-auto font-sans">
          {/* Grid lines */}
          <line
            x1={padding.left}
            y1={yZero}
            x2={width - padding.right}
            y2={yZero}
            stroke="#94a3b8"
            strokeWidth="1.5"
          />
          <line
            x1={padding.left}
            y1={padding.top}
            x2={width - padding.right}
            y2={padding.top}
            stroke="#e2e8f0"
            strokeDasharray="3 3"
          />
          <line
            x1={padding.left}
            y1={height - padding.bottom}
            x2={width - padding.right}
            y2={height - padding.bottom}
            stroke="#e2e8f0"
            strokeDasharray="3 3"
          />

          {/* Y Axis labels */}
          <text
            x={padding.left - 8}
            y={padding.top + 4}
            textAnchor="end"
            fontSize="10"
            fill="#64748b"
            fontWeight="bold"
          >
            ₹{maxVal.toFixed(0)} Cr
          </text>
          <text
            x={padding.left - 8}
            y={yZero + 4}
            textAnchor="end"
            fontSize="10"
            fill="#475569"
            fontWeight="bold"
          >
            ₹0
          </text>
          {minVal < 0 && (
            <text
              x={padding.left - 8}
              y={height - padding.bottom + 4}
              textAnchor="end"
              fontSize="10"
              fill="#e11d48"
              fontWeight="bold"
            >
              -₹{Math.abs(minVal).toFixed(0)} Cr
            </text>
          )}

          {/* Bars */}
          {data.map((d, idx) => {
            const xCenter = padding.left + idx * colWidth + colWidth / 2;
            const x = xCenter - barWidth / 2;

            if (d.amount === null) {
              // Honest representation: NEVER 0
              return (
                <g key={d.docId}>
                  <rect
                    tabIndex={0}
                    x={x}
                    y={yZero - 15}
                    width={barWidth}
                    height={30}
                    fill="#f1f5f9"
                    stroke="#cbd5e1"
                    strokeDasharray="4 2"
                    rx={3}
                    role="graphics-symbol"
                    aria-label={`${d.slot} ${d.companyName}: ${metricLabel} ${getChartStatusLabel(d.status)}`}
                    className="transition-all hover:opacity-85 focus:outline-none focus:ring-2 focus:ring-accent-500 focus:ring-offset-1 focus:opacity-85"
                  >
                    <title>{`${d.slot} ${d.companyName}: ${metricLabel} ${getChartStatusLabel(d.status)}`}</title>
                  </rect>
                  <text
                    x={xCenter}
                    y={yZero + 4}
                    textAnchor="middle"
                    fontSize="9"
                    fill="#94a3b8"
                    fontWeight="bold"
                  >
                    {d.status === "AMBIGUOUS" ? "Ambig." : d.status === "UNCERTAIN" ? "?" : "N/A"}
                  </text>
                  <text
                    x={xCenter}
                    y={height - padding.bottom + 18}
                    textAnchor="middle"
                    fontSize="11"
                    fill="#0f172a"
                    fontWeight="bold"
                  >
                    {d.slot}
                  </text>
                  <text
                    x={xCenter}
                    y={height - padding.bottom + 32}
                    textAnchor="middle"
                    fontSize="9"
                    fill="#475569"
                    fontWeight="bold"
                  >
                    {d.companyName.length > 14 ? d.companyName.slice(0, 12) + "…" : d.companyName}
                  </text>
                  {d.period && (
                    <text
                      x={xCenter}
                      y={height - padding.bottom + 44}
                      textAnchor="middle"
                      fontSize="8"
                      fill="#64748b"
                    >
                      {d.period}
                    </text>
                  )}
                </g>
              );
            }

            const val = d.amount;
            const isNegative = val < 0;
            const y = isNegative ? yZero : scaleY(val);
            const barH = isNegative ? scaleY(val) - yZero : yZero - scaleY(val);
            const fill = isNegative ? "#f43f5e" : barColor;

            return (
              <g key={d.docId}>
                <rect
                  tabIndex={0}
                  x={x}
                  y={y}
                  width={barWidth}
                  height={Math.max(2, barH)}
                  fill={fill}
                  rx={2}
                  role="graphics-symbol"
                  aria-label={`${d.slot} ${d.companyName}: ${metricLabel} ${d.displayAmount || formatChartAmount(val, d.unit, d.currency, metricKey)}`}
                  className="transition-all hover:opacity-85 focus:outline-none focus:ring-2 focus:ring-accent-500 focus:ring-offset-1 focus:opacity-85"
                >
                  <title>{`${d.slot} ${d.companyName}: ${metricLabel} ${d.displayAmount || formatChartAmount(val, d.unit, d.currency, metricKey)}`}</title>
                </rect>
                {/* Value label */}
                <text
                  x={xCenter}
                  y={isNegative ? y + barH + 12 : y - 6}
                  textAnchor="middle"
                  fontSize="11"
                  fill={isNegative ? "#be123c" : "#0f172a"}
                  fontWeight="bold"
                >
                  {d.displayAmount || formatChartAmount(val, d.unit, d.currency, metricKey)}
                </text>
                {/* X axis labels */}
                <text
                  x={xCenter}
                  y={height - padding.bottom + 18}
                  textAnchor="middle"
                  fontSize="11"
                  fill="#0f172a"
                  fontWeight="bold"
                >
                  {d.slot}
                </text>
                <text
                  x={xCenter}
                  y={height - padding.bottom + 32}
                  textAnchor="middle"
                  fontSize="9"
                  fill="#475569"
                  fontWeight="bold"
                >
                  {d.companyName.length > 14 ? d.companyName.slice(0, 12) + "…" : d.companyName}
                </text>
                {d.period && (
                  <text
                    x={xCenter}
                    y={height - padding.bottom + 44}
                    textAnchor="middle"
                    fontSize="8"
                    fill="#64748b"
                  >
                    {d.period}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>
    );
  };

  // Grouped Balance Sheet chart (Assets vs Liabilities)
  const renderBalanceSheetChart = () => {
    const assetsData = getMetricData("TOTAL_ASSETS");
    const liabilitiesData = getMetricData("TOTAL_LIABILITIES");

    const validAmounts = [
      ...assetsData.map((d) => d.amount),
      ...liabilitiesData.map((d) => d.amount),
    ].filter((v): v is number => v !== null && v !== undefined);

    if (validAmounts.length === 0) {
      return (
        <div className="flex flex-col items-center justify-center h-64 border border-dashed border-neutral-200 rounded-lg p-6 bg-neutral-50/50">
          <p className="text-sm font-medium text-neutral-500">
            {t("compare.charts.balance_sheet")}: {t("compare.matrix.not_disclosed")} {t("compare.charts.across_filings")}
          </p>
        </div>
      );
    }

    let maxVal = Math.max(0, ...validAmounts) * 1.15;
    if (maxVal === 0) maxVal = 100;

    const scaleY = (val: number) => padding.top + ((maxVal - val) / maxVal) * innerHeight;
    const yZero = scaleY(0);
    const colWidth = innerWidth / documents.length;
    const groupBarWidth = Math.min(26, colWidth * 0.35);

    return (
      <div className="w-full overflow-x-auto">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto max-w-2xl mx-auto font-sans">
          {/* Grid lines */}
          <line
            x1={padding.left}
            y1={yZero}
            x2={width - padding.right}
            y2={yZero}
            stroke="#94a3b8"
            strokeWidth="1.5"
          />
          <line
            x1={padding.left}
            y1={padding.top}
            x2={width - padding.right}
            y2={padding.top}
            stroke="#e2e8f0"
            strokeDasharray="3 3"
          />

          {/* Y Axis labels */}
          <text
            x={padding.left - 8}
            y={padding.top + 4}
            textAnchor="end"
            fontSize="10"
            fill="#64748b"
            fontWeight="bold"
          >
            ₹{maxVal.toFixed(0)} Cr
          </text>
          <text
            x={padding.left - 8}
            y={yZero + 4}
            textAnchor="end"
            fontSize="10"
            fill="#475569"
            fontWeight="bold"
          >
            ₹0
          </text>

          {documents.map((doc, idx) => {
            const xCenter = padding.left + idx * colWidth + colWidth / 2;
            const assetItem = assetsData[idx];
            const liabItem = liabilitiesData[idx];
            const assetAmt = assetItem?.amount;
            const liabAmt = liabItem?.amount;
            const meta = metadata?.[doc.doc_id];
            const compName = meta?.company_name || doc.original_filename;
            const periodStr = meta?.financial_year
              ? `${meta.financial_year}${meta.quarter ? ` (${meta.quarter})` : ""}`
              : meta?.reporting_period || "";

            const xAsset = xCenter - groupBarWidth - 2;
            const xLiab = xCenter + 2;

            return (
              <g key={doc.doc_id}>
                {/* Asset Bar */}
                {assetAmt !== null && assetAmt !== undefined ? (
                  <rect
                    tabIndex={0}
                    x={xAsset}
                    y={scaleY(assetAmt)}
                    width={groupBarWidth}
                    height={Math.max(2, yZero - scaleY(assetAmt))}
                    fill="#2563eb" // Blue for Assets
                    rx={2}
                    role="graphics-symbol"
                    aria-label={`${doc.slot.toUpperCase().replace("_", " ")} ${compName}: ${t("compare.metric.assets")} ${assetItem?.displayAmount || formatChartAmount(assetAmt, assetItem?.unit, assetItem?.currency, "TOTAL_ASSETS")}`}
                    className="transition-all hover:opacity-85 focus:outline-none focus:ring-2 focus:ring-accent-500 focus:ring-offset-1 focus:opacity-85"
                  >
                    <title>{`${doc.slot.toUpperCase().replace("_", " ")} ${compName}: ${t("compare.metric.assets")} ${assetItem?.displayAmount || formatChartAmount(assetAmt, assetItem?.unit, assetItem?.currency, "TOTAL_ASSETS")}`}</title>
                  </rect>
                ) : (
                  <rect
                    tabIndex={0}
                    x={xAsset}
                    y={yZero - 12}
                    width={groupBarWidth}
                    height={24}
                    fill="#f1f5f9"
                    stroke="#cbd5e1"
                    strokeDasharray="2 2"
                    rx={2}
                    role="graphics-symbol"
                    aria-label={`${doc.slot.toUpperCase().replace("_", " ")} ${compName}: ${t("compare.metric.assets")} ${getChartStatusLabel(assetItem?.status)}`}
                    className="transition-all hover:opacity-85 focus:outline-none focus:ring-2 focus:ring-accent-500 focus:ring-offset-1 focus:opacity-85"
                  >
                    <title>{`${doc.slot.toUpperCase().replace("_", " ")} ${compName}: ${t("compare.metric.assets")} ${getChartStatusLabel(assetItem?.status)}`}</title>
                  </rect>
                )}

                {/* Liability Bar */}
                {liabAmt !== null && liabAmt !== undefined ? (
                  <rect
                    tabIndex={0}
                    x={xLiab}
                    y={scaleY(liabAmt)}
                    width={groupBarWidth}
                    height={Math.max(2, yZero - scaleY(liabAmt))}
                    fill="#f97316" // Orange for Liabilities
                    rx={2}
                    role="graphics-symbol"
                    aria-label={`${doc.slot.toUpperCase().replace("_", " ")} ${compName}: ${t("compare.metric.liabilities")} ${liabItem?.displayAmount || formatChartAmount(liabAmt, liabItem?.unit, liabItem?.currency, "TOTAL_LIABILITIES")}`}
                    className="transition-all hover:opacity-85 focus:outline-none focus:ring-2 focus:ring-accent-500 focus:ring-offset-1 focus:opacity-85"
                  >
                    <title>{`${doc.slot.toUpperCase().replace("_", " ")} ${compName}: ${t("compare.metric.liabilities")} ${liabItem?.displayAmount || formatChartAmount(liabAmt, liabItem?.unit, liabItem?.currency, "TOTAL_LIABILITIES")}`}</title>
                  </rect>
                ) : (
                  <rect
                    tabIndex={0}
                    x={xLiab}
                    y={yZero - 12}
                    width={groupBarWidth}
                    height={24}
                    fill="#f1f5f9"
                    stroke="#cbd5e1"
                    strokeDasharray="2 2"
                    rx={2}
                    role="graphics-symbol"
                    aria-label={`${doc.slot.toUpperCase().replace("_", " ")} ${compName}: ${t("compare.metric.liabilities")} ${getChartStatusLabel(liabItem?.status)}`}
                    className="transition-all hover:opacity-85 focus:outline-none focus:ring-2 focus:ring-accent-500 focus:ring-offset-1 focus:opacity-85"
                  >
                    <title>{`${doc.slot.toUpperCase().replace("_", " ")} ${compName}: ${t("compare.metric.liabilities")} ${getChartStatusLabel(liabItem?.status)}`}</title>
                  </rect>
                )}

                {/* Slot label */}
                <text
                  x={xCenter}
                  y={height - padding.bottom + 18}
                  textAnchor="middle"
                  fontSize="11"
                  fill="#0f172a"
                  fontWeight="bold"
                >
                  {doc.slot.toUpperCase().replace("_", " ")}
                </text>
                <text
                  x={xCenter}
                  y={height - padding.bottom + 32}
                  textAnchor="middle"
                  fontSize="9"
                  fill="#475569"
                  fontWeight="bold"
                >
                  {compName.length > 14 ? compName.slice(0, 12) + "…" : compName}
                </text>
                {periodStr && (
                  <text
                    x={xCenter}
                    y={height - padding.bottom + 44}
                    textAnchor="middle"
                    fontSize="8"
                    fill="#64748b"
                  >
                    {periodStr}
                  </text>
                )}
              </g>
            );
          })}
        </svg>

        {/* Legend */}
        <div className="flex items-center justify-center gap-6 mt-4 text-xs font-semibold">
          <div className="flex items-center gap-2">
            <span className="w-3.5 h-3.5 rounded bg-blue-600 inline-block" />
            <span className="text-neutral-700">{t("compare.metric.assets")}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3.5 h-3.5 rounded bg-orange-500 inline-block" />
            <span className="text-neutral-700">{t("compare.metric.liabilities")}</span>
          </div>
        </div>
      </div>
    );
  };

  // Check if any compatibility finding targets current chart metric
  const currentMetricKey =
    selectedMetric === "revenue"
      ? "REVENUE"
      : selectedMetric === "pat"
      ? "PAT"
      : selectedMetric === "ebitda"
      ? "EBITDA"
      : selectedMetric === "debt"
      ? "TOTAL_DEBT"
      : selectedMetric === "cash"
      ? "CASH_EQUIVALENTS"
      : selectedMetric === "ocf"
      ? "OPERATING_CASH_FLOW"
      : "BALANCE_SHEET";

  const relevantFinding = compatibility?.findings.find(
    (f) =>
      f.relevant_fields?.some(
        (rf) =>
          rf.toUpperCase() === currentMetricKey ||
          (currentMetricKey === "BALANCE_SHEET" && (rf.toUpperCase() === "TOTAL_ASSETS" || rf.toUpperCase() === "TOTAL_LIABILITIES"))
      ) ||
      (f.code && (f.code.includes("CURRENCY") || f.code.includes("SCALE") || f.code.includes("PERIOD") || f.code.includes("SCOPE")))
  );

  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-6 shadow-sm space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-neutral-100 pb-4">
        <div>
          <h3 className="text-base font-bold text-neutral-900">{t("compare.charts.title")}</h3>
          <p className="text-xs text-neutral-500 mt-0.5">{t("compare.charts.missing_notice")}</p>
        </div>

        {/* Metric Selector Buttons */}
        <div className="flex flex-wrap rounded-lg bg-neutral-100 p-1 text-xs font-semibold gap-1">
          <button
            onClick={() => setSelectedMetric("revenue")}
            className={`px-2.5 py-1.5 rounded-md transition-colors ${
              selectedMetric === "revenue"
                ? "bg-white text-neutral-900 shadow-xs font-bold"
                : "text-neutral-600 hover:text-neutral-900"
            }`}
          >
            {t("compare.metric.revenue")}
          </button>
          <button
            onClick={() => setSelectedMetric("pat")}
            className={`px-2.5 py-1.5 rounded-md transition-colors ${
              selectedMetric === "pat"
                ? "bg-white text-neutral-900 shadow-xs font-bold"
                : "text-neutral-600 hover:text-neutral-900"
            }`}
          >
            {t("compare.metric.pat")}
          </button>
          <button
            onClick={() => setSelectedMetric("ebitda")}
            className={`px-2.5 py-1.5 rounded-md transition-colors ${
              selectedMetric === "ebitda"
                ? "bg-white text-neutral-900 shadow-xs font-bold"
                : "text-neutral-600 hover:text-neutral-900"
            }`}
          >
            {t("compare.metric.ebitda")}
          </button>
          <button
            onClick={() => setSelectedMetric("debt")}
            className={`px-2.5 py-1.5 rounded-md transition-colors ${
              selectedMetric === "debt"
                ? "bg-white text-neutral-900 shadow-xs font-bold"
                : "text-neutral-600 hover:text-neutral-900"
            }`}
          >
            {t("compare.charts.debt_trend")}
          </button>
          <button
            onClick={() => setSelectedMetric("cash")}
            className={`px-2.5 py-1.5 rounded-md transition-colors ${
              selectedMetric === "cash"
                ? "bg-white text-neutral-900 shadow-xs font-bold"
                : "text-neutral-600 hover:text-neutral-900"
            }`}
          >
            {t("compare.charts.cash_trend")}
          </button>
          <button
            onClick={() => setSelectedMetric("ocf")}
            className={`px-2.5 py-1.5 rounded-md transition-colors ${
              selectedMetric === "ocf"
                ? "bg-white text-neutral-900 shadow-xs font-bold"
                : "text-neutral-600 hover:text-neutral-900"
            }`}
          >
            {t("compare.charts.ocf_trend")}
          </button>
          <button
            onClick={() => setSelectedMetric("balance_sheet")}
            className={`px-2.5 py-1.5 rounded-md transition-colors ${
              selectedMetric === "balance_sheet"
                ? "bg-white text-neutral-900 shadow-xs font-bold"
                : "text-neutral-600 hover:text-neutral-900"
            }`}
          >
            {t("compare.charts.balance_sheet")}
          </button>
        </div>
      </div>

      {/* Compatibility Finding Notice for Chart if present */}
      {relevantFinding && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-800 flex items-start gap-2">
          <span className="font-bold shrink-0">⚠ {t("compare.charts.compat_notice")}</span>
          <span>({relevantFinding.title}: {relevantFinding.description})</span>
        </div>
      )}

      {/* Chart Output */}
      <div className="py-2">
        {selectedMetric === "revenue" &&
          renderSingleMetricChart("REVENUE", t("compare.metric.revenue"), "#0284c7")}
        {selectedMetric === "pat" &&
          renderSingleMetricChart("PAT", t("compare.metric.pat"), "#0d9488")}
        {selectedMetric === "ebitda" &&
          renderSingleMetricChart("EBITDA", t("compare.metric.ebitda"), "#6366f1")}
        {selectedMetric === "debt" &&
          renderSingleMetricChart("TOTAL_DEBT", t("compare.charts.debt_trend"), "#d97706")}
        {selectedMetric === "cash" &&
          renderSingleMetricChart("CASH_EQUIVALENTS", t("compare.charts.cash_trend"), "#059669")}
        {selectedMetric === "ocf" &&
          renderSingleMetricChart("OPERATING_CASH_FLOW", t("compare.charts.ocf_trend"), "#7c3aed")}
        {selectedMetric === "balance_sheet" && renderBalanceSheetChart()}
      </div>
    </div>
  );
}
