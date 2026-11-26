import { useI18n } from '../../i18n/context';

/** Shown while the account, the instance or the code of a page loads; announced to screen readers. */
export function Loading() {
  const { t } = useI18n();
  return (
    <main className="center">
      <p role="status">{t('app.loading')}</p>
    </main>
  );
}

/** A page whose code could not be loaded (offline before it was cached, or an update in between). */
export function PageFailed() {
  const { t } = useI18n();
  return (
    <main className="center">
      <p role="alert">{t('app.pageFailed')}</p>
      <button type="button" className="button" onClick={() => window.location.reload()}>{t('app.retry')}</button>
    </main>
  );
}
