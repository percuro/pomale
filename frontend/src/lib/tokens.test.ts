import { describe, expect, it } from 'vitest';
import { activeTokens, isExpired, tokenBody, tokenFormProblem, type TokenForm } from './tokens';
import type { ApiToken } from './types';

const form: TokenForm = { label: 'Home Assistant', scopes: ['read'], allHabits: true, habitIds: [], expiresInDays: null };

function token(fields: Partial<ApiToken>): ApiToken {
  return {
    id: 1,
    label: 'x',
    scopes: ['read'],
    habit_ids: [],
    created_at: '2026-11-24T10:00:00',
    last_used_at: null,
    expires_at: null,
    revoked_at: null,
    ...fields,
  };
}

describe('API key form', () => {
  it('needs a name, a permission and, when limited, a habit', () => {
    expect(tokenFormProblem(form)).toBeNull();
    expect(tokenFormProblem({ ...form, label: '  ' })).toBe('tokens.needLabel');
    expect(tokenFormProblem({ ...form, scopes: [] })).toBe('tokens.needScope');
    expect(tokenFormProblem({ ...form, allHabits: false })).toBe('tokens.needHabit');
    expect(tokenFormProblem({ ...form, allHabits: false, habitIds: [3] })).toBeNull();
  });

  it('sends scopes in a fixed order and no habits for "all"', () => {
    expect(tokenBody({ ...form, scopes: ['checkin', 'read'], habitIds: [4, 2] })).toEqual({
      label: 'Home Assistant',
      scopes: ['read', 'checkin'],
      habit_ids: [],
      expires_in_days: null,
    });
    expect(tokenBody({ ...form, allHabits: false, habitIds: [4, 2], expiresInDays: 90 }).habit_ids).toEqual([2, 4]);
  });

  it('knows which keys still work', () => {
    const now = Date.parse('2026-11-24T12:00:00Z');
    expect(isExpired(token({ expires_at: '2026-11-24T11:59:59' }), now)).toBe(true);
    expect(isExpired(token({ expires_at: '2026-11-24T12:00:01' }), now)).toBe(false);
    const list = [token({ id: 1 }), token({ id: 2, revoked_at: '2026-11-20T00:00:00' }), token({ id: 3, expires_at: '2026-11-01T00:00:00' })];
    expect(activeTokens(list, now).map((t) => t.id)).toEqual([1]);
  });
});
