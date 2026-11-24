import { useState } from 'react';
import { useUpdateAccount } from '../../hooks/useAccount';
import { useErrorText, useT } from '../../i18n/context';
import { browserTimeZone } from '../../lib/browser';
import type { Me } from '../../lib/types';

const DISMISSED_KEY = 'pomale.timezoneHint';

function dismissedFor(userId: number): string | null {
  try {
    return window.localStorage.getItem(`${DISMISSED_KEY}.${userId}`);
  } catch {
    return null;
  }
}

/**
 * Once per device and zone: an account without its own time zone, on a device whose
 * zone differs from the server default, is offered to switch.
 */
export function TimezoneHint({ me }: { me: Me }) {
  const t = useT();
  const errorText = useErrorText();
  const update = useUpdateAccount();
  const device = browserTimeZone();
  const [dismissed, setDismissed] = useState(() => dismissedFor(me.id));
  if (me.timezone_setting || !device || device === me.timezone || dismissed === device) return null;

  const keep = () => {
    try {
      window.localStorage.setItem(`${DISMISSED_KEY}.${me.id}`, device);
    } catch {
      // Without storage the hint returns next time
    }
    setDismissed(device);
  };

  return (
    <div className="sync-banner" role="status">
      <span>{t('timezoneHint.text', { device, account: me.timezone })}</span>
      <button type="button" className="link-button" disabled={update.isPending} onClick={() => update.mutate({ timezone: device })}>
        {t('timezoneHint.switch', { zone: device })}
      </button>
      <button type="button" className="link-button" onClick={keep}>
        {t('timezoneHint.keep', { zone: me.timezone })}
      </button>
      {update.isError && <span className="error">{errorText(update.error)}</span>}
    </div>
  );
}
