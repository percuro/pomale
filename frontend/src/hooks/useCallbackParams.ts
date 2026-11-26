import { useEffect, useState } from 'react';
import { clearHashParams, parseHashParams } from '../lib/oidc';

/**
 * What the OIDC callback put in the fragment (#error=…, #oidc=linked, #reauth=ok), read once.
 * Reading happens while rendering, removing only after the page is on screen: React may render
 * a page more than once before it shows it (e.g. while its code loads), and each attempt must
 * still find the fragment.
 */
export function useCallbackParams(): Record<string, string> {
  const [params] = useState(() => parseHashParams(window.location.hash));
  useEffect(() => clearHashParams(), []);
  return params;
}
