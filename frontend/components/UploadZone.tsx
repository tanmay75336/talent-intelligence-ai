"use client";

import { useRef, useState } from "react";
import { cx } from "@/lib/utils";

interface UploadZoneProps {
  files: File[];
  disabled?: boolean;
  onAddFiles: (files: File[]) => void;
  onRemoveFile: (fileName: string) => void;
}

export function UploadZone({
  files,
  disabled = false,
  onAddFiles,
  onRemoveFile,
}: UploadZoneProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const handleFiles = (incomingFiles: FileList | null) => {
    if (!incomingFiles?.length) {
      return;
    }

    const pdfFiles = Array.from(incomingFiles).filter(
      (file) => file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf"),
    );

    onAddFiles(pdfFiles);
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div>
        <p className="section-label">Resumes</p>
        <h2 className="mt-2 text-xl font-semibold text-slate-950">Upload candidate PDFs</h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          Add the resumes for this review. Files are processed by the existing backend ranking flow.
        </p>
      </div>

      <input
        ref={inputRef}
        accept=".pdf,application/pdf"
        className="hidden"
        disabled={disabled}
        multiple
        type="file"
        onChange={(event) => handleFiles(event.target.files)}
      />

      <button
        className={cx(
          "mt-5 flex w-full flex-col items-center justify-center rounded-lg border border-dashed px-6 py-9 text-center transition",
          disabled ? "cursor-not-allowed opacity-60" : "hover:border-slate-400 hover:bg-slate-50",
          isDragging ? "border-slate-500 bg-slate-50" : "border-slate-300 bg-white",
        )}
        disabled={disabled}
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragEnter={(event) => {
          event.preventDefault();
          if (!disabled) {
            setIsDragging(true);
          }
        }}
        onDragLeave={(event) => {
          event.preventDefault();
          setIsDragging(false);
        }}
        onDragOver={(event) => {
          event.preventDefault();
        }}
        onDrop={(event) => {
          event.preventDefault();
          setIsDragging(false);
          if (!disabled) {
            handleFiles(event.dataTransfer.files);
          }
        }}
      >
        <p className="text-base font-medium text-slate-900">Drop PDF resumes here</p>
        <p className="mt-2 text-sm text-slate-500">or browse from your device</p>
      </button>

      <div className="mt-5 flex items-center justify-between text-sm">
        <p className="text-slate-600">
          {files.length} {files.length === 1 ? "resume" : "resumes"} selected
        </p>
        <p className="text-slate-500">PDF only</p>
      </div>

      {files.length ? (
        <div className="mt-3 space-y-2">
          {files.map((file) => (
            <div
              key={`${file.name}-${file.lastModified}-${file.size}`}
              className="flex items-center justify-between gap-4 rounded-md border border-slate-200 bg-slate-50 px-3 py-2"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-slate-900">{file.name}</p>
                <p className="mt-0.5 text-xs text-slate-500">
                  {(file.size / 1024 / 1024).toFixed(2)} MB
                </p>
              </div>
              <button
                className="rounded-md border border-slate-300 px-2.5 py-1 text-xs text-slate-700 hover:bg-white"
                disabled={disabled}
                type="button"
                onClick={() => onRemoveFile(file.name)}
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
