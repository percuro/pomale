import { useT } from '../../i18n/context';

export const MIN_PASSWORD_LENGTH = 12;

/** "New password" and "repeat" with a mismatch hint. */
export function NewPasswordFields({
  password,
  confirm,
  onPassword,
  onConfirm,
}: {
  password: string;
  confirm: string;
  onPassword: (value: string) => void;
  onConfirm: (value: string) => void;
}) {
  const t = useT();
  const mismatch = confirm.length > 0 && password !== confirm;
  return (
    <>
      <label className="field">
        <span>{t('field.newPassword', { min: MIN_PASSWORD_LENGTH })}</span>
        <input
          name="new-password"
          type="password"
          autoComplete="new-password"
          required
          minLength={MIN_PASSWORD_LENGTH}
          value={password}
          onChange={(e) => onPassword(e.target.value)}
        />
      </label>
      <label className="field">
        <span>{t('field.repeatPassword')}</span>
        <input
          name="confirm-password"
          type="password"
          autoComplete="new-password"
          required
          value={confirm}
          aria-invalid={mismatch}
          onChange={(e) => onConfirm(e.target.value)}
        />
      </label>
      {mismatch && <p className="error" role="alert">{t('field.passwordMismatch')}</p>}
    </>
  );
}
