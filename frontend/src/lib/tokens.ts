import type { ApiToken, TokenScope } from './types';

export const TOKEN_SCOPES: TokenScope[] = ['read', 'checkin'];
export const TOKEN_EXPIRY_DAYS = [30, 90, 365] as const;
export type TokenExpiry = (typeof TOKEN_EXPIRY_DAYS)[number] | null;

export interface TokenForm {
  label: string;
  scopes: TokenScope[];
  /** false: only the habits in habitIds */
  allHabits: boolean;
  habitIds: number[];
  expiresInDays: TokenExpiry;
}

/** What keeps the form from being sent, as a message key; null = fine. */
export function tokenFormProblem(form: TokenForm): 'tokens.needScope' | 'tokens.needHabit' | 'tokens.needLabel' | null {
  if (!form.label.trim()) return 'tokens.needLabel';
  if (form.scopes.length === 0) return 'tokens.needScope';
  if (!form.allHabits && form.habitIds.length === 0) return 'tokens.needHabit';
  return null;
}

export function tokenBody(form: TokenForm) {
  return {
    label: form.label.trim(),
    scopes: TOKEN_SCOPES.filter((scope) => form.scopes.includes(scope)),
    habit_ids: form.allHabits ? [] : [...form.habitIds].sort((a, b) => a - b),
    expires_in_days: form.expiresInDays,
  };
}

/** Timestamps from the API are UTC without a zone. */
function parseUtc(value: string): number {
  return Date.parse(/[zZ]|[+-]\d\d:?\d\d$/.test(value) ? value : `${value}Z`);
}

export function isExpired(token: Pick<ApiToken, 'expires_at'>, now: number = Date.now()): boolean {
  return token.expires_at !== null && parseUtc(token.expires_at) <= now;
}

/** Keys that still work: not revoked and not expired. */
export function activeTokens(tokens: ApiToken[], now: number = Date.now()): ApiToken[] {
  return tokens.filter((token) => token.revoked_at === null && !isExpired(token, now));
}
