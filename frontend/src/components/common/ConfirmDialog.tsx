import { useEffect, useId, useRef, type FormEvent, type ReactNode } from 'react';
import { useT } from '../../i18n/context';

/**
 * Modal confirmation for destructive actions (role="alertdialog").
 * Uses the native <dialog>: focus stays inside while open and returns to the
 * element that opened it afterwards; Escape cancels.
 */
export function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel,
  busy = false,
  danger = false,
  error,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  children: ReactNode;
  confirmLabel: string;
  busy?: boolean;
  danger?: boolean;
  error?: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const t = useT();
  const ref = useRef<HTMLDialogElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const titleId = useId();
  const textId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      dialog.showModal();
    } else if (!open && dialog.open) {
      dialog.close();
      opener.current?.focus();
    }
  }, [open]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    onConfirm();
  };

  return (
    <dialog
      ref={ref}
      className="dialog card"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby={titleId}
      aria-describedby={textId}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onCancel();
      }}
    >
      {open && (
        <form className="dialog-body" onSubmit={submit}>
          <h2 id={titleId}>{title}</h2>
          <div id={textId} className="dialog-text">
            {children}
          </div>
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <div className="actions">
            <button type="submit" className={danger ? 'button danger' : 'button primary'} disabled={busy}>
              {confirmLabel}
            </button>
            <button type="button" className="button" onClick={onCancel} disabled={busy}>
              {t('common.cancel')}
            </button>
          </div>
        </form>
      )}
    </dialog>
  );
}
