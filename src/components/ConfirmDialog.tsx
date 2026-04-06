import { useEffect, useId, useRef, type ReactNode } from "react";

type ConfirmDialogProps = {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  loading?: boolean;
  errorMessage?: string | null;
  children?: ReactNode;
  onConfirm: () => void;
  onClose: () => void;
};

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  loading = false,
  errorMessage = null,
  children,
  onConfirm,
  onClose,
}: ConfirmDialogProps) {
  const titleId = useId();
  const descriptionId = useId();
  const confirmButtonRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }

    confirmButtonRef.current?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !loading) {
        event.preventDefault();
        onClose();
      }
    };

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [loading, onClose, open]);

  if (!open) {
    return null;
  }

  return (
    <div
      className="app-confirm-dialog-backdrop"
      onClick={event => {
        if (event.target === event.currentTarget && !loading) {
          onClose();
        }
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        className="app-confirm-dialog"
      >
        <div className="app-confirm-dialog-body">
          <h2 id={titleId}>{title}</h2>
          <p id={descriptionId}>{description}</p>
          {children ? <div className="app-confirm-dialog-meta">{children}</div> : null}
          {errorMessage ? (
            <p className="app-confirm-dialog-error" role="alert">
              {errorMessage}
            </p>
          ) : null}
        </div>
        <div className="app-confirm-dialog-actions">
          <button
            type="button"
            className="landing-button landing-button-secondary"
            onClick={onClose}
            disabled={loading}
          >
            Cancel
          </button>
          <button
            ref={confirmButtonRef}
            type="button"
            className="landing-button landing-button-danger"
            onClick={onConfirm}
            disabled={loading}
          >
            {loading ? "Deleting..." : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
