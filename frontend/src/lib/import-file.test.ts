import { describe, expect, it } from 'vitest';
import { summarizeExport } from './import-file';

describe('export file summary', () => {
  it('counts what the file contains', () => {
    const file = JSON.stringify({
      format: 'pomale-export',
      version: 1,
      exported_at: '2026-11-24T18:00:00',
      groups: [{}, {}],
      habits: [{ checkins: [{}, {}, {}] }, { checkins: [] }, {}],
      pauses: [{}],
    });
    expect(summarizeExport(file)).toEqual({ habits: 3, checkins: 3, groups: 2, pauses: 1, exportedAt: '2026-11-24T18:00:00' });
  });

  it('refuses other files', () => {
    expect(summarizeExport('not json')).toBeNull();
    expect(summarizeExport('null')).toBeNull();
    expect(summarizeExport(JSON.stringify({ format: 'pomale-export', version: 2 }))).toBeNull();
    expect(summarizeExport(JSON.stringify({ habits: [] }))).toBeNull();
  });
});
