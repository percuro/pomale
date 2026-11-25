export type DayState = 'not_planned' | 'open' | 'done' | 'extra_done' | 'future';

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
}

export interface Schedule {
  valid_from: string;
  weekdays: number;
}

export interface Habit {
  id: number;
  name: string;
  cue: string | null;
  sort_order: number;
  archived_on: string | null;
  weekdays: number;
  schedules: Schedule[];
}

export interface Day {
  date: string;
  state: DayState;
  planned: boolean;
  done: boolean;
  version: number;
  /** changed locally, waiting for the server to confirm */
  pending?: boolean;
  /** the server has a different state meanwhile */
  conflict?: boolean;
}

export interface HabitDays {
  id: number;
  name: string;
  cue: string | null;
  archived: boolean;
  days: Day[];
  quota: { done: number; due: number };
}

export interface DaysResponse {
  today: string;
  timezone: string;
  start: string;
  end: string;
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
}

/** GET /v1/meta: public facts for the signed-out pages */
export interface Meta {
  version: string;
  registration: 'invite' | 'open';
  setup_needed: boolean;
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
