import { useT } from '../i18n/context';
import { useMeta } from './useMeta';

/** Name of the OIDC provider for buttons: OIDC_LABEL, else a translated "single sign-on". */
export function useOidcLabel(): string {
  const t = useT();
  const meta = useMeta();
  return meta.data?.oidc?.label ?? t('oidc.defaultLabel');
}
