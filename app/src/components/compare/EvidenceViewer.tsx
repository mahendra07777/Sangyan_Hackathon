import { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import {
  X,
  FileText,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  AlertTriangle,
  Info,
  Loader2,
  FileSpreadsheet,
} from "lucide-react";
import { Badge } from "../ui/Badge";
import {
  fetchEvidencePageBlob,
  getEvidenceContext,
  type EvidenceReference,
  type ComparisonDocument,
  type DocumentExtractionResult,
} from "../../lib/compareApi";
import { getTranslation, type SupportedLanguage } from "../../lib/translations";

export interface CandidateInfo {
  candidate_id: string;
  raw_label: string;
  raw_text_value: string;
  normalized_amount?: number | null;
  statement_type?: string;
  is_selected?: boolean;
  resolution_reason?: string;
  evidence: EvidenceReference;
}

interface EvidenceViewerProps {
  evidence: EvidenceReference | null;
  document?: ComparisonDocument;
  allDocuments?: ComparisonDocument[];
  candidates?: CandidateInfo[];
  sessionId: string;
  sessionToken: string;
  isOpen: boolean;
  onClose: () => void;
  onSelectDocument?: (docId: string) => void;
  language: SupportedLanguage;
}

export function EvidenceViewer({
  evidence,
  document,
  allDocuments = [],
  candidates = [],
  sessionId,
  sessionToken,
  isOpen,
  onClose,
  onSelectDocument,
  language,
}: EvidenceViewerProps) {
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageImageUrl, setPageImageUrl] = useState<string | null>(null);
  const [isLoadingPage, setIsLoadingPage] = useState<boolean>(false);
  const [pageError, setPageError] = useState<string | null>(null);

  // Zoom & Pan
  const [zoomLevel, setZoomLevel] = useState<number>(1);

  // Structured context for spreadsheets and DOCX
  const [extractionContext, setExtractionContext] = useState<DocumentExtractionResult | null>(null);
  const [isLoadingContext, setIsLoadingContext] = useState<boolean>(false);
  const [selectedSheet, setSelectedSheet] = useState<string | null>(null);

  const t = (key: string) => getTranslation(key, language);

  const modalRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const previousActiveElement = useRef<HTMLElement | null>(null);

  // Reset or initialize page when evidence changes
  useEffect(() => {
    if (evidence) {
      const targetPage = evidence.page_number && evidence.page_number > 0 ? evidence.page_number : 1;
      setCurrentPage(targetPage);
      setSelectedSheet(evidence.sheet_name || null);
    }
  }, [evidence]);

  // Handle escape key, focus trapping, focus restoration, and page navigation
  useEffect(() => {
    if (isOpen) {
      previousActiveElement.current = (typeof window !== "undefined" ? window.document.activeElement : null) as HTMLElement | null;

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
          return;
        }

        if (e.key === "ArrowLeft" && currentPage > 1) {
          setCurrentPage((p) => p - 1);
        }
        if (e.key === "ArrowRight" && document?.page_count && currentPage < document.page_count) {
          setCurrentPage((p) => p + 1);
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
  }, [isOpen, currentPage, document?.page_count, onClose]);

  // Fetch page image for PDF / Images
  useEffect(() => {
    if (!isOpen || !sessionId || !sessionToken || !evidence) return;

    const format = document?.file_format;
    const isRenderable =
      format === "PDF_DIGITAL" ||
      format === "PDF_SCANNED" ||
      format === "IMAGE_PNG" ||
      format === "IMAGE_JPG" ||
      format === "IMAGE_JPEG";

    if (!isRenderable) {
      setPageImageUrl(null);
      return;
    }

    let active = true;
    setIsLoadingPage(true);
    setPageError(null);

    fetchEvidencePageBlob(sessionId, sessionToken, evidence.doc_id, currentPage)
      .then((blob) => {
        if (!active) return;
        const url = URL.createObjectURL(blob);
        setPageImageUrl(url);
      })
      .catch((err) => {
        if (!active) return;
        setPageError(err.message || "Could not load document page preview.");
        setPageImageUrl(null);
      })
      .finally(() => {
        if (active) setIsLoadingPage(false);
      });

    return () => {
      active = false;
      if (pageImageUrl) URL.revokeObjectURL(pageImageUrl);
    };
  }, [isOpen, sessionId, sessionToken, evidence?.doc_id, currentPage, document?.file_format]);

  // Fetch structured context for spreadsheets or DOCX
  useEffect(() => {
    if (!isOpen || !sessionId || !sessionToken || !evidence) return;

    const format = document?.file_format;
    const needsContext =
      format === "XLSX" || format === "XLS" || format === "DOCX" || !pageImageUrl;

    if (!needsContext) return;

    let active = true;
    setIsLoadingContext(true);

    getEvidenceContext(sessionId, sessionToken, evidence.doc_id)
      .then((res) => {
        if (!active) return;
        setExtractionContext(res);
        if (!selectedSheet && res.sheet_names && res.sheet_names.length > 0) {
          setSelectedSheet(res.sheet_names[0]);
        }
      })
      .catch(() => {
        // Context fetch optional fallback
      })
      .finally(() => {
        if (active) setIsLoadingContext(false);
      });

    return () => {
      active = false;
    };
  }, [isOpen, sessionId, sessionToken, evidence?.doc_id, document?.file_format, selectedSheet]);

  if (!isOpen || !evidence) return null;

  const totalPages = document?.page_count || 1;
  const format = document?.file_format || "PDF_DIGITAL";
  const isImageOrPdf =
    format === "PDF_DIGITAL" ||
    format === "PDF_SCANNED" ||
    format === "IMAGE_PNG" ||
    format === "IMAGE_JPG" ||
    format === "IMAGE_JPEG";

  // Bounding box overlay calculation
  // normalized bbox: [x0, y0, x1, y1] where 0.0 <= coord <= 1.0
  const bbox = evidence.bounding_box;
  const hasBbox = Array.isArray(bbox) && bbox.length === 4;

  // Filter matching table for spreadsheets if available
  const matchingTable = extractionContext?.tables.find((t) => {
    if (evidence.sheet_name && t.sheet_name) {
      return t.sheet_name.toLowerCase() === evidence.sheet_name.toLowerCase();
    }
    if (selectedSheet && t.sheet_name) {
      return t.sheet_name.toLowerCase() === selectedSheet.toLowerCase();
    }
    return true;
  });

  const modalContent = (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-3 sm:p-6 bg-black/60 backdrop-blur-xs font-sans animate-fade-in" role="dialog" aria-modal="true" aria-labelledby="evidence-viewer-title">
      <div ref={modalRef} className="bg-white rounded-2xl w-full max-w-6xl h-[92vh] shadow-2xl border border-neutral-300 flex flex-col overflow-hidden">
        {/* 1. Header Bar */}
        <div className="h-14 border-b border-neutral-200 bg-neutral-50/90 px-4 sm:px-6 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3 overflow-hidden">
            <span className="w-7 h-7 rounded-md bg-neutral-900 text-white font-extrabold text-xs flex items-center justify-center shrink-0">
              {document?.slot.toUpperCase().replace("DOC_", "") || "A"}
            </span>

            <div className="truncate">
              <div className="flex items-center gap-2">
                <h3 id="evidence-viewer-title" className="text-xs sm:text-sm font-extrabold text-neutral-900 truncate max-w-sm">
                  {evidence.document_name}
                </h3>
                <span className="text-[10px] font-bold font-mono px-2 py-0.5 rounded bg-neutral-200 text-neutral-800">
                  {format}
                </span>
                {document?.is_scanned && (
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-amber-100 text-amber-800 border border-amber-200">
                    {t("compare.evidence.scanned_badge")}
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {allDocuments.length > 1 && onSelectDocument && (
              <div className="hidden sm:flex items-center gap-1 bg-neutral-200/80 p-1 rounded-lg text-xs font-semibold mr-2">
                {allDocuments.map((d) => (
                  <button
                    key={d.doc_id}
                    onClick={() => onSelectDocument(d.doc_id)}
                    className={`px-2 py-1 rounded text-[11px] font-bold transition-colors ${
                      d.doc_id === evidence.doc_id
                        ? "bg-white text-neutral-900 shadow-2xs"
                        : "text-neutral-600 hover:text-neutral-900"
                    }`}
                  >
                    Doc {d.slot.toUpperCase().replace("DOC_", "")}
                  </button>
                ))}
              </div>
            )}

            <button
              ref={closeButtonRef}
              onClick={onClose}
              className="w-8 h-8 rounded-lg hover:bg-neutral-200 text-neutral-500 hover:text-neutral-900 flex items-center justify-center transition-colors focus:outline-none focus:ring-2 focus:ring-accent-500"
              title={t("compare.evidence.close")}
              aria-label={t("compare.evidence.close")}
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* 2. Format Notice Banners */}
        {format === "PDF_SCANNED" && (
          <div className="bg-amber-50 border-b border-amber-200 px-4 py-2 flex items-center gap-2 text-xs text-amber-800 font-medium">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
            <span>{t("compare.evidence.scanned_notice")}</span>
          </div>
        )}
        {(format === "IMAGE_PNG" || format === "IMAGE_JPG" || format === "IMAGE_JPEG") && (
          <div className="bg-neutral-100 border-b border-neutral-200 px-4 py-2 flex items-center gap-2 text-xs text-neutral-700 font-medium">
            <Info className="w-4 h-4 text-neutral-500 shrink-0" />
            <span>{t("compare.evidence.image_notice")}</span>
          </div>
        )}
        {(format === "XLSX" || format === "XLS") && (
          <div className="bg-emerald-50 border-b border-emerald-200 px-4 py-2 flex items-center gap-2 text-xs text-emerald-800 font-medium">
            <FileSpreadsheet className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{t("compare.evidence.spreadsheet_notice")}</span>
          </div>
        )}
        {format === "DOCX" && (
          <div className="bg-blue-50 border-b border-blue-200 px-4 py-2 flex items-center gap-2 text-xs text-blue-800 font-medium">
            <FileText className="w-4 h-4 text-blue-600 shrink-0" />
            <span>{t("compare.evidence.docx_notice")}</span>
          </div>
        )}

        {/* 3. Main Workspace: Split into Document Preview (left) and Traceability Details (right) */}
        <div className="flex-1 flex flex-col lg:flex-row overflow-hidden">
          {/* LEFT: Document Preview Canvas */}
          <div className="flex-1 bg-neutral-900 relative flex flex-col overflow-hidden">
            {/* Page Navigation & Zoom Toolbar (for PDF and images) */}
            {isImageOrPdf && (
              <div className="h-10 bg-neutral-800 border-b border-neutral-700 px-4 flex items-center justify-between text-neutral-200 text-xs shrink-0 select-none">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                    disabled={currentPage <= 1 || isLoadingPage}
                    className="p-1 rounded hover:bg-neutral-700 disabled:opacity-40"
                    title={t("compare.evidence.prev_page")}
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>

                  <span className="font-mono text-xs">
                    {t("compare.evidence.page")} {currentPage} {t("compare.evidence.of")} {totalPages}
                  </span>

                  <button
                    onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                    disabled={currentPage >= totalPages || isLoadingPage}
                    className="p-1 rounded hover:bg-neutral-700 disabled:opacity-40"
                    title={t("compare.evidence.next_page")}
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setZoomLevel((z) => Math.max(0.6, z - 0.2))}
                    className="p-1 rounded hover:bg-neutral-700"
                    title={t("compare.evidence.zoom_out")}
                  >
                    <ZoomOut className="w-4 h-4" />
                  </button>
                  <span className="font-mono text-[11px] w-12 text-center">
                    {Math.round(zoomLevel * 100)}%
                  </span>
                  <button
                    onClick={() => setZoomLevel((z) => Math.min(2.5, z + 0.2))}
                    className="p-1 rounded hover:bg-neutral-700"
                    title={t("compare.evidence.zoom_in")}
                  >
                    <ZoomIn className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => setZoomLevel(1)}
                    className="p-1 rounded hover:bg-neutral-700 text-[10px] font-bold"
                    title={t("compare.evidence.zoom_fit")}
                  >
                    {t("compare.evidence.reset_zoom")}
                  </button>
                </div>
              </div>
            )}

            {/* Document Render Area */}
            <div className="flex-1 overflow-auto p-4 flex items-center justify-center bg-neutral-950/80">
              {isLoadingPage && (
                <div className="flex flex-col items-center gap-3 text-neutral-400 text-xs">
                  <Loader2 className="w-6 h-6 animate-spin text-accent-500" />
                  <span>{t("compare.evidence.loading_page")}</span>
                </div>
              )}

              {pageError && (
                <div className="p-4 bg-error-950/80 border border-error-800 rounded-lg text-error-200 text-xs max-w-md text-center">
                  <p className="font-bold">{t("compare.evidence.page_err_title")}</p>
                  <p className="text-neutral-400 mt-1">{pageError}</p>
                </div>
              )}

              {/* RENDERED IMAGE OR PDF PAGE */}
              {pageImageUrl && !isLoadingPage && (
                <div
                  className="relative inline-block transition-transform duration-200 shadow-2xl bg-white"
                  style={{ transform: `scale(${zoomLevel})`, transformOrigin: "center center" }}
                >
                  <img
                    src={pageImageUrl}
                    alt={`Document page ${currentPage}`}
                    className="max-h-[75vh] w-auto object-contain block select-none pointer-events-none"
                  />

                  {/* High-Precision Source Bounding Box Highlight Overlay */}
                  {hasBbox && evidence.page_number === currentPage && (
                    <div
                      className="absolute border-2 border-amber-500 bg-amber-400/25 rounded-xs transition-all pointer-events-none shadow-sm animate-pulse"
                      style={{
                        left: `${bbox[0] * 100}%`,
                        top: `${bbox[1] * 100}%`,
                        width: `${(bbox[2] - bbox[0]) * 100}%`,
                        height: `${(bbox[3] - bbox[1]) * 100}%`,
                      }}
                    >
                      <span className="absolute -top-5 left-0 bg-amber-500 text-neutral-900 font-extrabold text-[9px] px-1.5 py-0.5 rounded shadow">
                        {t("compare.evidence.cited_excerpt_badge")}
                      </span>
                    </div>
                  )}
                </div>
              )}

              {/* SPREADSHEET TABLE VIEWER (XLSX, XLS) */}
              {(format === "XLSX" || format === "XLS") && (
                <div className="w-full h-full bg-white rounded-xl p-5 overflow-auto text-neutral-900 space-y-4">
                  {/* Sheet Selector Tabs */}
                  {extractionContext?.sheet_names && extractionContext.sheet_names.length > 0 && (
                    <div className="flex items-center gap-2 border-b border-neutral-200 pb-2 overflow-x-auto">
                      <span className="text-xs font-bold text-neutral-500 uppercase tracking-wider mr-2">
                        {t("compare.evidence.sheet")}:
                      </span>
                      {extractionContext.sheet_names.map((s) => (
                        <button
                          key={s}
                          onClick={() => setSelectedSheet(s)}
                          className={`px-3 py-1 rounded text-xs font-bold transition-colors ${
                            selectedSheet === s
                              ? "bg-emerald-700 text-white shadow-2xs"
                              : "bg-neutral-100 text-neutral-700 hover:bg-neutral-200"
                          }`}
                        >
                          {s}
                        </button>
                      ))}
                    </div>
                  )}

                  {/* Render Table Cells */}
                  {matchingTable ? (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between text-xs text-neutral-600">
                        <span className="font-bold">
                          {t("compare.evidence.table_info_prefix")} {matchingTable.sheet_name || matchingTable.table_id} ({matchingTable.num_rows} {t("compare.evidence.rows_label")} × {matchingTable.num_cols} {t("compare.evidence.cols_label")})
                        </span>
                        {evidence.cell_range && (
                          <span className="font-mono font-bold text-emerald-800 bg-emerald-100 px-2.5 py-0.5 rounded">
                            {t("compare.evidence.target_label")} {evidence.cell_range}
                          </span>
                        )}
                      </div>

                      <div className="overflow-x-auto border border-neutral-200 rounded-lg max-h-[50vh]">
                        <table className="w-full text-left border-collapse text-xs font-sans">
                          <thead>
                            <tr className="bg-neutral-100 border-b border-neutral-200 text-neutral-700 font-bold">
                              <th className="py-2 px-3 border-r border-neutral-200 w-12 text-center text-[10px] text-neutral-400">
                                #
                              </th>
                              {matchingTable.headers.map((h, i) => (
                                <th key={i} className="py-2 px-3 border-r border-neutral-200 truncate max-w-[180px]">
                                  {h || `Col ${i + 1}`}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-neutral-100">
                            {matchingTable.rows.slice(0, 50).map((row, rIdx) => {
                              const isCitedRow = evidence.cell_range?.includes(`Row ${rIdx + 1}`);
                              return (
                                <tr
                                  key={rIdx}
                                  className={isCitedRow ? "bg-amber-100 font-semibold" : "hover:bg-neutral-50"}
                                >
                                  <td className="py-1.5 px-3 border-r border-neutral-200 text-center font-mono text-[10px] text-neutral-400">
                                    {rIdx + 1}
                                  </td>
                                  {row.map((cellVal, cIdx) => (
                                    <td
                                      key={cIdx}
                                      className="py-1.5 px-3 border-r border-neutral-200 truncate max-w-[200px]"
                                    >
                                      {cellVal || "—"}
                                    </td>
                                  ))}
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ) : (
                    <div className="p-8 text-center text-neutral-400 text-xs">
                      {isLoadingContext ? t("compare.evidence.loading_cells") : t("compare.evidence.no_tables_found")}
                    </div>
                  )}
                </div>
              )}

              {/* DOCX STRUCTURAL VIEWER */}
              {format === "DOCX" && (
                <div className="w-full h-full bg-white rounded-xl p-6 overflow-auto text-neutral-900 space-y-4">
                  <div className="border-b border-neutral-200 pb-3">
                    <span className="text-xs font-bold text-blue-700 uppercase tracking-widest">
                      {t("compare.evidence.structural_ref")}
                    </span>
                    <h4 className="text-sm font-bold text-neutral-900 mt-1">
                      {evidence.structural_ref || t("compare.evidence.docx_fallback_title")}
                    </h4>
                  </div>

                  <div className="bg-neutral-50 p-4 rounded-xl border border-neutral-200 font-serif leading-relaxed text-sm text-neutral-800">
                    &ldquo;{evidence.verbatim_snippet}&rdquo;
                  </div>

                  {extractionContext && extractionContext.text_blocks.length > 0 && (
                    <div className="space-y-2 pt-2">
                      <span className="text-[11px] font-bold text-neutral-500 uppercase tracking-wider block">
                        {t("compare.evidence.surrounding_blocks")}
                      </span>
                      <div className="space-y-2 max-h-[40vh] overflow-auto pr-2">
                        {extractionContext.text_blocks.slice(0, 10).map((block) => (
                          <div
                            key={block.block_id}
                            className={`p-3 rounded-lg text-xs border ${
                              block.text.includes(evidence.verbatim_snippet.slice(0, 30))
                                ? "border-amber-400 bg-amber-50 font-medium"
                                : "border-neutral-200 bg-white"
                            }`}
                          >
                            <span className="font-mono text-[10px] text-neutral-400 block mb-1">
                              {block.structural_ref}
                            </span>
                            <p className="text-neutral-700">{block.text}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* RIGHT: Traceability & Evidence Meta Panel */}
          <div className="w-full lg:w-96 border-t lg:border-t-0 lg:border-l border-neutral-200 bg-white p-5 overflow-y-auto space-y-5 shrink-0 text-xs">
            {/* Source Location Callouts */}
            <div className="space-y-3">
              <span className="text-[11px] font-bold text-accent-700 uppercase tracking-widest block">
                {t("compare.evidence.location_context")}
              </span>

              <div className="space-y-2 bg-neutral-50 p-3.5 rounded-xl border border-neutral-200">
                <div className="flex justify-between py-1 border-b border-neutral-200/60">
                  <span className="font-semibold text-neutral-500">{t("compare.evidence.doc_label")}</span>
                  <span className="font-bold text-neutral-900 text-right truncate max-w-[180px]">
                    {evidence.document_name}
                  </span>
                </div>

                {evidence.page_number && (
                  <div className="flex justify-between py-1 border-b border-neutral-200/60">
                    <span className="font-semibold text-neutral-500">{t("compare.evidence.page")}:</span>
                    <span className="font-bold text-neutral-900 font-mono">
                      Page {evidence.page_number}
                    </span>
                  </div>
                )}

                {evidence.sheet_name && (
                  <div className="flex justify-between py-1 border-b border-neutral-200/60">
                    <span className="font-semibold text-neutral-500">{t("compare.evidence.sheet")}:</span>
                    <span className="font-bold text-neutral-900 font-mono">
                      {evidence.sheet_name}
                    </span>
                  </div>
                )}

                {evidence.cell_range && (
                  <div className="flex justify-between py-1 border-b border-neutral-200/60">
                    <span className="font-semibold text-neutral-500">{t("compare.evidence.cell")}:</span>
                    <span className="font-bold text-neutral-900 font-mono text-emerald-800">
                      {evidence.cell_range}
                    </span>
                  </div>
                )}

                {evidence.structural_ref && (
                  <div className="flex justify-between py-1 border-b border-neutral-200/60">
                    <span className="font-semibold text-neutral-500">{t("compare.evidence.section_label")}</span>
                    <span className="font-bold text-neutral-900 truncate max-w-[180px]">
                      {evidence.structural_ref}
                    </span>
                  </div>
                )}

                {evidence.table_context && (
                  <div className="flex justify-between py-1">
                    <span className="font-semibold text-neutral-500">{t("compare.evidence.context_label")}</span>
                    <span className="font-medium text-neutral-700 text-right truncate max-w-[180px]">
                      {evidence.table_context}
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Verbatim Source Quote */}
            <div className="space-y-2">
              <span className="text-[11px] font-bold text-neutral-700 uppercase tracking-wider block">
                {t("compare.evidence.verbatim_snippet")}
              </span>
              <div className="bg-amber-50/70 border-l-4 border-l-amber-500 border border-neutral-200 p-3.5 rounded-lg font-mono text-[11px] leading-relaxed text-neutral-800 break-words">
                &ldquo;{evidence.verbatim_snippet}&rdquo;
              </div>
            </div>

            {/* Multiple Candidate Arbitration (if available) */}
            {candidates.length > 0 && (
              <div className="space-y-3 pt-2 border-t border-neutral-200">
                <span className="text-[11px] font-bold text-accent-700 uppercase tracking-widest block">
                  {t("compare.evidence.candidates_title")}
                </span>

                <div className="space-y-2">
                  {candidates.map((cand) => (
                    <div
                      key={cand.candidate_id}
                      className={`p-3 rounded-lg border text-xs space-y-1 ${
                        cand.is_selected
                          ? "bg-success-50/50 border-success-300"
                          : "bg-neutral-50 border-neutral-200 opacity-80"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-neutral-900">{cand.raw_label}</span>
                        {cand.is_selected ? (
                          <Badge variant="success" className="text-[9px]">
                            {t("compare.evidence.selected_candidate")}
                          </Badge>
                        ) : (
                          <Badge variant="outline" className="text-[9px]">
                            {t("compare.evidence.conflicting_candidate")}
                          </Badge>
                        )}
                      </div>

                      <div className="flex items-center justify-between font-mono text-[11px] text-neutral-700">
                        <span>{t("compare.evidence.reported_label")} {cand.raw_text_value}</span>
                        {cand.normalized_amount !== undefined && (
                          <span className="font-bold">₹{cand.normalized_amount} Cr</span>
                        )}
                      </div>

                      {cand.resolution_reason && (
                        <p className="text-[10px] text-neutral-500 pt-1 italic">
                          {t("compare.evidence.rule_label")} {cand.resolution_reason}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Educational Disclaimer */}
            <div className="p-3 bg-neutral-100 rounded-lg text-[10px] text-neutral-500 leading-normal border border-neutral-200">
              {t("compare.evidence.educational_notice")}
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  return typeof window !== "undefined" ? createPortal(modalContent, window.document.body) : modalContent;
}
