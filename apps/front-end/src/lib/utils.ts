import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDateTime(value?: string | null) {
  if (!value) return 'Unavailable';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

export function formatBytes(value?: number | null) {
  const bytes = value ?? 0;
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const size = bytes / 1024 ** index;
  return `${size.toFixed(size >= 10 || index === 0 ? 0 : 1)} ${units[index]}`;
}

export function formatNumber(value?: number | null) {
  return new Intl.NumberFormat('en-IN').format(value ?? 0);
}

export function titleize(value?: string | null) {
  if (!value) return 'Unknown';
  return value.replace(/[_-]/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

export function clampPercentage(value?: number | null) {
  const numeric = Number(value ?? 0);
  if (Number.isNaN(numeric)) return 0;
  return Math.max(0, Math.min(100, numeric));
}
