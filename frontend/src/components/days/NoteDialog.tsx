import { useEffect, useId, useRef, useState, type FormEvent } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../../lib/api';
import { useErrorText, useI18n } from '../../i18n/context';
import { useOnline } from '../../hooks/useOnline';
import { DAYS_KEY } from '../../hooks/useDays';
import { HISTORY_KEY } from '../../hooks/useHistory';

/**
 * Optional note for one habit on one day. Never part of checking off: it opens only from
 * its own button. Saved directly (needs a connection); the last saved text wins.
 */
export function NoteDialog({
  habitId,
  habitName,
  date,
  note,
  onClose,
}: {
  habitId: number;
  habitName: string;
  date: string;
  note: string | null;
  onClose: () => void;
}) {
  const { t, format } = useI18n();
  const errorText = useErrorText();
  const online = useOnline();
  const queryClient = useQueryClient();
  const ref = useRef<HTMLDialogElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const titleId = useId();
  const fieldId = useId();
  const [text, setText] = useState(note ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const dialog = ref.current;
    opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    dialog?.showModal();
    return () => {
      if (dialog?.open) dialog.close();
      opener.current?.focus();
    };
  }, []);

  const save = async (value: string) => {
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`/v1/habits/${habitId}/days/${date}/note`, {
        method: 'PUT',
        body: JSON.stringify({ note: value }),
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: DAYS_KEY }),
        queryClient.invalidateQueries({ queryKey: HISTORY_KEY }),
      ]);
      onClose();
    } catch (failure) {
      setError(t('note.failed', { reason: errorText(failure) }));
    } finally {
      setBusy(false);
    }
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void save(text);
  };

  return (
    <dialog
      ref={ref}
      className="dialog"
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose();
      }}
    >
      <form className="dialog-body" onSubmit={submit}>
        <h2 id={titleId}>{t('note.title', { name: habitName, date: format.longDate(date) })}</h2>
        <label htmlFor={fieldId}>{t('note.label')}</label>
        <textarea
          id={fieldId}
          className="input note-input"
          rows={4}
          maxLength={500}
          value={text}
          onChange={(event) => setText(event.target.value)}
        />
        {!online && <p className="subtle">{t('common.offlineOnly')}</p>}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <div className="button-row">
          <button type="submit" className="button primary" disabled={busy || !online}>
            {t('note.save')}
          </button>
          {note && (
            <button type="button" className="button" disabled={busy || !online} onClick={() => void save('')}>
              {t('note.remove')}
            </button>
          )}
          <button type="button" className="button" onClick={onClose} disabled={busy}>
            {t('common.cancel')}
          </button>
        </div>
      </form>
    </dialog>
  );
}
