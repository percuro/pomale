import { useMutation } from '@tanstack/react-query';
import { useOidcLabel } from '../../hooks/useOidcLabel';
import { useOnline } from '../../hooks/useOnline';
import { useErrorText, useT } from '../../i18n/context';
import { startOidc } from '../../lib/oidc';

export type OidcAction = 'signIn' | 'continue' | 'link' | 'confirm';

/**
 * Leaves the app for the OIDC provider. `body` returns the request body, or null when the
 * surrounding form is not valid yet (then nothing happens; the form shows why).
 */
export function OidcButton({
  action,
  path,
  body,
  primary = false,
}: {
  action: OidcAction;
  path: string;
  body: () => Record<string, unknown> | null;
  primary?: boolean;
}) {
  const t = useT();
  const errorText = useErrorText();
  const online = useOnline();
  const provider = useOidcLabel();
  const start = useMutation({ mutationFn: (payload: Record<string, unknown>) => startOidc(path, payload) });
  // Stays "pending" while the browser leaves the page
  const busy = start.isPending || start.isSuccess;

  const click = () => {
    const payload = body();
    if (payload) start.mutate(payload);
  };

  return (
    <>
      <button
        type="button"
        className={primary ? 'button primary' : 'button'}
        disabled={busy || !online}
        onClick={click}
      >
        {busy ? t('oidc.redirecting', { provider }) : t(`oidc.${action}`, { provider })}
      </button>
      {start.isError && <p className="error" role="alert">{errorText(start.error)}</p>}
    </>
  );
}
