"use client";

import { useEffect } from "react";
import type { Citation } from "@/lib/api";
import { CitationPanel } from "@/components/CitationPanel";
import type { SourceSnapshot } from "@/lib/sourcePreview";

export function CitationModal({
  citation,
  snapshot,
  onClose,
}: {
  citation: Citation;
  snapshot?: SourceSnapshot;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4 sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="citation-modal-title"
    >
      <button
        type="button"
        className="absolute inset-0 bg-black/65 backdrop-blur-[2px]"
        aria-label="关闭引用预览"
        onClick={onClose}
      />

      <div className="relative z-10 w-full max-w-lg max-h-[min(88vh,640px)] flex flex-col">
        <CitationPanel
          citation={citation}
          snapshot={snapshot}
          onClose={onClose}
          variant="modal"
        />
      </div>
    </div>
  );
}
