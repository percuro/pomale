import { useEffect, useId, useRef, useState, type FormEvent } from 'react';
import { useI18n } from '../../i18n/context';

/** Set the amount of a quantity goal for one day (week view). Works offline via the queue. */
export function AmountDialog({
  habitName,
  date,
  value,
  target,
  unit,
  onSave,
  onClose,
}: {
  habitName: string;
  date: string;
  value: number;
  target: number;
  unit: string | null;
  onSave: (value: number) => void;
  onClose: () => void;
}) {
  const { t, format } = useI18n();
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const fieldId = useId();
  const [amount, setAmount] = useState(String(value));

  useEffect(() => {
    const dialog = ref.current;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    dialog?.showModal();
    return () => {
      if (dialog?.open) dialog.close();
      opener?.focus();
    };
  }, []);

  const parsed = Math.max(0, Math.min(9999, Math.round(Number(amount) || 0)));
  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSave(parsed);
    onClose();
  };

  return (
    <dialog
      ref={ref}
      className="dialog card"
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <form className="dialog-body" onSubmit={submit}>
        <h2 id={titleId}>{t('week.amountTitle', { name: habitName, date: format.longDate(date) })}</h2>
        <label htmlFor={fieldId}>
          {t('week.amountLabel')} ({unit ? t('today.amountUnit', { value: parsed, target, unit }) : t('today.amount', { value: parsed, target })})
        </label>
        <div className="stepper">
          <button type="button" className="button" aria-label={t('today.less', { name: habitName })} onClick={() => setAmount(String(Math.max(0, parsed - 1)))}>
            −
          </button>
          <input
            id={fieldId}
            className="input stepper-input"
            type="number"
            inputMode="numeric"
            min={0}
            max={9999}
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
          />
          <button type="button" className="button" aria-label={t('today.more', { name: habitName })} onClick={() => setAmount(String(Math.min(9999, parsed + 1)))}>
            +
          </button>
        </div>
        <div className="actions">
          <button type="submit" className="button primary">
            {t('common.save')}
          </button>
          <button type="button" className="button" onClick={onClose}>
            {t('common.cancel')}
          </button>
        </div>
      </form>
    </dialog>
  );
}
