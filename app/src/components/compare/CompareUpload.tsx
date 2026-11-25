import { useState, useRef } from "react";
import { Upload, Trash2, AlertCircle, ArrowRight, ShieldCheck, Layers } from "lucide-react";
import { Button } from "../ui/Button";
import type { ComparisonMode } from "../../lib/compareApi";
import { getTranslation, type SupportedLanguage } from "../../lib/translations";

interface CompareUploadProps {
  onStartUpload: (files: File[], mode: ComparisonMode) => Promise<void>;
  isLoading: boolean;
  language: SupportedLanguage;
}

const MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024; // 20 MiB
const MAX_SESSION_SIZE_BYTES = 100 * 1024 * 1024; // 100 MiB
const ACCEPTED_EXTENSIONS = [".pdf", ".png", ".jpg", ".jpeg", ".docx", ".xlsx", ".xls"];

export function CompareUpload({ onStartUpload, isLoading, language }: CompareUploadProps) {
  const [mode, setMode] = useState<ComparisonMode>("QUICK_COMPARE");
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const t = (key: string) => getTranslation(key, language);

  const maxFiles = mode === "QUICK_COMPARE" ? 2 : 5;

  const validateAndAddFiles = (newFiles: FileList | File[]) => {
    setError(null);
    const validList = Array.from(newFiles);

    // Filter accepted extensions
    const acceptable = validList.filter((f) => {
      const ext = "." + f.name.split(".").pop()?.toLowerCase();
      return ACCEPTED_EXTENSIONS.includes(ext);
    });

    if (acceptable.length !== validList.length) {
      setError(`${t("compare.upload.skipped_types")}${ACCEPTED_EXTENSIONS.join(", ")}`);
    }

    const merged = [...selectedFiles];
    for (const f of acceptable) {
      if (f.size > MAX_FILE_SIZE_BYTES) {
        setError(`${t("compare.upload.error.file_size")} ${f.name} (${(f.size / (1024 * 1024)).toFixed(1)} MiB > 20 MiB)`);
        return;
      }
      if (merged.some((existing) => existing.name === f.name && existing.size === f.size)) {
        continue; // duplicate
      }
      if (merged.length >= maxFiles) {
        setError(t("compare.upload.error.max_files"));
        break;
      }
      merged.push(f);
    }

    // Check session limit
    const totalSize = merged.reduce((acc, curr) => acc + curr.size, 0);
    if (totalSize > MAX_SESSION_SIZE_BYTES) {
      setError(t("compare.upload.error.session_size"));
      return;
    }

    setSelectedFiles(merged);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files) {
      validateAndAddFiles(e.dataTransfer.files);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      validateAndAddFiles(e.target.files);
      e.target.value = "";
    }
  };

  const handleRemoveFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, idx) => idx !== index));
    setError(null);
  };

  const handleModeChange = (newMode: ComparisonMode) => {
    setMode(newMode);
    setError(null);
    if (newMode === "QUICK_COMPARE" && selectedFiles.length > 2) {
      setSelectedFiles((prev) => prev.slice(0, 2));
    }
  };

  const handleSubmit = async () => {
    if (selectedFiles.length < 2) {
      setError(t("compare.upload.error.min_files"));
      return;
    }
    setError(null);
    try {
      await onStartUpload(selectedFiles, mode);
    } catch (err: any) {
      setError(err.message || t("compare.upload.failed"));
    }
  };

  const totalSessionSize = selectedFiles.reduce((acc, curr) => acc + curr.size, 0);

  return (
    <div className="max-w-4xl mx-auto py-8 px-4 sm:px-6 space-y-8 animate-fade-in font-sans">
      {/* Title & Mode Selection */}
      <div className="text-center space-y-3">
        <div className="inline-flex items-center gap-2 bg-accent-50 text-accent-700 px-3 py-1 rounded-full text-xs font-bold border border-accent-200">
          <Layers className="w-3.5 h-3.5" />
          {t("compare.nav.badge")}
        </div>
        <h1 className="text-3xl sm:text-4xl font-extrabold text-neutral-900 font-heading">
          {t("compare.title")}
        </h1>
        <p className="text-sm sm:text-base text-neutral-600 max-w-2xl mx-auto font-medium">
          {t("compare.subtitle")}
        </p>

        {/* Mode Selector */}
        <div className="pt-4 flex justify-center">
          <div className="inline-flex rounded-xl bg-neutral-200/80 p-1.5 shadow-inner">
            <button
              onClick={() => handleModeChange("QUICK_COMPARE")}
              className={`px-4 py-2 rounded-lg text-xs font-bold transition-all ${
                mode === "QUICK_COMPARE"
                  ? "bg-white text-neutral-900 shadow-sm"
                  : "text-neutral-600 hover:text-neutral-900"
              }`}
            >
              {t("compare.mode.quick")}
            </button>
            <button
              onClick={() => handleModeChange("MULTI_DOCUMENT")}
              className={`px-4 py-2 rounded-lg text-xs font-bold transition-all ${
                mode === "MULTI_DOCUMENT"
                  ? "bg-white text-neutral-900 shadow-sm"
                  : "text-neutral-600 hover:text-neutral-900"
              }`}
            >
              {t("compare.mode.multi")}
            </button>
          </div>
        </div>
        <p className="text-xs text-neutral-500">
          {mode === "QUICK_COMPARE" ? t("compare.mode.quick.desc") : t("compare.mode.multi.desc")}
        </p>
      </div>

      {/* Upload Box */}
      <div className="bg-white border border-neutral-200 rounded-xl p-6 sm:p-8 shadow-sm space-y-6">
        <input
          type="file"
          ref={fileInputRef}
          className="hidden"
          multiple
          accept=".pdf,.png,.jpg,.jpeg,.docx,.xlsx,.xls"
          onChange={handleFileChange}
        />

        <div
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragOver(true);
          }}
          onDragLeave={() => setIsDragOver(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors flex flex-col items-center justify-center space-y-4 ${
            isDragOver ? "border-accent-500 bg-accent-50/30" : "border-neutral-200 hover:border-neutral-300 hover:bg-neutral-50/50"
          }`}
        >
          <div className="w-12 h-12 rounded-full bg-neutral-100 flex items-center justify-center text-neutral-600">
            <Upload className="w-6 h-6" />
          </div>

          <div className="space-y-1">
            <p className="text-sm font-bold text-neutral-900">{t("compare.upload.dropzone")}</p>
            <p className="text-xs font-semibold text-neutral-400">{t("compare.upload.limits")}</p>
            <p className="text-[11px] font-bold text-accent-700 tracking-wider pt-1">{t("compare.upload.formats")}</p>
          </div>

          <Button
            type="button"
            variant="outline"
            size="sm"
            className="text-xs font-bold"
            onClick={(e) => {
              e.stopPropagation();
              fileInputRef.current?.click();
            }}
          >
            {t("compare.upload.select_btn")}
          </Button>
        </div>

        {/* Selected Files List */}
        {selectedFiles.length > 0 && (
          <div className="space-y-3 pt-2">
            <div className="flex items-center justify-between text-xs font-semibold text-neutral-500 border-b border-neutral-100 pb-2">
              <span>
                {selectedFiles.length} of {maxFiles} {t("compare.upload.files_selected")}
              </span>
              <span>
                {t("compare.upload.total_label")} {(totalSessionSize / (1024 * 1024)).toFixed(2)} / 100 MiB
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {selectedFiles.map((file, idx) => {
                const slotLetters = ["A", "B", "C", "D", "E"];
                const slotLabel = `Doc ${slotLetters[idx] || idx + 1}`;
                const ext = file.name.split(".").pop()?.toUpperCase() || "DOC";

                return (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-3 rounded-lg border border-neutral-200 bg-neutral-50/60"
                  >
                    <div className="flex items-center gap-3 overflow-hidden">
                      <span className="w-6 h-6 rounded-md bg-neutral-900 text-white font-bold text-[11px] flex items-center justify-center shrink-0">
                        {slotLetters[idx]}
                      </span>
                      <div className="truncate">
                        <p className="text-xs font-bold text-neutral-900 truncate">{file.name}</p>
                        <p className="text-[10px] text-neutral-500">
                          <span className="font-semibold text-accent-700">{ext}</span> · {(file.size / 1024 / 1024).toFixed(2)} MiB · {slotLabel}
                        </p>
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={() => handleRemoveFile(idx)}
                      disabled={isLoading}
                      className="text-neutral-400 hover:text-error-600 transition-colors p-1"
                      title={t("compare.upload.remove_title")}
                      aria-label={`${t("compare.upload.remove_title")}: ${file.name}`}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Error Alert */}
        {error && (
          <div className="flex items-start gap-2.5 p-3.5 rounded-lg bg-error-50 border border-error-200 text-error-700 text-xs">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <p className="font-medium">{error}</p>
          </div>
        )}

        {/* Start Upload Button */}
        <div className="flex justify-end pt-2">
          <Button
            onClick={handleSubmit}
            disabled={selectedFiles.length < 2 || isLoading}
            className="w-full sm:w-auto font-bold text-xs px-6 py-2.5"
          >
            {isLoading ? t("compare.upload.uploading_detecting") : t("compare.upload.start_btn")}
            <ArrowRight className="w-4 h-4 ml-2" />
          </Button>
        </div>
      </div>

      {/* Safety Notice */}
      <div className="flex items-center justify-center gap-2 text-xs text-neutral-500 font-medium">
        <ShieldCheck className="w-4 h-4 text-neutral-400" />
        <span>{t("compare.upload.security_disclaimer")}</span>
      </div>
    </div>
  );
}
