import { APP_NAME } from '../app/brand';
import { useState, type FormEvent } from 'react';
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type Announcements,
  type DragEndEvent,
} from '@dnd-kit/core';
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { useErrorText, useI18n } from '../i18n/context';
import type { Group, Habit, HabitColor } from '../lib/types';
import { colorStyle } from '../lib/habit-style';
import { ColorPicker } from '../components/habits/ColorPicker';
import { GoalFields } from '../components/habits/GoalFields';
import { goalValid, sameGoal } from '../lib/goals';
import { normalizeTimes, sameTimes, timesValid } from '../lib/reminder-times';
import { GroupsSection } from '../components/habits/GroupsSection';
import { PausesSection } from '../components/habits/PausesSection';
import { ReminderTimes } from '../components/habits/ReminderTimes';
import { ShortcutPanel } from '../components/habits/ShortcutPanel';
import { useHabitAction, useHabits, type Goal } from '../hooks/useHabits';
import { useGroups } from '../hooks/useGroups';
import { useSession } from '../hooks/useSession';
import { ArrowDownIcon, ArrowUpIcon, GripIcon } from '../components/Icons';

export function HabitsPage() {
  const { t, format } = useI18n();
  const errorText = useErrorText();
  const habits = useHabits();
  const groups = useGroups();
  const action = useHabitAction();
  const active = (habits.data ?? []).filter((h) => !h.archived_on);
  const archived = (habits.data ?? []).filter((h) => h.archived_on);
  // Shown order while a new order is being saved, so the list does not jump back
  const [pendingOrder, setPendingOrder] = useState<number[] | null>(null);
  const ordered = pendingOrder
    ? pendingOrder.map((id) => active.find((h) => h.id === id)).filter((h): h is Habit => Boolean(h))
    : active;

  const saveOrder = (ids: number[]) => {
    setPendingOrder(ids);
    action.mutate(
      { type: 'order', items: ids.map((id) => ({ id, group_id: active.find((h) => h.id === id)?.group_id ?? null })) },
      { onSettled: () => setPendingOrder(null) },
    );
  };
  const move = (index: number, delta: number) => {
    const ids = ordered.map((h) => h.id);
    if (index + delta < 0 || index + delta >= ids.length) return;
    saveOrder(arrayMove(ids, index, index + delta));
  };

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );
  const nameOf = (id: string | number) => ordered.find((h) => h.id === Number(id))?.name ?? '';
  const positionOf = (id: string | number | undefined) => ordered.findIndex((h) => h.id === Number(id)) + 1;
  const announcements: Announcements = {
    onDragStart: ({ active: dragged }) => t('habits.dnd.picked', { name: nameOf(dragged.id) }),
    onDragOver: ({ active: dragged, over }) =>
      over
        ? t('habits.dnd.moved', { name: nameOf(dragged.id), position: positionOf(over.id), total: ordered.length })
        : undefined,
    onDragEnd: ({ active: dragged, over }) =>
      over
        ? t('habits.dnd.dropped', { name: nameOf(dragged.id), position: positionOf(over.id), total: ordered.length })
        : undefined,
    onDragCancel: ({ active: dragged }) => t('habits.dnd.cancelled', { name: nameOf(dragged.id) }),
  };
  const onDragEnd = ({ active: dragged, over }: DragEndEvent) => {
    if (!over || dragged.id === over.id) return;
    const ids = ordered.map((h) => h.id);
    saveOrder(arrayMove(ids, ids.indexOf(Number(dragged.id)), ids.indexOf(Number(over.id))));
  };

  return (
    <>
      <div className="page-head">
        <h1>{t('habits.title')}</h1>
      </div>
      <NewHabitForm groups={groups.data ?? []} />

      {action.isError && <p role="alert" className="error">{errorText(action.error)}</p>}
      {habits.isPending && <p>{t('app.loading')}</p>}
      {habits.isError && <p role="alert" className="error">{errorText(habits.error)}</p>}

      {ordered.length > 0 && (
        <section aria-labelledby="active-heading">
          <h2 id="active-heading">{t('habits.active')}</h2>
          <p className="subtle" id="sort-hint">
            {t('habits.sortHint')}
          </p>
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={onDragEnd}
            accessibility={{ announcements, screenReaderInstructions: { draggable: t('habits.dnd.instructions') } }}
          >
            <SortableContext items={ordered.map((h) => h.id)} strategy={verticalListSortingStrategy}>
              <ul className="habit-list">
                {ordered.map((habit, i) => (
                  <HabitItem
                    key={habit.id}
                    habit={habit}
                    groups={groups.data ?? []}
                    onUp={i > 0 ? () => move(i, -1) : undefined}
                    onDown={i < ordered.length - 1 ? () => move(i, 1) : undefined}
                  />
                ))}
              </ul>
            </SortableContext>
          </DndContext>
        </section>
      )}

      {archived.length > 0 && (
        <details className="archived">
          <summary>{t('habits.archivedCount', { count: archived.length })}</summary>
          <ul className="habit-list">
            {archived.map((habit) => (
              <li key={habit.id} className="habit-item">
                <div className="habit-summary">
                  <span className="habit-title">{habit.name}</span>
                  <span className="subtle">{t('habits.archivedOn', { date: format.longDate(habit.archived_on!) })}</span>
                </div>
                <div className="button-row">
                  <button
                    type="button"
                    className="button"
                    onClick={() => action.mutate({ type: 'unarchive', id: habit.id })}
                  >
                    {t('habits.reactivate')}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </details>
      )}

      <GroupsSection />
      <PausesSection habits={active} />
      <p className="subtle version">{t('app.version', { name: APP_NAME, version: __APP_VERSION__ })}</p>
    </>
  );
}

function GroupSelect({ groups, value, onChange }: { groups: Group[]; value: number | null; onChange: (id: number | null) => void }) {
  const t = useI18n().t;
  if (!groups.length) return null;
  return (
    <label className="field">
      <span>{t('habits.group')}</span>
      <select value={value ?? ''} onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}>
        <option value="">{t('habits.group.none')}</option>
        {groups.map((group) => (
          <option key={group.id} value={group.id}>
            {group.name}
          </option>
        ))}
      </select>
    </label>
  );
}

const NEW_GOAL: Goal = { goal_type: 'days', target: null, weekdays: 127 };

function NewHabitForm({ groups }: { groups: Group[] }) {
  const { today } = useSession();
  const t = useI18n().t;
  const errorText = useErrorText();
  const action = useHabitAction();
  const [name, setName] = useState('');
  const [cue, setCue] = useState('');
  const [goal, setGoal] = useState<Goal>(NEW_GOAL);
  const [unit, setUnit] = useState('');
  const [color, setColor] = useState<HabitColor | null>(null);
  const [groupId, setGroupId] = useState<number | null>(null);
  const [startOn, setStartOn] = useState(today);
  const [reminders, setReminders] = useState<string[]>([]);
  const valid = goalValid(goal) && timesValid(reminders);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!valid) return;
    action.mutate(
      {
        type: 'create',
        body: {
          name,
          cue: cue || null,
          ...goal,
          unit: goal.goal_type === 'quantity' ? unit || null : null,
          color,
          group_id: groupId,
          reminders: normalizeTimes(reminders),
          start_on: startOn,
        },
      },
      {
        onSuccess: () => {
          setName('');
          setCue('');
          setGoal(NEW_GOAL);
          setUnit('');
          setReminders([]);
        },
      },
    );
  };

  return (
    <form className="card habit-form" onSubmit={submit} aria-labelledby="new-heading">
      <h2 id="new-heading">{t('habits.new')}</h2>
      <label className="field">
        <span>{t('habits.name')}</span>
        <input
          required
          maxLength={120}
          value={name}
          placeholder={t('habits.namePlaceholder')}
          onChange={(e) => setName(e.target.value)}
        />
      </label>
      <label className="field">
        <span>{t('habits.cue')}</span>
        <input
          maxLength={200}
          value={cue}
          placeholder={t('habits.cuePlaceholder')}
          onChange={(e) => setCue(e.target.value)}
        />
      </label>
      <GoalFields value={goal} unit={unit} onChange={setGoal} onUnitChange={setUnit} />
      <ColorPicker value={color} onChange={setColor} />
      <GroupSelect groups={groups} value={groupId} onChange={setGroupId} />
      <ReminderTimes value={reminders} onChange={setReminders} />
      <label className="field">
        <span>{t('habits.startsOn')}</span>
        <input type="date" required value={startOn} onChange={(e) => setStartOn(e.target.value)} />
      </label>
      {action.isError && <p role="alert" className="error">{errorText(action.error)}</p>}
      <button type="submit" className="button primary" disabled={action.isPending || !valid}>
        {t('habits.create')}
      </button>
    </form>
  );
}

function goalSummary(habit: Habit, t: ReturnType<typeof useI18n>['t'], weekdays: (mask: number) => string): string {
  if (habit.goal_type === 'weekly_count') return t('habits.summary.weekly_count', { target: habit.target ?? 1 });
  if (habit.goal_type === 'quantity') {
    const amount = habit.unit
      ? t('habits.summary.quantityUnit', { target: habit.target ?? 1, unit: habit.unit })
      : t('habits.summary.quantity', { target: habit.target ?? 1 });
    return habit.weekdays === 127 ? amount : `${amount}, ${weekdays(habit.weekdays)}`;
  }
  return weekdays(habit.weekdays);
}

function HabitItem({
  habit,
  groups,
  onUp,
  onDown,
}: {
  habit: Habit;
  groups: Group[];
  onUp?: () => void;
  onDown?: () => void;
}) {
  const { today } = useSession();
  const { t, format } = useI18n();
  const errorText = useErrorText();
  const action = useHabitAction();
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: habit.id });
  const [editing, setEditing] = useState(false);
  const [shortcut, setShortcut] = useState(false);
  const [name, setName] = useState(habit.name);
  const [cue, setCue] = useState(habit.cue ?? '');
  const current: Goal = { goal_type: habit.goal_type, target: habit.target, weekdays: habit.weekdays };
  const [goal, setGoal] = useState<Goal>(current);
  const [unit, setUnit] = useState(habit.unit ?? '');
  const [color, setColor] = useState<HabitColor | null>(habit.color);
  const [groupId, setGroupId] = useState<number | null>(habit.group_id);
  const [validFrom, setValidFrom] = useState(today);
  const [reminders, setReminders] = useState<string[]>(habit.reminders);
  const goalChanged = !sameGoal(goal, current);
  const valid = goalValid(goal) && timesValid(reminders);

  const startEdit = () => {
    setName(habit.name);
    setCue(habit.cue ?? '');
    setGoal(current);
    setUnit(habit.unit ?? '');
    setColor(habit.color);
    setGroupId(habit.group_id);
    setValidFrom(today);
    setReminders(habit.reminders);
    setEditing(true);
  };

  const save = async (event: FormEvent) => {
    event.preventDefault();
    if (!valid) return;
    try {
      const details = {
        name,
        cue: cue || null,
        unit: goal.goal_type === 'quantity' ? unit || null : habit.unit,
        color,
        group_id: groupId,
        reminders: normalizeTimes(reminders),
      };
      const changed =
        details.name !== habit.name ||
        details.cue !== habit.cue ||
        details.unit !== habit.unit ||
        details.color !== habit.color ||
        details.group_id !== habit.group_id ||
        !sameTimes(details.reminders, habit.reminders);
      if (changed) await action.mutateAsync({ type: 'update', id: habit.id, body: details });
      if (goalChanged) {
        await action.mutateAsync({ type: 'schedule', id: habit.id, body: { ...goal, valid_from: validFrom } });
      }
      setEditing(false);
    } catch {
      // action.error shows the message
    }
  };

  const style = {
    ...colorStyle(habit.color),
    transform: CSS.Transform.toString(transform),
    transition,
  };

  if (editing) {
    return (
      <li className="habit-item" ref={setNodeRef} style={style}>
        <form className="habit-form" onSubmit={save} aria-label={t('habits.editLabel', { name: habit.name })}>
          <label className="field">
            <span>{t('habits.name')}</span>
            <input required maxLength={120} value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="field">
            <span>{t('habits.cue')}</span>
            <input maxLength={200} value={cue} onChange={(e) => setCue(e.target.value)} />
          </label>
          <GoalFields value={goal} unit={unit} onChange={setGoal} onUnitChange={setUnit} />
          {goalChanged && (
            <label className="field">
              <span>{t('habits.newPlanFrom')}</span>
              <input type="date" required value={validFrom} onChange={(e) => setValidFrom(e.target.value)} />
              <small className="subtle">{t('habits.newPlanHint')}</small>
            </label>
          )}
          <ColorPicker value={color} onChange={setColor} />
          <GroupSelect groups={groups} value={groupId} onChange={setGroupId} />
          <ReminderTimes value={reminders} onChange={setReminders} />
          {action.isError && <p role="alert" className="error">{errorText(action.error)}</p>}
          <div className="button-row">
            <button type="submit" className="button primary" disabled={action.isPending || !valid}>
              {t('common.save')}
            </button>
            <button type="button" className="button" onClick={() => setEditing(false)}>
              {t('common.cancel')}
            </button>
          </div>
        </form>
      </li>
    );
  }

  const group = groups.find((g) => g.id === habit.group_id);
  return (
    <li
      className={`habit-item${isDragging ? ' is-dragging' : ''}`}
      ref={setNodeRef}
      style={style}
    >
      <button
        type="button"
        className="button icon drag-handle"
        aria-label={t('habits.dragHandle', { name: habit.name })}
        {...attributes}
        {...listeners}
      >
        <GripIcon />
      </button>
      <div className="habit-summary">
        <span className="habit-title">{habit.name}</span>
        <span className="subtle">
          {goalSummary(habit, t, format.weekdays)}
          {group && <> · {group.name}</>}
          {habit.cue && <> · {habit.cue}</>}
          {habit.reminders.length > 0 && (
            <>
              {' · '}
              {t('reminders.summary', { times: habit.reminders.join(', ') })}
            </>
          )}
        </span>
      </div>
      <div className="button-row">
        <button
          type="button"
          className="button icon"
          disabled={!onUp}
          onClick={onUp}
          aria-label={t('habits.moveUp', { name: habit.name })}
        >
          <ArrowUpIcon />
        </button>
        <button
          type="button"
          className="button icon"
          disabled={!onDown}
          onClick={onDown}
          aria-label={t('habits.moveDown', { name: habit.name })}
        >
          <ArrowDownIcon />
        </button>
        <button type="button" className="button" onClick={startEdit}>
          {t('habits.edit')}
        </button>
        <button type="button" className="button" aria-expanded={shortcut} onClick={() => setShortcut(!shortcut)}>
          {t('habits.shortcut')}
        </button>
        <button
          type="button"
          className="button"
          onClick={() => action.mutate({ type: 'archive', id: habit.id })}
          aria-label={t('habits.archiveLabel', { name: habit.name })}
        >
          {t('habits.archive')}
        </button>
      </div>
      {shortcut && <ShortcutPanel habit={habit} />}
    </li>
  );
}
