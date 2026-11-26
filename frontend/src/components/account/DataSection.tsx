import { useState, type ChangeEvent } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ME_KEY } from '../../hooks/useMe';
import { useGroups, usePauses } from '../../hooks/useGroups';
import { useHabits } from '../../hooks/useHabits';
import { useErrorText, useI18n } from '../../i18n/context';
import { apiFetch } from '../../lib/api';
import { summarizeExport, type ExportSummary } from '../../lib/import-file';
import type { ImportResult } from '../../lib/types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api';

/** Export as CSV (spreadsheets) or JSON (complete, for moving), and import JSON into an empty account. */
export function DataSection() {
  const { t } = useI18n();
  // Kept here: after the import the account is no longer empty and the form goes away
  const [imported, setImported] = useState<ImportResult | null>(null);
  const habits = useHabits();
  const groups = useGroups();
  const pauses = usePauses();
  const loaded = habits.isSuccess && groups.isSuccess && pauses.isSuccess;
  const empty = loaded && habits.data.length === 0 && groups.data.length === 0 && pauses.data.length === 0;

  return (
    <section aria-labelledby="data-heading">
      <h2 id="data-heading">{t('data.title')}</h2>
      <p className="subtle">{t('data.intro')}</p>
      <div className="button-row section-actions">
        <a className="button" href={`${API_BASE_URL}/v1/export.csv`} download>
          {t('account.exportButton')}
        </a>
        <a className="button" href={`${API_BASE_URL}/v1/export.json`} download>
          {t('data.exportJson')}
        </a>
      </div>
      <h3>{t('data.import')}</h3>
      {imported ? (
        <p role="status">{t('data.imported', { habits: imported.habits, checkins: imported.checkins })}</p>
      ) : (
        <>
          {loaded && !empty && <p className="subtle">{t('data.importOnlyEmpty')}</p>}
          {empty && <ImportForm onImported={setImported} />}
        </>
      )}
    </section>
  );
}

function ImportForm({ onImported }: { onImported: (result: ImportResult) => void }) {
  const { t, format } = useI18n();
  const errorText = useErrorText();
  const queryClient = useQueryClient();
  const [file, setFile] = useState<{ text: string; summary: ExportSummary } | null>(null);
  const [invalid, setInvalid] = useState(false);
  const run = useMutation({
    mutationFn: (text: string) =>
      apiFetch<ImportResult>('/v1/import', { method: 'POST', body: text }),
    onSuccess: async (result) => {
      onImported(result);
      // Everything may have changed, including time zone, language and day end
      await queryClient.invalidateQueries();
      await queryClient.refetchQueries({ queryKey: ME_KEY });
    },
  });

  const choose = async (event: ChangeEvent<HTMLInputElement>) => {
    const chosen = event.target.files?.[0];
    run.reset();
    if (!chosen) return;
    const text = await chosen.text();
    const summary = summarizeExport(text);
    setInvalid(summary === null);
    setFile(summary ? { text, summary } : null);
  };

  return (
    <div className="card habit-form">
      <p className="subtle">{t('data.importIntro')}</p>
      <label className="field">
        <span>{t('data.importFile')}</span>
        <input type="file" accept="application/json,.json" onChange={(e) => void choose(e)} />
      </label>
      {invalid && (
        <p className="error" role="alert">
          {t('data.importInvalid')}
        </p>
      )}
      {file && (
        <>
          <p role="status">
            {t('data.importSummary', {
              habits: file.summary.habits,
              checkins: file.summary.checkins,
              groups: file.summary.groups,
              pauses: file.summary.pauses,
            })}
            {file.summary.exportedAt && <> {t('data.importFrom', { date: format.dateTime(file.summary.exportedAt) })}</>}
          </p>
          <div className="button-row">
            <button type="button" className="button primary" disabled={run.isPending} onClick={() => run.mutate(file.text)}>
              {t('data.importButton')}
            </button>
          </div>
        </>
      )}
      {run.isError && (
        <p className="error" role="alert">
          {errorText(run.error)}
        </p>
      )}
    </div>
  );
}
