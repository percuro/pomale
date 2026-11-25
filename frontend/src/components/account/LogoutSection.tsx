import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../../lib/api';
import { signedOut } from '../../hooks/useMe';
import { useSession } from '../../hooks/useSession';
import { useI18n } from '../../i18n/context';
import { forgetLocalSubscription } from '../../lib/push';
import { syncEngine } from '../../lib/sync-engine';
import { ConfirmDialog } from '../common/ConfirmDialog';

/** Logging out, and for administrators the way to the administration. */
export function LogoutSection() {
  const { me } = useSession();
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [confirmLogout, setConfirmLogout] = useState(0);
  const logout = useMutation({
    mutationFn: () => apiFetch<void>('/v1/auth/logout', { method: 'POST' }),
    // Forget local data only after a successful logout. The server dropped this device's
    // reminders; the browser subscription goes too, so the next account does not inherit it.
    onSuccess: async () => {
      await forgetLocalSubscription();
      await signedOut(queryClient);
    },
    onSettled: () => setConfirmLogout(0),
  });

  const onLogout = () => {
    // Unsent changes stay on this device; ask before leaving them behind
    const waiting = syncEngine.getSnapshot().ops.length;
    if (waiting > 0) setConfirmLogout(waiting);
    else logout.mutate();
  };

  return (
    <>
      <div className="button-row">
        <button type="button" className="button" onClick={onLogout} disabled={logout.isPending}>
          {t('nav.logout')}
        </button>
        {me.role === 'admin' && (
          <Link to="/admin" className="button">
            {t('nav.admin')}
          </Link>
        )}
      </div>
      {logout.isError && <p className="error" role="alert">{t('logout.failed')}</p>}
      <ConfirmDialog
        open={confirmLogout > 0}
        title={t('logout.title')}
        confirmLabel={t('logout.confirm')}
        busy={logout.isPending}
        onConfirm={() => logout.mutate()}
        onCancel={() => setConfirmLogout(0)}
      >
        <p>{t('logout.pending', { count: confirmLogout })}</p>
      </ConfirmDialog>
    </>
  );
}
