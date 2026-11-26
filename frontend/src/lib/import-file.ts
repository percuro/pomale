/** A first look at a chosen export file, to show what an import would bring. The server checks it fully. */
export interface ExportSummary {
  habits: number;
  checkins: number;
  groups: number;
  pauses: number;
  exportedAt: string | null;
}

interface ExportShape {
  format?: unknown;
  version?: unknown;
  exported_at?: unknown;
  habits?: { checkins?: unknown[] }[];
  groups?: unknown[];
  pauses?: unknown[];
}

/** null: not a pomale export of a version this app knows. */
export function summarizeExport(text: string): ExportSummary | null {
  let data: ExportShape;
  try {
    data = JSON.parse(text) as ExportShape;
  } catch {
    return null;
  }
  if (!data || typeof data !== 'object' || data.format !== 'pomale-export' || data.version !== 1) return null;
  const habits = Array.isArray(data.habits) ? data.habits : [];
  return {
    habits: habits.length,
    checkins: habits.reduce((sum, habit) => sum + (Array.isArray(habit?.checkins) ? habit.checkins.length : 0), 0),
    groups: Array.isArray(data.groups) ? data.groups.length : 0,
    pauses: Array.isArray(data.pauses) ? data.pauses.length : 0,
    exportedAt: typeof data.exported_at === 'string' ? data.exported_at : null,
  };
}
