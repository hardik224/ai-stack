'use client';

import { LockKeyhole, ShieldCheck } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { useAuth } from '@/components/auth-provider';
import { Card } from '@/components/ui';

export default function LoginPage() {
  const router = useRouter();
  const { login, ready, user } = useAuth();
  const [email, setEmail] = useState('admin@example.com');
  const [password, setPassword] = useState('StrongPass123!');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (ready && user?.role === 'admin') {
      router.replace('/dashboard');
    }
  }, [ready, router, user]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(email, password);
      router.replace('/dashboard');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to sign in.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-16">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(34,211,238,0.18),_transparent_25%),radial-gradient(circle_at_bottom_right,_rgba(168,85,247,0.14),_transparent_25%)]" />
      <div className="relative grid w-full max-w-6xl gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <Card className="hidden min-h-[680px] overflow-hidden lg:flex lg:flex-col lg:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.4em] text-cyan-200/70">AI Stack</p>
            <h1 className="mt-5 max-w-xl text-5xl font-semibold leading-tight text-white">A premium operational cockpit for retrieval, ingestion, and grounded chat systems.</h1>
            <p className="mt-6 max-w-2xl text-base leading-8 text-slate-400">Monitor files, jobs, processes, users, and read-only chat transcripts through a focused dark interface tuned for admin workflows.</p>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {[
              'Glassmorphism cards with depth and motion.',
              'Charts and progress states wired to live backend metrics.',
              'Read-only chat transcript views with citations and status badges.',
              'Role-aware provisioning flow for admins.',
            ].map((item) => (
              <div key={item} className="rounded-3xl border border-white/10 bg-white/5 p-5 text-sm leading-7 text-slate-300">{item}</div>
            ))}
          </div>
        </Card>

        <Card className="mx-auto w-full max-w-xl p-8">
          <div className="mb-8 flex items-center gap-4">
            <div className="rounded-2xl border border-cyan-300/20 bg-cyan-400/10 p-3 text-cyan-100">
              <ShieldCheck className="size-6" />
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.35em] text-slate-500">Admin access</p>
              <h2 className="mt-2 text-3xl font-semibold text-white">Sign in to the portal</h2>
            </div>
          </div>
          <form className="space-y-5" onSubmit={handleSubmit}>
            <label className="block space-y-2">
              <span className="text-sm text-slate-400">Email</span>
              <input value={email} onChange={(event) => setEmail(event.target.value)} className="w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none" placeholder="admin@example.com" />
            </label>
            <label className="block space-y-2">
              <span className="text-sm text-slate-400">Password</span>
              <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} className="w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none" placeholder="************" />
            </label>
            {error ? <p className="rounded-2xl border border-rose-400/15 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">{error}</p> : null}
            <button type="submit" disabled={submitting} className="flex w-full items-center justify-center gap-2 rounded-full bg-gradient-to-r from-cyan-400 via-sky-400 to-indigo-400 px-5 py-3 text-sm font-semibold text-slate-950 transition disabled:cursor-not-allowed disabled:opacity-70">
              <LockKeyhole className="size-4" />
              {submitting ? 'Signing in...' : 'Enter admin portal'}
            </button>
          </form>
        </Card>
      </div>
    </main>
  );
}
