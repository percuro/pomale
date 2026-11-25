import type { ReactNode } from 'react';
import { useOnline } from '../../hooks/useOnline';
import { useT } from '../../i18n/context';

/** Account and admin pages need the server; offline they only show a hint. */
export function OnlineOnly({ children }: { children: ReactNode }) {
  const online = useOnline();
  const t = useT();
  if (!online) {
    return (
      <p className="sync-banner" role="status">
        {t('common.offlineOnly')}
      </p>
    );
  }
  return <>{children}</>;
}
