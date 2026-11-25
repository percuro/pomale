import { useState, type FormEvent } from 'react';
import { useErrorText, useI18n } from '../../i18n/context';
import { useGroupAction, useGroups } from '../../hooks/useGroups';
import type { Group } from '../../lib/types';
import { ConfirmDialog } from '../common/ConfirmDialog';
import { ArrowDownIcon, ArrowUpIcon } from '../Icons';

export function GroupsSection() {
  const t = useI18n().t;
  const errorText = useErrorText();
  const groups = useGroups();
  const action = useGroupAction();
  const [name, setName] = useState('');
  const [deleting, setDeleting] = useState<Group | null>(null);
  const list = groups.data ?? [];

  const add = (event: FormEvent) => {
    event.preventDefault();
    action.mutate({ type: 'createGroup', name }, { onSuccess: () => setName('') });
  };
  const move = (index: number, delta: number) => {
    const ids = list.map((g) => g.id);
    [ids[index], ids[index + delta]] = [ids[index + delta], ids[index]];
    action.mutate({ type: 'orderGroups', ids });
  };

  return (
    <section aria-labelledby="groups-heading" className="settings-section">
      <h2 id="groups-heading">{t('groups.title')}</h2>
      <p className="subtle">{t('groups.intro')}</p>
      {groups.isSuccess && list.length === 0 && <p className="subtle">{t('groups.empty')}</p>}
      {list.length > 0 && (
        <ul className="habit-list">
          {list.map((group, i) => (
            <GroupItem
              key={group.id}
              group={group}
              onUp={i > 0 ? () => move(i, -1) : undefined}
              onDown={i < list.length - 1 ? () => move(i, 1) : undefined}
              onDelete={() => setDeleting(group)}
            />
          ))}
        </ul>
      )}
      <form className="inline-form" onSubmit={add}>
        <label className="field">
          <span>{t('groups.new')}</span>
          <input required maxLength={60} value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <button type="submit" className="button" disabled={action.isPending}>
          {t('groups.add')}
        </button>
      </form>
      {action.isError && !deleting && <p role="alert" className="error">{errorText(action.error)}</p>}
      <ConfirmDialog
        open={deleting !== null}
        title={t('groups.deleteTitle', { name: deleting?.name ?? '' })}
        confirmLabel={t('groups.delete')}
        danger
        busy={action.isPending}
        error={action.isError ? errorText(action.error) : null}
        onCancel={() => setDeleting(null)}
        onConfirm={() =>
          deleting && action.mutate({ type: 'deleteGroup', id: deleting.id }, { onSuccess: () => setDeleting(null) })
        }
      >
        <p>{t('groups.deleteText')}</p>
      </ConfirmDialog>
    </section>
  );
}

function GroupItem({
  group,
  onUp,
  onDown,
  onDelete,
}: {
  group: Group;
  onUp?: () => void;
  onDown?: () => void;
  onDelete: () => void;
}) {
  const t = useI18n().t;
  const action = useGroupAction();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(group.name);

  if (editing) {
    return (
      <li className="habit-item">
        <form
          className="inline-form"
          aria-label={t('groups.renameLabel', { name: group.name })}
          onSubmit={(event) => {
            event.preventDefault();
            action.mutate({ type: 'renameGroup', id: group.id, name }, { onSuccess: () => setEditing(false) });
          }}
        >
          <label className="field">
            <span>{t('habits.name')}</span>
            <input required maxLength={60} value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <button type="submit" className="button primary" disabled={action.isPending}>
            {t('common.save')}
          </button>
          <button type="button" className="button" onClick={() => setEditing(false)}>
            {t('common.cancel')}
          </button>
        </form>
      </li>
    );
  }
  return (
    <li className="habit-item">
      <span className="habit-summary habit-title">{group.name}</span>
      <div className="button-row">
        <button type="button" className="button icon" disabled={!onUp} onClick={onUp} aria-label={t('groups.moveUp', { name: group.name })}>
          <ArrowUpIcon />
        </button>
        <button type="button" className="button icon" disabled={!onDown} onClick={onDown} aria-label={t('groups.moveDown', { name: group.name })}>
          <ArrowDownIcon />
        </button>
        <button
          type="button"
          className="button"
          aria-label={t('groups.renameLabel', { name: group.name })}
          onClick={() => {
            setName(group.name);
            setEditing(true);
          }}
        >
          {t('groups.rename')}
        </button>
        <button type="button" className="button" aria-label={t('groups.deleteLabel', { name: group.name })} onClick={onDelete}>
          {t('groups.delete')}
        </button>
      </div>
    </li>
  );
}
