export type DayState = 'not_planned' | 'open' | 'done' | 'extra_done' | 'future';

export interface Me {
  username: string;
  today: string;
  timezone: string;
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
