export type DayState = 'not_planned' | 'open' | 'done' | 'extra_done' | 'future' | 'paused' | 'partial';

/** days: on chosen weekdays; weekly_count: n times a week, any day; quantity: an amount per day */
export type GoalType = 'days' | 'weekly_count' | 'quantity';

/** Keys of the fixed palette; the colours themselves live in index.css (--habit-<key>) */
export const HABIT_COLORS = ['slate', 'red', 'orange', 'amber', 'green', 'teal', 'blue', 'purple', 'pink'] as const;
export type HabitColor = (typeof HABIT_COLORS)[number];

export type Role = 'admin' | 'user';
export type Locale = 'de' | 'en';

export interface Me {
  id: number;
  username: string;
  display_name: string | null;
  role: Role;
  /** effective time zone: "today" is computed in it */
  timezone: string;
  /** the account's own setting; null = server default */
  timezone_setting: string | null;
  /** the server's DEFAULT_TIMEZONE, used while timezone_setting is null */
  default_timezone: string;
  /** null = the browser language decides */
  locale: Locale | null;
  today: string;
  /** false: the account signs in through OIDC only */
  has_password: boolean;
  /** null = not linked to the OIDC provider */
  oidc: OidcLink | null;
}

/** What the provider told us at the last sign-in; for display only */
export interface OidcLink {
  email: string | null;
  preferred_username: string | null;
  linked_at: string;
}

export interface Schedule {
  valid_from: string;
  weekdays: number;
  goal_type: GoalType;
  target: number | null;
}

export interface Habit {
  id: number;
  name: string;
  cue: string | null;
  sort_order: number;
  archived_on: string | null;
  /** the plan in effect today (or the last one) */
  weekdays: number;
  goal_type: GoalType;
  target: number | null;
  unit: string | null;
  color: HabitColor | null;
  group_id: number | null;
  /** Local reminder times "HH:MM" in the account's time zone, sorted */
  reminders: string[];
  schedules: Schedule[];
}

export interface PushConfig {
  enabled: boolean;
  /** applicationServerKey (base64url); null when the server has reminders turned off */
  public_key: string | null;
}

/** A device (browser) that receives reminders */
export interface PushDevice {
  id: number;
  device: string | null;
  created_at: string;
  last_success_at: string | null;
  last_error: string | null;
  /** Registered from this login session */
  current: boolean;
}

export interface Group {
  id: number;
  name: string;
  sort_order: number;
}

export interface Pause {
  id: number;
  /** null = all habits */
  habit_id: number | null;
  start_on: string;
  end_on: string;
  reason: string | null;
}

/**
 * One day of one habit. goal_type, target, planned, paused, done and value are the raw
 * input of the evaluation (lib/evaluate.ts), so offline changes can be re-evaluated.
 */
export interface Day {
  date: string;
  state: DayState;
  planned: boolean;
  /** days and weekly goals: checked off; quantity goals: target reached */
  done: boolean;
  version: number;
  goal_type: GoalType;
  /** quantity: per day; weekly goal: this week's target (reduced for pauses) */
  target: number | null;
  paused: boolean;
  /** quantity goals only */
  value: number | null;
  note: string | null;
  /** changed locally, waiting for the server to confirm */
  pending?: boolean;
  /** the server has a different state meanwhile */
  conflict?: boolean;
}

export interface Quota {
  done: number;
  due: number;
}

export interface HabitDays {
  id: number;
  name: string;
  cue: string | null;
  archived: boolean;
  /** the plan in effect today */
  goal_type: GoalType;
  target: number | null;
  unit: string | null;
  color: HabitColor | null;
  group_id: number | null;
  days: Day[];
  quota: Quota;
  /** weekly goals: progress in the week that contains today */
  week: { done: number; target: number } | null;
}

export interface DaysResponse {
  today: string;
  timezone: string;
  start: string;
  end: string;
  groups: Group[];
  habits: HabitDays[];
  /** from local storage, server not reachable */
  offline?: boolean;
}

export interface CheckinResponse {
  habit_id: number;
  date: string;
  done: boolean;
  state: DayState;
  version: number;
  value: number | null;
}

export interface HistoryWeek {
  week_start: string;
  done: number;
  due: number;
}

export interface HistoryDay {
  date: string;
  state: DayState;
  value: number | null;
  note: string | null;
}

export interface HistoryHabit {
  id: number;
  name: string;
  archived: boolean;
  goal_type: GoalType;
  target: number | null;
  unit: string | null;
  color: HabitColor | null;
  group_id: number | null;
  quota: Quota;
  weeks: HistoryWeek[];
  /** only when asking for one habit */
  days: HistoryDay[] | null;
}

export interface HistoryResponse {
  today: string;
  start: string;
  end: string;
  habits: HistoryHabit[];
}

/** GET /v1/meta: public facts for the signed-out pages */
export interface Meta {
  version: string;
  registration: 'invite' | 'open';
  setup_needed: boolean;
  /** false: sign-in, registration and setup through OIDC only */
  password_login: boolean;
  /** null = OIDC not configured; label = name for the button (null = default text) */
  oidc: { label: string | null } | null;
}

export interface SessionInfo {
  id: number;
  created_at: string;
  last_seen_at: string | null;
  /** e.g. "iPhone · Safari"; null if unknown */
  device: string | null;
  current: boolean;
}

/** What an admin sees about an account (no habits, no check-ins) */
export interface AdminUser {
  id: number;
  username: string;
  display_name: string | null;
  role: Role;
  is_active: boolean;
  created_at: string;
  last_seen_at: string | null;
  has_password: boolean;
  oidc_linked: boolean;
}

export interface AuditEvent {
  id: number;
  created_at: string;
  /** e.g. "auth.login"; translated as audit.<event> */
  event: string;
  actor_user_id: number | null;
  actor_username: string | null;
  target_user_id: number | null;
  target_username: string | null;
  /** shortened, only for failed logins and rate-limit blocks */
  ip_prefix: string | null;
  details: Record<string, string | number | boolean | null>;
}

export interface AuditPage {
  events: AuditEvent[];
  /** pass as before_id for older entries; null = no more */
  next_before_id: number | null;
}

export type InvitationPurpose = 'signup' | 'password_reset';

export interface InvitationCreated {
  id: number;
  purpose: InvitationPurpose;
  /** Shown only once */
  url: string;
  expires_at: string;
}

export interface Invitation {
  id: number;
  purpose: InvitationPurpose;
  role: Role | null;
  note: string | null;
  target_username: string | null;
  created_by_username: string | null;
  created_at: string;
  expires_at: string;
}

export interface InvitationInfo {
  purpose: InvitationPurpose;
  username: string | null;
  expires_at: string;
}
