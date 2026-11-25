import { useEffect, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { PUSH_DEVICES_KEY, usePushConfig, usePushDevices } from '../../hooks/usePush';
import { useErrorText, useI18n } from '../../i18n/context';
import { apiFetch } from '../../lib/api';
import {
  PermissionDeniedError,
  browserEnvironment,
  disablePush,
  enablePush,
  localSubscription,
  pushState,
  pushSupport,
  registerSubscription,
} from '../../lib/push';

function currentPermission(): NotificationPermission | null {
  return typeof Notification === 'undefined' ? null : Notification.permission;
}

/** Turn reminders on or off for this device, send a test, and see every device that gets them. */
export function RemindersSection() {
  const { t, format } = useI18n();
  const errorText = useErrorText();
  const queryClient = useQueryClient();
  const config = usePushConfig();
  const enabled = config.data?.enabled === true;
  const devices = usePushDevices(enabled);
  const [support] = useState(() => pushSupport(browserEnvironment()));
  const [permission, setPermission] = useState(currentPermission);
  // This device's entry on the server; null = reminders are off here
  const [currentId, setCurrentId] = useState<number | null>(null);
  const [checked, setChecked] = useState(support !== 'supported');
  const refresh = () => queryClient.invalidateQueries({ queryKey: PUSH_DEVICES_KEY });

  useEffect(() => {
    if (!enabled || support !== 'supported') return;
    let cancelled = false;
    // An existing subscription is registered again: it heals the server's list and tells
    // which entry is this device
    (async () => {
      try {
        const subscription = await localSubscription();
        if (subscription && currentPermission() === 'granted') {
          const device = await registerSubscription(subscription);
          if (!cancelled) setCurrentId(device.id);
          await queryClient.invalidateQueries({ queryKey: PUSH_DEVICES_KEY });
        }
      } catch {
        // Shown as "off"; turning it on again repairs it
      } finally {
        if (!cancelled) setChecked(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [enabled, support, queryClient]);

  const turnOn = useMutation({
    mutationFn: () => enablePush(config.data?.public_key ?? ''),
    onSuccess: (device) => {
      setCurrentId(device.id);
      setPermission(currentPermission());
      void refresh();
    },
    onError: () => setPermission(currentPermission()),
  });
  const turnOff = useMutation({
    mutationFn: () => disablePush(currentId),
    onSuccess: () => {
      setCurrentId(null);
      void refresh();
    },
  });
  const test = useMutation({
    mutationFn: (id: number) => apiFetch<void>(`/v1/push/subscriptions/${id}/test`, { method: 'POST' }),
    onSettled: refresh,
  });
  const remove = useMutation({
    mutationFn: (id: number) =>
      id === currentId ? disablePush(id) : apiFetch<void>(`/v1/push/subscriptions/${id}`, { method: 'DELETE' }),
    onSuccess: (_, id) => {
      if (id === currentId) setCurrentId(null);
      void refresh();
    },
  });

  if (!enabled) return null;
  const state = pushState(support, permission, currentId != null);
  const busy = !checked || turnOn.isPending || turnOff.isPending;
  const failed = [turnOn, turnOff, remove].find((mutation) => mutation.isError);

  return (
    <section aria-labelledby="reminders-heading">
      <h2 id="reminders-heading">{t('push.title')}</h2>
      <p className="subtle">{t('push.intro')}</p>
      <div className="card habit-form">
        <p>
          <strong>{t('push.thisDevice')}</strong> {checked ? t(`push.state.${state}`) : t('app.loading')}
        </p>
        {state === 'ios-needs-install' && <p className="subtle">{t('push.iosHint')}</p>}
        {state === 'denied' && <p className="subtle">{t('push.deniedHint')}</p>}
        {turnOn.error instanceof PermissionDeniedError ? (
          <p className="error" role="alert">{t('push.permissionNotGiven')}</p>
        ) : (
          failed && <p className="error" role="alert">{errorText(failed.error)}</p>
        )}
        {test.isSuccess && <p role="status">{t('push.testSent')}</p>}
        {test.isError && <p className="error" role="alert">{errorText(test.error)}</p>}
        <div className="actions">
          {state === 'off' && (
            <button type="button" className="button primary" disabled={busy} onClick={() => turnOn.mutate()}>
              {t('push.turnOn')}
            </button>
          )}
          {state === 'on' && currentId != null && (
            <>
              <button type="button" className="button" disabled={test.isPending} onClick={() => test.mutate(currentId)}>
                {t('push.test')}
              </button>
              <button type="button" className="button" disabled={busy} onClick={() => turnOff.mutate()}>
                {t('push.turnOff')}
              </button>
            </>
          )}
        </div>
      </div>
      {(devices.data ?? []).length > 0 && (
        <>
          <h3 id="reminder-devices-heading">{t('push.devices')}</h3>
          <ul className="token-list card" aria-labelledby="reminder-devices-heading">
            {(devices.data ?? []).map((device) => {
              const name = device.device ?? t('account.unknownDevice');
              return (
                <li key={device.id}>
                  <span>
                    <strong>{name}</strong>
                    {device.id === currentId && <> ({t('account.thisDevice')})</>}
                    <span className="subtle">
                      {' · '}
                      {device.last_error
                        ? t('push.lastError', { error: device.last_error })
                        : device.last_success_at
                          ? t('push.lastSent', { date: format.dateTime(device.last_success_at) })
                          : t('push.since', { date: format.dateTime(device.created_at) })}
                    </span>
                  </span>
                  <button
                    type="button"
                    className="button"
                    disabled={remove.isPending}
                    onClick={() => remove.mutate(device.id)}
                    aria-label={t('push.removeLabel', { device: name })}
                  >
                    {t('push.remove')}
                  </button>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </section>
  );
}
