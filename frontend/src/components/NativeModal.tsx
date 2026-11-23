"use client";

import { useEffect, useId, useRef } from "react";
import { X } from "lucide-react";

interface NativeModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}

/**
 * Modal berbasis elemen native `<dialog>` sesuai panduan modern web:
 * - Memakai `showModal()` (tanpa role="dialog"/aria-modal manual)
 * - Mendukung `Esc` dan `closedby="any"` + fallback pointer-bounds untuk Safari
 */
export default function NativeModal({
  open,
  onClose,
  title,
  children,
}: NativeModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    if (open && !dialog.open) {
      dialog.showModal();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  // Fallback light-dismiss berbasis posisi pointer untuk browser tanpa `closedby` (mis. Safari)
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog || "closedBy" in HTMLDialogElement.prototype) return;

    const isOutside = (e: PointerEvent) => {
      const r = dialog.getBoundingClientRect();
      return (
        e.clientX < r.left ||
        e.clientX > r.right ||
        e.clientY < r.top ||
        e.clientY > r.bottom
      );
    };

    let pressedOutside = false;
    const onDown = (e: PointerEvent) => {
      pressedOutside = isOutside(e);
    };
    const onUp = (e: PointerEvent) => {
      if (pressedOutside && isOutside(e)) {
        dialog.close();
      }
      pressedOutside = false;
    };

    dialog.addEventListener("pointerdown", onDown);
    dialog.addEventListener("pointerup", onUp);
    return () => {
      dialog.removeEventListener("pointerdown", onDown);
      dialog.removeEventListener("pointerup", onUp);
    };
  }, []);

  return (
    <dialog
      ref={dialogRef}
      className="native-modal"
      aria-labelledby={titleId}
      {...({ closedby: "any" } as Record<string, string>)}
      onClose={() => {
        if (dialogRef.current) {
          dialogRef.current.returnValue = "";
        }
        onClose();
      }}
    >
      <div className="rounded-xl bg-white border border-slate-200 overflow-hidden">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3.5">
          <h2 id={titleId} className="text-base font-semibold text-slate-900">
            {title}
          </h2>
          <button
            type="button"
            onClick={() => dialogRef.current?.close()}
            aria-label="Tutup dialog"
            className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-800"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="max-h-[80vh] overflow-y-auto p-5">{children}</div>
      </div>
    </dialog>
  );
}
