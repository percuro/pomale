/** The device's time zone, e.g. "Europe/Berlin" (null if the browser does not say). */
export function browserTimeZone(): string | null {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || null;
  } catch {
    return null;
  }
}
