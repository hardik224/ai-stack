'use client';

import { motion } from 'framer-motion';
import Link from 'next/link';
import { AlertTriangle, ArrowUpRight, Search, Sparkles } from 'lucide-react';

import { cn, clampPercentage, formatBytes, formatDateTime, formatNumber, titleize } from '@/lib/utils';

export { formatBytes, formatDateTime, formatNumber, titleize };

export function Card({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <div
      className={cn(
        'rounded-3xl border border-white/10 bg-white/6 p-5 shadow-[0_30px_80px_-40px_rgba(7,10,20,0.95)] backdrop-blur-xl',
        className,
      )}
    >
      {children}
    </div>
  );
}

export function MetricCard({ title, value, helper, accent, icon, href }: { title: string; value: string; helper?: string; accent?: string; icon?: React.ReactNode; href?: string }) {
  const content = (
    <Card className={cn('relative overflow-hidden', href ? 'transition hover:border-cyan-300/20 hover:bg-white/8' : '')}>
      <div className={cn('absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-cyan-400/0 via-cyan-300/70 to-fuchsia-400/0', accent)} />
      {href ? (
        <div className="absolute right-5 top-5 flex items-center gap-2 text-xs uppercase tracking-[0.25em] text-cyan-200/70">
          <span>Open</span>
          <ArrowUpRight className="size-4 transition-transform duration-200 group-hover:translate-x-1 group-hover:-translate-y-1" />
        </div>
      ) : null}
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.35em] text-slate-400">{title}</p>
          <p className="mt-4 text-3xl font-semibold text-white">{value}</p>
          {helper ? <p className="mt-2 text-sm text-slate-400">{helper}</p> : null}
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/5 p-3 text-slate-200">{icon ?? <Sparkles className="size-5" />}</div>
      </div>
    </Card>
  );

  return (
    <motion.div whileHover={{ y: -4 }} transition={{ duration: 0.2 }}>
      {href ? <Link href={href} className="group block">{content}</Link> : content}
    </motion.div>
  );
}

export function StatusBadge({ value }: { value?: string | null }) {
  const normalized = (value ?? 'unknown').toLowerCase();
  const styles: Record<string, string> = {
    completed: 'border-emerald-400/20 bg-emerald-400/10 text-emerald-200',
    active: 'border-cyan-400/20 bg-cyan-400/10 text-cyan-200',
    processing: 'border-blue-400/20 bg-blue-400/10 text-blue-200',
    running: 'border-blue-400/20 bg-blue-400/10 text-blue-200',
    queued: 'border-amber-400/20 bg-amber-400/10 text-amber-200',
    failed: 'border-rose-400/20 bg-rose-400/10 text-rose-200',
    admin: 'border-fuchsia-400/20 bg-fuchsia-400/10 text-fuchsia-200',
    internal_user: 'border-violet-400/20 bg-violet-400/10 text-violet-200',
    user: 'border-slate-400/20 bg-slate-400/10 text-slate-200',
  };

  return (
    <span className={cn('inline-flex items-center rounded-full border px-3 py-1 text-xs font-medium capitalize tracking-wide', styles[normalized] ?? 'border-white/10 bg-white/5 text-slate-300')}>
      {titleize(normalized)}
    </span>
  );
}

export function ProgressBar({ value }: { value?: number | null }) {
  const percent = clampPercentage(value);
  return (
    <div className="space-y-2">
      <div className="h-2 w-full overflow-hidden rounded-full bg-white/8">
        <div className="h-full rounded-full bg-gradient-to-r from-cyan-400 via-sky-400 to-indigo-400" style={{ width: `${percent}%` }} />
      </div>
      <p className="text-xs text-slate-400">{percent.toFixed(0)}%</p>
    </div>
  );
}

export function SectionHeading({ eyebrow, title, description, action }: { eyebrow: string; title: string; description?: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <p className="text-xs uppercase tracking-[0.4em] text-cyan-200/70">{eyebrow}</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white">{title}</h1>
        {description ? <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-400">{description}</p> : null}
      </div>
      {action}
    </div>
  );
}

export function SearchInput({ value, onChange, placeholder = 'Search' }: { value: string; onChange: (value: string) => void; placeholder?: string }) {
  return (
    <label className="flex items-center gap-3 rounded-2xl border border-white/10 bg-slate-950/50 px-4 py-3 text-sm text-slate-300 shadow-inner shadow-black/20">
      <Search className="size-4 text-slate-500" />
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="w-full bg-transparent outline-none placeholder:text-slate-500"
      />
    </label>
  );
}

export function ErrorState({ title, description, onRetry }: { title: string; description: string; onRetry?: () => void }) {
  return (
    <Card className="border-rose-400/15 bg-rose-500/5 text-rose-50">
      <div className="flex items-start gap-4">
        <div className="rounded-2xl bg-rose-500/15 p-3 text-rose-200">
          <AlertTriangle className="size-5" />
        </div>
        <div className="space-y-2">
          <h3 className="text-lg font-semibold">{title}</h3>
          <p className="text-sm text-rose-100/70">{description}</p>
          {onRetry ? (
            <button onClick={onRetry} className="rounded-full border border-rose-300/20 px-4 py-2 text-sm text-rose-100 transition hover:bg-rose-400/10">
              Retry
            </button>
          ) : null}
        </div>
      </div>
    </Card>
  );
}

export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <Card className="flex min-h-56 flex-col items-center justify-center text-center">
      <div className="rounded-full border border-white/10 bg-white/5 p-4 text-slate-300">
        <Sparkles className="size-5" />
      </div>
      <h3 className="mt-5 text-lg font-semibold text-white">{title}</h3>
      <p className="mt-2 max-w-md text-sm leading-7 text-slate-400">{description}</p>
    </Card>
  );
}

export function SkeletonCard() {
  return <div className="h-48 animate-pulse rounded-3xl border border-white/10 bg-white/5" />;
}

export function TableShell({ children }: { children: React.ReactNode }) {
  return <div className="overflow-hidden rounded-3xl border border-white/10 bg-slate-950/55 shadow-[0_25px_60px_-30px_rgba(15,23,42,0.95)]">{children}</div>;
}
