import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useErrorText, useI18n } from '../../i18n/context';
import { apiFetch } from '../../lib/api';
import type { BackupFile, BackupStatus } from '../../lib/types';

const BACKUPS_KEY = ['admin', 'backups'] as const;

/** Status of the built-in backups and a backup on demand. No download: admins do not see others' data. */
export function BackupsSection() {
  const { t, format } = useI18n();
  const errorText = useErrorText();
  const queryClient = useQueryClient();
  const status = useQuery({ queryKey: BACKUPS_KEY, queryFn: () => apiFetch<BackupStatus>('/v1/admin/backups') });
  const now = useMutation({
    mutationFn: () => apiFetch<BackupFile>('/v1/admin/backups', { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: BACKUPS_KEY }),
  });
  const data = status.data;

  return (
    <section aria-labelledby="backups-heading">
      <h2 id="backups-heading">{t('backups.title')}</h2>
      {status.isPending && <p>{t('app.loading')}</p>}
      {status.isError && (
        <p className="error" role="alert">
          {errorText(status.error)}
        </p>
      )}
      {data && (
        <div className="card habit-form">
          <p>
            {data.enabled
              ? t('backups.daily', { time: data.time, timezone: data.timezone, days: data.keep_days })
              : t('backups.off')}
          </p>
          <p>
            {data.latest
              ? t('backups.latest', { date: format.dateTime(data.latest.created_at), size: format.bytes(data.latest.size) })
              : t('backups.none')}
            {data.count > 0 && <> · {t('backups.count', { count: data.count, size: format.bytes(data.total_size) })}</>}
          </p>
          <p className="subtle">
            {t('backups.where', { directory: data.directory })} {t('backups.offsite')}
          </p>
          {data.last_error && (
            <p className="error" role="alert">
              {t('backups.failed', { date: format.dateTime(data.last_error_at), error: data.last_error })}
            </p>
          )}
          {now.isSuccess && <p role="status">{t('backups.done', { name: now.data.name })}</p>}
          {now.isError && (
            <p className="error" role="alert">
              {errorText(now.error)}
            </p>
          )}
          <div className="button-row">
            <button type="button" className="button" disabled={now.isPending} onClick={() => now.mutate()}>
              {t('backups.now')}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
