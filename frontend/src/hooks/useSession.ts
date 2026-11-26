import { createContext, useContext } from 'react';
import type { Me } from '../lib/types';

export interface Session {
  me: Me;
  today: string;
  /** Between midnight and a later day end: "today" is still the calendar day before */
  beforeDayEnd: boolean;
}

export const SessionContext = createContext<Session | null>(null);

export function useSession(): Session {
  const session = useContext(SessionContext);
  if (!session) throw new Error('useSession outside the signed-in app');
  return session;
}
