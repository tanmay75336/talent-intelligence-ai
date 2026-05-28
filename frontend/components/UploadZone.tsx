"use client";

import { useRef, useState } from "react";
import { cx } from "@/lib/utils";

interface UploadZoneProps {
  files: File[];
  disabled?: boolean;
  onAddFiles: (files: File[]) => void;
  onRemoveFile: (fileName: string) => void;
}

function PdfIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-6 w-6"
      fill="none"
      viewBox="0 0 24 24"
    >
      <path
        d="M7 3.75h6.2L18.25 8.8V19A2.25 2.25 0 0 1 16 21.25H7A2.25 2.25 0 0 1 4.75 19V6A2.25 2.25 0 0 1 7 3.75Z"
        className="stroke-slate-300"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.5"
      />
      <path
        d="M13 3.75V8.5h4.75"
        className="stroke-slate-300"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.5"
      />
      <path
        d="M8 15.25h8M8 11.75h3"
        className="stroke-sky-300"
        strokeLinecap="round"
        strokeWidth="1.5"
      />
    </svg>
  );
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
    <div className="card-muted p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="section-label">Resume Upload</p>
          <h2 className="mt-3 text-xl font-semibold text-slate-50">
            Upload candidate resumes
          </h2>
          <p className="mt-2 text-sm leading-6 text-slate-400">
            Drag PDF resumes here or browse from your device. The ranking API will
            process multiple files in a single run.
          </p>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/40 p-3 text-slate-300">
          <PdfIcon />
        </div>
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
          "mt-6 flex w-full flex-col items-center justify-center rounded-3xl border border-dashed px-6 py-10 text-center transition duration-200",
          disabled ? "cursor-not-allowed opacity-60" : "hover:border-sky-400/50 hover:bg-sky-500/5",
          isDragging
            ? "border-sky-400/60 bg-sky-500/10"
            : "border-slate-600/80 bg-slate-950/30",
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
        <div className="rounded-full border border-slate-700/70 bg-slate-900/70 p-4 text-slate-200">
          <PdfIcon />
        </div>
        <p className="mt-4 text-base font-medium text-slate-100">
          Drag and drop PDF resumes
        </p>
        <p className="mt-2 text-sm text-slate-400">
          Multiple files supported. Only PDF files are accepted.
        </p>
        <span className="mt-5 rounded-full border border-slate-700/70 px-4 py-2 text-sm text-slate-300">
          Browse files
        </span>
      </button>

      <div className="mt-6 flex items-center justify-between">
        <p className="text-sm text-slate-400">
          {files.length} {files.length === 1 ? "resume" : "resumes"} selected
        </p>
        <p className="text-sm text-slate-500">Best results with clean PDF text layers.</p>
      </div>

      <div className="mt-4 space-y-3">
        {files.map((file) => (
          <div
            key={`${file.name}-${file.lastModified}-${file.size}`}
            className="flex items-center justify-between gap-4 rounded-2xl border border-slate-700/60 bg-slate-950/35 px-4 py-3"
          >
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-slate-100">{file.name}</p>
              <p className="mt-1 text-xs text-slate-500">
                {(file.size / 1024 / 1024).toFixed(2)} MB
              </p>
            </div>
            <button
              className="rounded-full border border-slate-700/70 px-3 py-1 text-xs text-slate-300 transition hover:border-slate-500 hover:text-slate-100"
              disabled={disabled}
              type="button"
              onClick={() => onRemoveFile(file.name)}
            >
              Remove
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
