/**
 * Settings: connect real ad accounts, choose the model, and inspect system state.
 *
 * The Google Ads panel is the path from synthetic demo data to real insights.
 * Credentials are posted to the server and held in server-side custody — the
 * browser never stores or re-reads them, it only sees masked status.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../api';
import { useHelm } from '../store';
import { Button, Chip, Icon, Spinner } from '../components/ui';
import { ContextBar } from '../components/Shell';

export function SettingsScreen() {
  const { health, refreshOverview } = useHelm();
  const [connections, setConnections] = useState(null);
  const [verified, setVerified] = useState(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState(null);

  const refresh = useCallback(async () => {
    try {
      setConnections(await api.connections());
    } catch (err) {
      setNotice({ tone: 'error', text: err.message });
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const verify = async () => {
    setBusy(true);
    setNotice(null);
    try {
      const result = await api.verifyConnections();
      setVerified(result.platforms);
      refreshOverview();
    } catch (err) {
      setNotice({ tone: 'error', text: err.message });
    } finally {
      setBusy(false);
    }
  };

  const afterSave = (result) => {
    setConnections(result);
    setNotice({ tone: 'success', text: 'Credentials saved in server-side custody.' });
    refreshOverview();
    verify();
  };

  return (
    <>
      <ContextBar title="Settings" subtitle="Connect live ad accounts and inspect system state" />
      <div className="p-4 sm:p-7 max-w-[1100px]">

      {notice && (
        <div
          className={`rounded-xl p-3 mb-5 flex gap-2 text-body-sm ${
            notice.tone === 'error'
              ? 'border border-error/30 bg-error-container text-on-error-container'
              : 'border border-green-200 bg-green-50 text-green-800'
          }`}
        >
          <Icon name={notice.tone === 'error' ? 'error' : 'check_circle'} size={18} fill />
          {notice.text}
        </div>
      )}

      <SystemPanel health={health} />

      <GoogleAdsPanel
        status={connections?.google_ads}
        verified={verified?.google_ads}
        onSaved={afterSave}
      />

      <MetaAdsPanel status={connections?.meta_ads} verified={verified?.meta_ads} onSaved={afterSave} />
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ */

function SystemPanel({ health }) {
  if (!health) return null;
  return (
    <Panel icon="monitor_heart" title="System" subtitle="Live state of the gateway and data path.">
      <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-3">
        <Row label="Gateway mode">
          <Chip label={health.gateway_mode} />
        </Row>
        <Row label="Active model">
          <span className="font-mono text-body-sm">{health.active_model}</span>
        </Row>
        <Row label="Campaign data source">
          <Chip label={health.data_source} />
        </Row>
        <Row label="Write mode">
          <Chip label={health.dry_run ? 'Dry run' : 'LIVE WRITES'} />
        </Row>
      </dl>

      {health.gateway_mode === 'replay' ? (
        <Note icon="warning" tone="warn">
          No Anthropic API key is reachable, so agent reasoning is unavailable and narratives fall
          back to deterministic templates. Metrics, compliance verdicts, and budget math are still
          computed for real. Set{' '}
          <code className="font-mono text-[11px] bg-surface-container px-1 py-0.5 rounded">
            ANTHROPIC_API_KEY
          </code>{' '}
          in <code className="font-mono text-[11px]">.env</code> and restart.
        </Note>
      ) : (
        <Note icon="auto_awesome">
          Agents reason with Claude on every task — no cheaper tier is substituted. The model is
          fixed by design: HELM&apos;s outputs drive real budget decisions, so the choice is not a
          per-request setting.
        </Note>
      )}
      {!health.dry_run && (
        <Note icon="warning" tone="warn">
          Live write mode is on. Approved budget changes will be dispatched to the real ad
          platforms.
        </Note>
      )}
    </Panel>
  );
}

function GoogleAdsPanel({ status, verified, onSaved }) {
  const [form, setForm] = useState({
    client_id: '',
    client_secret: '',
    refresh_token: '',
    developer_token: '',
    customer_id: '',
    login_customer_id: '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState(false);

  const startOAuth = async () => {
    setError(null);
    try {
      const { auth_url } = await api.googleOAuthStart();
      window.open(auth_url, '_blank', 'noopener');
    } catch (err) {
      setError(err.message);
    }
  };

  const save = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      onSaved(await api.saveGoogleConnection(form));
      setForm((prev) => ({ ...prev, client_secret: '', refresh_token: '', developer_token: '' }));
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Panel
      icon="ads_click"
      title="Google Ads"
      subtitle="Connect a real account to replace synthetic data with live campaign metrics."
      badge={<ConnectionBadge status={status} verified={verified} />}
    >
      {verified?.connected && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-3 mb-4 text-body-sm text-green-800">
          <p className="font-semibold flex items-center gap-1.5">
            <Icon name="check_circle" size={16} fill /> Live handshake succeeded
          </p>
          <p className="mt-1">
            {verified.descriptive_name || 'Account'} · customer {verified.customer_id}
            {verified.currency_code ? ` · ${verified.currency_code}` : ''}
          </p>
        </div>
      )}
      {verified && !verified.connected && (
        <div className="rounded-lg border border-error/30 bg-error-container p-3 mb-4 text-body-sm text-on-error-container">
          <p className="font-semibold">Connection failed</p>
          <p className="mt-1 break-words">{verified.reason}</p>
        </div>
      )}

      <ol className="text-body-sm text-on-surface-variant space-y-1.5 mb-4 list-decimal list-inside leading-relaxed">
        <li>
          In Google Cloud Console, create an OAuth client (type <em>Web application</em>) with the
          redirect URI{' '}
          <code className="font-mono text-[11px] bg-surface-container px-1 py-0.5 rounded">
            {window.location.origin}/api/oauth/google/callback
          </code>
        </li>
        <li>
          Put <code className="font-mono text-[11px]">GOOGLE_OAUTH_CLIENT_ID</code> and{' '}
          <code className="font-mono text-[11px]">GOOGLE_OAUTH_CLIENT_SECRET</code> in{' '}
          <code className="font-mono text-[11px]">.env</code>, then restart the server.
        </li>
        <li>Run the consent flow below to capture a refresh token.</li>
        <li>
          Add your developer token (Google Ads API Center) and customer ID, then verify the
          connection.
        </li>
      </ol>

      <Button variant="secondary" icon="open_in_new" onClick={startOAuth} className="mb-4">
        Start Google consent flow
      </Button>

      <button
        onClick={() => setExpanded((open) => !open)}
        className="flex items-center gap-1.5 text-body-sm font-medium text-primary hover:underline mb-3 focus-ring rounded"
      >
        <Icon name={expanded ? 'expand_less' : 'expand_more'} size={18} />
        {expanded ? 'Hide manual credential entry' : 'Enter credentials manually'}
      </button>

      {expanded && (
        <form onSubmit={save} className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field
              label="Client ID"
              value={form.client_id}
              onChange={(v) => setForm({ ...form, client_id: v })}
              placeholder="…apps.googleusercontent.com"
            />
            <Field
              label="Client secret"
              type="password"
              value={form.client_secret}
              onChange={(v) => setForm({ ...form, client_secret: v })}
            />
            <Field
              label="Refresh token"
              type="password"
              value={form.refresh_token}
              onChange={(v) => setForm({ ...form, refresh_token: v })}
              hint="Captured by the consent flow above"
            />
            <Field
              label="Developer token"
              type="password"
              value={form.developer_token}
              onChange={(v) => setForm({ ...form, developer_token: v })}
              hint="Google Ads API Center"
            />
            <Field
              label="Customer ID"
              value={form.customer_id}
              onChange={(v) => setForm({ ...form, customer_id: v })}
              placeholder="123-456-7890"
            />
            <Field
              label="Login customer ID"
              value={form.login_customer_id}
              onChange={(v) => setForm({ ...form, login_customer_id: v })}
              hint="Only if the account sits under an MCC"
            />
          </div>

          {error && <p className="text-body-sm text-error">{error}</p>}

          <Button type="submit" icon="save" disabled={saving}>
            {saving ? 'Saving…' : 'Save Google Ads credentials'}
          </Button>
        </form>
      )}
    </Panel>
  );
}

function MetaAdsPanel({ status, verified, onSaved }) {
  const [form, setForm] = useState({ access_token: '', ad_account_id: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const save = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      onSaved(await api.saveMetaConnection(form));
      setForm({ access_token: '', ad_account_id: form.ad_account_id });
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Panel
      icon="thumb_up"
      title="Meta Ads"
      subtitle="Paste a Graph API access token and the ad account it belongs to."
      badge={<ConnectionBadge status={status} verified={verified} />}
    >
      {verified && !verified.connected && (
        <div className="rounded-lg border border-error/30 bg-error-container p-3 mb-4 text-body-sm text-on-error-container">
          <p className="font-semibold">Connection failed</p>
          <p className="mt-1 break-words">{verified.reason}</p>
        </div>
      )}
      {verified?.connected && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-3 mb-4 text-body-sm text-green-800">
          <p className="font-semibold flex items-center gap-1.5">
            <Icon name="check_circle" size={16} fill /> Connected
          </p>
          <p className="mt-1">
            {verified.name} · {verified.ad_account_id}
            {verified.currency ? ` · ${verified.currency}` : ''}
          </p>
        </div>
      )}

      <form onSubmit={save} className="space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field
            label="Access token"
            type="password"
            value={form.access_token}
            onChange={(v) => setForm({ ...form, access_token: v })}
          />
          <Field
            label="Ad account ID"
            value={form.ad_account_id}
            onChange={(v) => setForm({ ...form, ad_account_id: v })}
            placeholder="act_1234567890"
          />
        </div>
        {error && <p className="text-body-sm text-error">{error}</p>}
        <Button type="submit" icon="save" disabled={saving}>
          {saving ? 'Saving…' : 'Save Meta credentials'}
        </Button>
      </form>
    </Panel>
  );
}

/* ------------------------------------------------------------------ */

function Panel({ icon, title, subtitle, badge, children }) {
  return (
    <section className="card p-5 mb-5">
      <header className="flex items-start gap-3 mb-4">
        <span className="w-9 h-9 rounded-lg bg-surface-container text-on-surface-variant flex items-center justify-center shrink-0">
          <Icon name={icon} size={20} />
        </span>
        <div className="flex-1 min-w-0">
          <h2 className="font-headline text-headline-md text-on-surface">{title}</h2>
          {subtitle && <p className="text-body-sm text-on-surface-variant mt-0.5">{subtitle}</p>}
        </div>
        {badge}
      </header>
      {children}
    </section>
  );
}

function ConnectionBadge({ status, verified }) {
  if (verified?.connected) return <Chip label="Verified" />;
  if (verified && !verified.connected) return <Chip label="Failed" />;
  if (status?.connected) return <Chip label="Credentials stored" />;
  return <Chip label="Not connected" />;
}

function Row({ label, children }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-outline-variant/25 pb-2">
      <dt className="text-body-sm text-outline">{label}</dt>
      <dd className="text-body-sm font-medium text-on-surface">{children}</dd>
    </div>
  );
}

function Field({ label, value, onChange, type = 'text', placeholder, hint }) {
  return (
    <label className="block">
      <span className="rail-label block mb-1">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        autoComplete="off"
        className="w-full bg-surface-container-low border border-outline-variant/40 rounded-lg px-3 py-2 text-body-sm text-on-surface placeholder:text-outline focus-ring focus:border-primary/50"
      />
      {hint && <span className="block text-[11px] text-outline mt-1">{hint}</span>}
    </label>
  );
}

function Note({ icon, tone = 'info', children }) {
  return (
    <p
      className={`mt-4 rounded-lg p-3 text-body-sm flex gap-2 leading-relaxed ${
        tone === 'warn'
          ? 'bg-amber-50 border border-amber-200 text-amber-800'
          : 'bg-surface-container-low border border-outline-variant/30 text-on-surface-variant'
      }`}
    >
      <Icon name={icon} size={16} className="shrink-0 mt-0.5" fill />
      <span>{children}</span>
    </p>
  );
}
