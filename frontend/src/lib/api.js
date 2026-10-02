import { createClient } from '@supabase/supabase-js';

export const supabase = createClient(process.env.REACT_APP_SUPABASE_URL, process.env.REACT_APP_SUPABASE_ANON_KEY);
export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export async function request(path, options = {}) {
  const { data: { session } } = await supabase.auth.getSession();
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(session ? { Authorization: `Bearer ${session.access_token}` } : {}), ...options.headers },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const message = Array.isArray(error.detail) ? error.detail.map(e => e.msg).join('. ') : error.detail;
    throw new Error(message || 'Unable to complete request. Please try again.');
  }
  return options.download ? response.blob() : response.json();
}

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url; anchor.download = filename; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const money = value => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0, notation: Math.abs(value) >= 100000 ? 'compact' : 'standard' }).format(value || 0);
export const number = value => new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(value || 0);
export const recoveryLabel = value => value == null ? 'Not reached' : `${value} days`;
