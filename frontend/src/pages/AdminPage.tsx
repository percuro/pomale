import { useState, type FormEvent } from 'react';
import { Navigate } from 'react-router-dom';
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { APP_NAME } from '../app/brand';
import { ConfirmDialog } from '../components/common/ConfirmDialog';
import { OnlineOnly } from '../components/common/OnlineOnly';
import { ShareLink } from '../components/common/ShareLink';
import { useSession } from '../hooks/useSession';
import { useErrorText, useI18n } from '../i18n/context';
import { hasMessage } from '../i18n/core';
import { apiFetch } from '../lib/api';
import type { AdminUser, AuditEvent, AuditPage, Invitation, InvitationCreated, Role } from '../lib/types';
import { useOidcLabel } from '../hooks/useOidcLabel';

const USERS_KEY = ['admin', 'users'] as const;
const INVITATIONS_KEY = ['admin', 'invitations'] as const;
const AUDIT_KEY = ['admin', 'audit'] as const;

/** A link that was just created: shown once, then only its hash exists on the server */
interface CreatedLink extends InvitationCreated {
  username?: string;
}

export function AdminPage() {
  const { me } = useSession();
  const { t } = useI18n();
  const [created, setCreated] = useState<CreatedLink | null>(null);
  if (me.role !== 'admin') return <Navigate to="/" replace />;

  return (
    <>
      <div className="page-head">
        <h1>{t('admin.title')}</h1>
      </div>
      <OnlineOnly>
        <InviteSection created={created} onCreated={setCreated} />
        <OpenLinksSection />
        <AccountsSection onResetLink={setCreated} />
        <AuditSection />
      </OnlineOnly>
    </>
  );
}

function InviteSection({
  created,
  onCreated,
}: {
  created: CreatedLink | null;
  onCreated: (link: CreatedLink | null) => void;
}) {
  const { t } = useI18n();
  const errorText = useErrorText();
  const queryClient = useQueryClient();
  const [role, setRole] = useState<Role>('user');
  const [note, setNote] = useState('');
  const create = useMutation({
    mutationFn: () =>
      apiFetch<InvitationCreated>('/v1/admin/invitations', {
        method: 'POST',
        body: JSON.stringify({ role, note: note.trim() || null }),
      }),
    onSuccess: (link) => {
      onCreated(link);
      setNote('');
      setRole('user');
      void queryClient.invalidateQueries({ queryKey: INVITATIONS_KEY });
    },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate();
  };

  return (
    <section aria-labelledby="invite-heading">
      <h2 id="invite-heading">{t('admin.invite')}</h2>
      {created ? (
        <ShareLink
          intro={
            created.purpose === 'signup'
              ? t('admin.inviteCreated')
              : t('admin.resetCreated', { username: created.username ?? '' })
          }
          url={created.url}
          expiresAt={created.expires_at}
          shareTitle={t('admin.shareTitle', { app: APP_NAME })}
          onDone={() => onCreated(null)}
        />
      ) : (
        <form className="card habit-form" onSubmit={submit}>
          <p className="subtle">{t('admin.inviteIntro')}</p>
          <label className="field">
            <span>{t('admin.role')}</span>
            <select value={role} onChange={(e) => setRole(e.target.value as Role)}>
              <option value="user">{t('role.user')}</option>
              <option value="admin">{t('role.admin')}</option>
            </select>
          </label>
          <label className="field">
            <span>{t('admin.note')}</span>
            <input
              maxLength={80}
              value={note}
              placeholder={t('admin.notePlaceholder')}
              onChange={(e) => setNote(e.target.value)}
            />
          </label>
          {create.isError && <p className="error" role="alert">{errorText(create.error)}</p>}
          <div className="button-row">
            <button type="submit" className="button primary" disabled={create.isPending}>
              {t('admin.createInvite')}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}

function OpenLinksSection() {
  const { t, format } = useI18n();
  const errorText = useErrorText();
  const queryClient = useQueryClient();
  const invitations = useQuery({
    queryKey: INVITATIONS_KEY,
    queryFn: () => apiFetch<Invitation[]>('/v1/admin/invitations'),
  });
  const revoke = useMutation({
    mutationFn: (id: number) => apiFetch<void>(`/v1/admin/invitations/${id}`, { method: 'DELETE' }),
    onSettled: () => queryClient.invalidateQueries({ queryKey: INVITATIONS_KEY }),
  });

  const name = (invitation: Invitation) =>
    invitation.purpose === 'signup'
      ? [t('admin.purposeSignup'), invitation.note].filter(Boolean).join(' – ')
      : t('admin.purposeReset', { username: invitation.target_username ?? '' });

  return (
    <section aria-labelledby="links-heading">
      <h2 id="links-heading">{t('admin.openLinks')}</h2>
      {invitations.isPending && <p>{t('app.loading')}</p>}
      {invitations.isError && <p className="error" role="alert">{errorText(invitations.error)}</p>}
      {invitations.data?.length === 0 && <p className="subtle">{t('admin.noOpenLinks')}</p>}
      {(invitations.data ?? []).length > 0 && (
        <ul className="token-list card">
          {invitations.data!.map((invitation) => (
            <li key={invitation.id}>
              <span>
                <strong>{name(invitation)}</strong>
                <span className="subtle">
                  {' · '}
                  {t('admin.linkInfo', {
                    role: invitation.role ? t(`role.${invitation.role}`) : t('role.user'),
                    date: format.dateTime(invitation.expires_at),
                    creator: invitation.created_by_username ?? '—',
                  })}
                </span>
              </span>
              <button
                type="button"
                className="button"
                disabled={revoke.isPending}
                onClick={() => revoke.mutate(invitation.id)}
                aria-label={t('admin.revokeLabel', { name: name(invitation) })}
              >
                {t('admin.revoke')}
              </button>
            </li>
          ))}
        </ul>
      )}
      {revoke.isError && <p className="error" role="alert">{errorText(revoke.error)}</p>}
    </section>
  );
}

type Pending = { kind: 'deactivate' | 'delete' | 'unlink'; user: AdminUser } | null;

function AccountsSection({ onResetLink }: { onResetLink: (link: CreatedLink) => void }) {
  const { me } = useSession();
  const { t, format } = useI18n();
  const errorText = useErrorText();
  const queryClient = useQueryClient();
  const [pending, setPending] = useState<Pending>(null);
  const users = useQuery({ queryKey: USERS_KEY, queryFn: () => apiFetch<AdminUser[]>('/v1/admin/users') });
  const refresh = () => queryClient.invalidateQueries({ queryKey: USERS_KEY });

  const update = useMutation({
    mutationFn: ({ id, body }: { id: number; body: { role?: Role; is_active?: boolean } }) =>
      apiFetch<AdminUser>(`/v1/admin/users/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
    onSuccess: () => setPending(null),
    onSettled: refresh,
  });
  const remove = useMutation({
    mutationFn: (id: number) => apiFetch<void>(`/v1/admin/users/${id}`, { method: 'DELETE' }),
    onSuccess: () => setPending(null),
    onSettled: refresh,
  });
  const unlink = useMutation({
    mutationFn: (id: number) => apiFetch<void>(`/v1/admin/users/${id}/oidc`, { method: 'DELETE' }),
    onSuccess: () => setPending(null),
    onSettled: refresh,
  });
  const provider = useOidcLabel();
  const methods = (user: AdminUser) =>
    [user.has_password && t('admin.methodPassword'), user.oidc_linked && provider].filter(Boolean).join(' + ') ||
    t('admin.methodNone');
  const resetLink = useMutation({
    mutationFn: (user: AdminUser) =>
      apiFetch<InvitationCreated>(`/v1/admin/users/${user.id}/password-reset`, { method: 'POST' }),
    onSuccess: (link, user) => {
      onResetLink({ ...link, username: user.username });
      void queryClient.invalidateQueries({ queryKey: INVITATIONS_KEY });
      window.scrollTo({ top: 0, behavior: 'smooth' });
    },
  });

  const closeDialog = () => {
    setPending(null);
    update.reset();
    remove.reset();
    unlink.reset();
  };
  const dialogMutation = pending?.kind === 'delete' ? remove : pending?.kind === 'unlink' ? unlink : update;
  const dialogError = pending && dialogMutation.isError ? errorText(dialogMutation.error) : null;
  const inlineError = !pending && (update.error ?? remove.error ?? resetLink.error ?? unlink.error);

  return (
    <section aria-labelledby="accounts-heading">
      <h2 id="accounts-heading">{t('admin.accounts')}</h2>
      <p className="subtle">{t('admin.accountsIntro')}</p>
      {users.isPending && <p>{t('app.loading')}</p>}
      {users.isError && <p className="error" role="alert">{errorText(users.error)}</p>}
      {inlineError && <p className="error" role="alert">{errorText(inlineError)}</p>}
      <ul className="habit-list">
        {(users.data ?? []).map((user) => {
          const self = user.id === me.id;
          const label = (action: string) => t('admin.actionLabel', { action, username: user.username });
          return (
            <li key={user.id} className="habit-item">
              <div className="habit-summary">
                <span className="habit-title">
                  {user.display_name ? `${user.display_name} (${user.username})` : user.username}
                  {self && ` · ${t('admin.you')}`}
                </span>
                <span className="subtle">
                  {t(`role.${user.role}`)}
                  {!user.is_active && ` · ${t('admin.inactive')}`}
                  {' · '}
                  {t('admin.signInWith', { methods: methods(user) })}
                  {' · '}
                  {t('admin.accountInfo', {
                    created: format.dateTime(user.created_at),
                    seen: format.dateTime(user.last_seen_at),
                  })}
                </span>
              </div>
              <div className="button-row">
                <button
                  type="button"
                  className="button"
                  disabled={update.isPending}
                  aria-label={label(user.role === 'admin' ? t('admin.makeUser') : t('admin.makeAdmin'))}
                  onClick={() =>
                    update.mutate({ id: user.id, body: { role: user.role === 'admin' ? 'user' : 'admin' } })
                  }
                >
                  {user.role === 'admin' ? t('admin.makeUser') : t('admin.makeAdmin')}
                </button>
                {user.is_active ? (
                  !self && (
                    <button
                      type="button"
                      className="button"
                      aria-label={label(t('admin.deactivate'))}
                      onClick={() => setPending({ kind: 'deactivate', user })}
                    >
                      {t('admin.deactivate')}
                    </button>
                  )
                ) : (
                  <button
                    type="button"
                    className="button"
                    disabled={update.isPending}
                    aria-label={label(t('admin.reactivate'))}
                    onClick={() => update.mutate({ id: user.id, body: { is_active: true } })}
                  >
                    {t('admin.reactivate')}
                  </button>
                )}
                {user.is_active && (
                  <button
                    type="button"
                    className="button"
                    disabled={resetLink.isPending}
                    aria-label={label(t('admin.resetLink'))}
                    onClick={() => resetLink.mutate(user)}
                  >
                    {t('admin.resetLink')}
                  </button>
                )}
                {user.oidc_linked && (
                  <button
                    type="button"
                    className="button"
                    aria-label={label(t('admin.oidcUnlink'))}
                    onClick={() => setPending({ kind: 'unlink', user })}
                  >
                    {t('admin.oidcUnlink')}
                  </button>
                )}
                {!self && (
                  <button
                    type="button"
                    className="button danger"
                    aria-label={label(t('common.delete'))}
                    onClick={() => setPending({ kind: 'delete', user })}
                  >
                    {t('common.delete')}
                  </button>
                )}
              </div>
            </li>
          );
        })}
      </ul>

      <ConfirmDialog
        open={pending?.kind === 'deactivate'}
        title={t('admin.deactivateTitle', { username: pending?.user.username ?? '' })}
        confirmLabel={t('admin.deactivate')}
        danger
        busy={update.isPending}
        error={pending?.kind === 'deactivate' ? dialogError : null}
        onConfirm={() => pending && update.mutate({ id: pending.user.id, body: { is_active: false } })}
        onCancel={closeDialog}
      >
        <p>{t('admin.deactivateText', { username: pending?.user.username ?? '' })}</p>
      </ConfirmDialog>
      <ConfirmDialog
        open={pending?.kind === 'delete'}
        title={t('admin.deleteTitle', { username: pending?.user.username ?? '' })}
        confirmLabel={t('admin.deleteConfirm')}
        danger
        busy={remove.isPending}
        error={pending?.kind === 'delete' ? dialogError : null}
        onConfirm={() => pending && remove.mutate(pending.user.id)}
        onCancel={closeDialog}
      >
        <p>{t('admin.deleteText')}</p>
      </ConfirmDialog>
      <ConfirmDialog
        open={pending?.kind === 'unlink'}
        title={t('admin.oidcUnlinkTitle', { username: pending?.user.username ?? '', provider })}
        confirmLabel={t('admin.oidcUnlink')}
        danger
        busy={unlink.isPending}
        error={pending?.kind === 'unlink' ? dialogError : null}
        onConfirm={() => pending && unlink.mutate(pending.user.id)}
        onCancel={closeDialog}
      >
        <p>{t('admin.oidcUnlinkText', { username: pending?.user.username ?? '', provider })}</p>
      </ConfirmDialog>
    </section>
  );
}

const AUDIT_PAGE_SIZE = 50;

/** Details shown after the event text, e.g. "user → admin" or the key's label */
function auditDetail(event: AuditEvent, t: ReturnType<typeof useI18n>['t']): string | null {
  const d = event.details;
  const parts: string[] = [];
  if (typeof d.before === 'string' && typeof d.after === 'string') {
    parts.push(`${t(`role.${d.before as Role}`)} → ${t(`role.${d.after as Role}`)}`);
  }
  if (typeof d.method === 'string') parts.push(d.method === 'oidc' ? 'OIDC' : t('admin.methodPassword'));
  if (typeof d.label === 'string') parts.push(d.label);
  if (typeof d.count === 'number') parts.push(String(d.count));
  if (d.via === 'cli') parts.push(t('audit.viaCli'));
  if (event.ip_prefix) parts.push(event.ip_prefix);
  return parts.length ? parts.join(' · ') : null;
}

function AuditSection() {
  const { t, format } = useI18n();
  const errorText = useErrorText();
  const [userId, setUserId] = useState<number | ''>('');
  const users = useQuery({ queryKey: USERS_KEY, queryFn: () => apiFetch<AdminUser[]>('/v1/admin/users') });
  const audit = useInfiniteQuery({
    queryKey: [...AUDIT_KEY, userId],
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams({ limit: String(AUDIT_PAGE_SIZE) });
      if (pageParam) params.set('before_id', String(pageParam));
      if (userId) params.set('user_id', String(userId));
      return apiFetch<AuditPage>(`/v1/admin/audit?${params}`);
    },
    initialPageParam: 0,
    getNextPageParam: (page) => page.next_before_id ?? undefined,
  });
  const events = audit.data?.pages.flatMap((page) => page.events) ?? [];
  const text = (event: AuditEvent) => {
    const key = `audit.${event.event}`;
    const params = { actor: event.actor_username ?? t('audit.nobody'), target: event.target_username ?? '' };
    // Without a target (e.g. an unknown username): drop the empty "()" instead of showing it
    return hasMessage(key) ? t(key, params).replace(' ()', '') : event.event;
  };

  return (
    <section aria-labelledby="audit-heading">
      <h2 id="audit-heading">{t('admin.audit')}</h2>
      <p className="subtle">{t('admin.auditIntro')}</p>
      <label className="field">
        <span>{t('admin.auditFilter')}</span>
        <select value={userId} onChange={(e) => setUserId(e.target.value ? Number(e.target.value) : '')}>
          <option value="">{t('admin.auditAll')}</option>
          {(users.data ?? []).map((user) => (
            <option key={user.id} value={user.id}>
              {user.username}
            </option>
          ))}
        </select>
      </label>
      {audit.isPending && <p>{t('app.loading')}</p>}
      {audit.isError && <p className="error" role="alert">{errorText(audit.error)}</p>}
      {audit.isSuccess && events.length === 0 && <p className="subtle">{t('admin.auditEmpty')}</p>}
      {events.length > 0 && (
        <ul className="token-list card audit-list">
          {events.map((event) => {
            const detail = auditDetail(event, t);
            return (
              <li key={event.id}>
                <span>
                  <time dateTime={event.created_at} className="subtle">
                    {format.dateTime(event.created_at)}
                  </time>{' '}
                  <span className={event.event.endsWith('failed') || event.event.endsWith('limited') ? 'warn' : undefined}>
                    {text(event)}
                  </span>
                  {detail && <span className="subtle"> · {detail}</span>}
                </span>
              </li>
            );
          })}
        </ul>
      )}
      {audit.hasNextPage && (
        <div className="button-row section-actions">
          <button type="button" className="button" disabled={audit.isFetchingNextPage} onClick={() => audit.fetchNextPage()}>
            {t('admin.auditMore')}
          </button>
        </div>
      )}
    </section>
  );
}
