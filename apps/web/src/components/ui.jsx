/** Small shared primitives used across the console. */

import React from 'react';

export function Icon({ name, className = '', fill = false, size }) {
  return (
    <span
      className={`material-symbols-outlined ${fill ? 'icon-fill' : ''} ${className}`}
      style={size ? { fontSize: `${size}px` } : undefined}
      aria-hidden="true"
    >
      {name}
    </span>
  );
}

const CHIP_TONES = {
  PASS: 'bg-green-50 text-green-700 border border-green-200',
  VALID: 'bg-green-50 text-green-700 border border-green-200',
  WINNER: 'bg-green-50 text-green-700 border border-green-200',
  SCALE: 'bg-green-50 text-green-700 border border-green-200',
  COMPLETED: 'bg-green-50 text-green-700 border border-green-200',
  SUCCESS: 'bg-green-50 text-green-700 border border-green-200',

  FLAG: 'bg-amber-50 text-amber-700 border border-amber-200',
  WARN: 'bg-amber-50 text-amber-700 border border-amber-200',
  FATIGUED: 'bg-amber-50 text-amber-700 border border-amber-200',
  DEGRADED: 'bg-amber-50 text-amber-700 border border-amber-200',
  REDUCE_OR_REFRESH: 'bg-amber-50 text-amber-700 border border-amber-200',
  REVIEW: 'bg-amber-50 text-amber-700 border border-amber-200',
  PENDING_APPROVAL: 'bg-amber-50 text-amber-700 border border-amber-200',

  BLOCK: 'bg-error-container text-on-error-container border border-error/20',
  FAILED: 'bg-error-container text-on-error-container border border-error/20',
  REJECTED: 'bg-error-container text-on-error-container border border-error/20',
  'OUT OF POLICY': 'bg-error-container text-on-error-container border border-error/20',

  STABLE: 'bg-secondary-container text-on-secondary-fixed border border-outline-variant/40',
  DEFAULT: 'bg-surface-container text-on-surface-variant border border-outline-variant/40',
};

export function Chip({ label, className = '' }) {
  const key = String(label ?? '').toUpperCase().replace(/_/g, ' ');
  const tone =
    CHIP_TONES[String(label ?? '').toUpperCase()] || CHIP_TONES[key] || CHIP_TONES.DEFAULT;
  return <span className={`chip ${tone} ${className}`}>{key || '—'}</span>;
}

export function SectionTitle({ children, className = '' }) {
  return (
    <h3 className={`font-headline text-headline-md text-on-surface ${className}`}>{children}</h3>
  );
}

export function Spinner({ className = '' }) {
  return (
    <span
      className={`inline-block w-3.5 h-3.5 rounded-full border-2 border-current border-t-transparent animate-spin ${className}`}
      role="status"
      aria-label="Loading"
    />
  );
}

export function EmptyState({ icon, title, body, action }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-16 px-6">
      <div className="w-14 h-14 rounded-2xl bg-surface-container flex items-center justify-center text-outline mb-4">
        <Icon name={icon} size={28} />
      </div>
      <p className="font-headline text-headline-md text-on-surface mb-1">{title}</p>
      {body && <p className="text-body-sm text-on-surface-variant max-w-sm">{body}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function Button({
  children,
  variant = 'primary',
  size = 'md',
  icon,
  className = '',
  ...props
}) {
  const variants = {
    primary: 'bg-primary text-on-primary hover:bg-on-primary-fixed-variant disabled:bg-outline/40',
    secondary:
      'bg-surface-container-lowest text-on-surface border border-outline-variant/50 hover:bg-surface-container-low',
    ghost: 'text-on-surface-variant hover:bg-surface-container-low',
    success: 'bg-green-600 text-white hover:bg-green-700',
    danger: 'bg-error text-on-error hover:bg-on-error-container',
  };
  const sizes = { sm: 'px-3 py-1.5 text-body-sm', md: 'px-4 py-2 text-body-md' };

  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-lg font-headline font-semibold transition-colors focus-ring disabled:cursor-not-allowed disabled:opacity-60 ${variants[variant]} ${sizes[size]} ${className}`}
      {...props}
    >
      {icon && <Icon name={icon} size={18} />}
      {children}
    </button>
  );
}

/** Indian-grouped rupee formatting, matching the backend's `_inr`. */
export function formatINR(amount) {
  const value = Number(amount);
  if (!Number.isFinite(value)) return String(amount ?? '—');

  const sign = value < 0 ? '-' : '';
  const whole = Math.round(Math.abs(value)).toString();
  if (whole.length <= 3) return `${sign}₹${whole}`;

  const tail = whole.slice(-3);
  let head = whole.slice(0, -3);
  const groups = [];
  while (head.length > 2) {
    groups.unshift(head.slice(-2));
    head = head.slice(0, -2);
  }
  if (head) groups.unshift(head);
  return `${sign}₹${groups.join(',')},${tail}`;
}

export function formatCompact(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return String(value ?? '—');
  return num.toLocaleString('en-IN');
}

export function relativeTime(iso) {
  if (!iso) return '';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const seconds = Math.round((Date.now() - then) / 1000);
  if (seconds < 60) return 'Just now';
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days === 1) return 'Yesterday';
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
}

export function formatTime(iso) {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
}
