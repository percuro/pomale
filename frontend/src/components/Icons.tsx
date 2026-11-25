/*
 * Icons of fahrma and pomale: one set, drawn on a 24 px grid with a 2 px stroke and
 * round ends; the colour comes from the text. This file is identical in both projects.
 * See docs/design-language.md.
 */
const base = {
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  'aria-hidden': true,
};

/* Places */
export const HomeIcon = () => (
  <svg {...base}><path d="M3 11l9-7 9 7" /><path d="M5 10v10h14V10" /></svg>
);
export const CalendarIcon = () => (
  <svg {...base}><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 10h18M8 3v4M16 3v4" /></svg>
);
export const ListIcon = () => (
  <svg {...base}><path d="M8 6h13M8 12h13M8 18h13" /><circle cx="3.5" cy="6" r="1" /><circle cx="3.5" cy="12" r="1" /><circle cx="3.5" cy="18" r="1" /></svg>
);
export const ScaleIcon = () => (
  <svg {...base}><path d="M12 3v18M5 7h14" /><path d="M5 7l-3 7a3 3 0 0 0 6 0z" /><path d="M19 7l-3 7a3 3 0 0 0 6 0z" /></svg>
);
export const UsersIcon = () => (
  <svg {...base}><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20a6.5 6.5 0 0 1 13 0" /><path d="M16 4.5a3.5 3.5 0 0 1 0 7M18 14a6 6 0 0 1 3.5 6" /></svg>
);
export const UserIcon = () => (
  <svg {...base}><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></svg>
);
export const CheckCircleIcon = () => (
  <svg {...base}><circle cx="12" cy="12" r="9" /><path d="M8 12.5l3 3 5-6" /></svg>
);
export const WeekIcon = () => (
  <svg {...base}><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M9 5v14M15 5v14M3 12h18" /></svg>
);
export const ChartIcon = () => (
  <svg {...base}><path d="M5 20V10M12 20V4M19 20v-7" /></svg>
);
export const ChecklistIcon = () => (
  <svg {...base}><path d="M10 6h11M10 12h11M10 18h11" /><path d="M3 6l1.5 1.5L7 5M3 12l1.5 1.5L7 11M3 18l1.5 1.5L7 17" /></svg>
);

/* Things */
export const CarIcon = () => (
  <svg {...base}><path d="M3 13l2-5.5A2 2 0 0 1 6.9 6h10.2a2 2 0 0 1 1.9 1.5L21 13" /><rect x="2" y="13" width="20" height="5" rx="1.5" /><circle cx="7" cy="18.5" r="1.5" /><circle cx="17" cy="18.5" r="1.5" /></svg>
);
export const FuelIcon = () => (
  <svg {...base}><path d="M4 21V5a2 2 0 0 1 2-2h7a2 2 0 0 1 2 2v16M3 21h13M4 10h11" /><path d="M15 8l3 2v7a1.5 1.5 0 0 0 3 0V9l-3-3" /></svg>
);
export const ReceiptIcon = () => (
  <svg {...base}><path d="M5 3h14v18l-3-2-2 2-2-2-2 2-2-2-3 2z" /><path d="M9 8h6M9 12h6" /></svg>
);
export const BoltIcon = () => (
  <svg {...base}><path d="M13 2L4 14h7l-1 8 9-12h-7z" /></svg>
);

/* Actions and states */
export const CheckIcon = () => (
  <svg {...base}><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>
);
export const PlusIcon = () => (
  <svg {...base}><path d="M12 5v14M5 12h14" /></svg>
);
export const MinusIcon = () => (
  <svg {...base}><path d="M5 12h14" /></svg>
);
export const UndoIcon = () => (
  <svg {...base}><path d="M9 14L4 9l5-5" /><path d="M4 9h10a6 6 0 0 1 0 12h-3" /></svg>
);
export const PencilIcon = () => (
  <svg {...base}><path d="M4 20h4L19.5 8.5a2.1 2.1 0 0 0-3-3L5 17v3z" /><path d="M14.5 6.5l3 3" /></svg>
);
export const ChevronLeftIcon = () => (
  <svg {...base}><path d="M15 5l-7 7 7 7" /></svg>
);
export const ChevronRightIcon = () => (
  <svg {...base}><path d="M9 5l7 7-7 7" /></svg>
);
export const ArrowUpIcon = () => (
  <svg {...base}><path d="M12 19V5M6 11l6-6 6 6" /></svg>
);
export const ArrowDownIcon = () => (
  <svg {...base}><path d="M12 5v14M6 13l6 6 6-6" /></svg>
);
export const GripIcon = () => (
  <svg {...base} fill="currentColor" stroke="none"><circle cx="9" cy="6" r="1.6" /><circle cx="15" cy="6" r="1.6" /><circle cx="9" cy="12" r="1.6" /><circle cx="15" cy="12" r="1.6" /><circle cx="9" cy="18" r="1.6" /><circle cx="15" cy="18" r="1.6" /></svg>
);
export const InfoIcon = () => (
  <svg {...base}><circle cx="12" cy="12" r="9" /><path d="M12 11v6M12 7.5v.5" /></svg>
);
export const AlertIcon = () => (
  <svg {...base}><path d="M12 3.5L2.5 20h19z" /><path d="M12 10v5M12 17.5v.5" /></svg>
);
