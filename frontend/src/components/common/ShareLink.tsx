import { CopyField } from '../habits/ShortcutPanel';
import { useI18n } from '../../i18n/context';

/** A one-time link with copy and (where the device offers it) the share sheet. */
export function ShareLink({
  intro,
  url,
  expiresAt,
  shareTitle,
  onDone,
}: {
  intro: string;
  url: string;
  expiresAt: string;
  shareTitle: string;
  onDone: () => void;
}) {
  const { t, format } = useI18n();
  const canShare = typeof navigator !== 'undefined' && typeof navigator.share === 'function';
  return (
    <div className="card created-token" role="status">
      <p>
        <strong>{intro}</strong>
      </p>
      <CopyField label={t('shortcut.url')} value={url} />
      <p className="subtle">{t('admin.linkExpires', { date: format.dateTime(expiresAt) })}</p>
      <div className="actions">
        {canShare && (
          <button
            type="button"
            className="button"
            onClick={() => navigator.share({ title: shareTitle, url }).catch(() => undefined)}
          >
            {t('common.share')}
          </button>
        )}
        <button type="button" className="button" onClick={onDone}>
          {t('admin.linkHide')}
        </button>
      </div>
    </div>
  );
}
