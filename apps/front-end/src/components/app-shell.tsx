'use client';

import { motion } from 'framer-motion';
import { Activity, BookCopy, Boxes, Bot, ChevronRight, Cpu, DatabaseZap, LayoutDashboard, LogOut, MessageSquareText, Upload, Users } from 'lucide-react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useMemo } from 'react';

import { useAuth } from '@/components/auth-provider';
import { Card, StatusBadge } from '@/components/ui';
import type { UserRole } from '@/features/admin/types';
import { cn, titleize } from '@/lib/utils';

const NAV_ITEMS: Record<UserRole, Array<{ href: string; label: string; icon: React.ComponentType<{ className?: string }> }>> = {
  admin: [
    { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { href: '/assistant', label: 'Assistant', icon: Bot },
    { href: '/users', label: 'Users', icon: Users },
    { href: '/uploads', label: 'Uploads', icon: Upload },
    { href: '/jobs', label: 'Jobs', icon: Boxes },
    { href: '/processes', label: 'Processes', icon: DatabaseZap },
    { href: '/activity', label: 'Activity', icon: Activity },
    { href: '/chats', label: 'Chats', icon: MessageSquareText },
    { href: '/collections', label: 'Collections', icon: BookCopy },
    { href: '/models', label: 'Models', icon: Cpu },
  ],
  internal_user: [
    { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { href: '/assistant', label: 'Assistant', icon: Bot },
    { href: '/uploads', label: 'Uploads', icon: Upload },
  ],
  user: [
    { href: '/assistant', label: 'Assistant', icon: Bot },
  ],
};

function pathLabel(pathname: string) {
  const segment = pathname.split('/').filter(Boolean)[0] ?? 'assistant';
  return titleize(segment);
}

function getDefaultRoute(role: UserRole) {
  return role === 'user' ? '/assistant' : '/dashboard';
}

function getPortalTitle(role: UserRole) {
  if (role === 'admin') return 'Admin Portal';
  if (role === 'internal_user') return 'Knowledge Workspace';
  return 'Assistant Workspace';
}

function getPortalDescription(role: UserRole) {
  if (role === 'admin') return 'Monitor users, uploads, jobs, chats, and platform health from one premium command center.';
  if (role === 'internal_user') return 'Upload documents, track your ingestion flow, and work with a grounded assistant in one streamlined workspace.';
  return 'Ask grounded questions and stream structured answers with citations from your knowledge base.';
}

export function ProtectedShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { ready, user, logout } = useAuth();
  const role = user?.role;
  const navItems = role ? NAV_ITEMS[role] : [];
  const currentSection = pathname.split('/').filter(Boolean)[0] ?? (role ? getDefaultRoute(role).replace('/', '') : 'assistant');

  useEffect(() => {
    if (!ready) return;
    if (!user) {
      router.replace('/login');
      return;
    }
    const allowedSections = new Set(navItems.map((item) => item.href.replace('/', '')));
    if (!allowedSections.has(currentSection)) {
      router.replace(getDefaultRoute(user.role));
    }
  }, [currentSection, navItems, ready, router, user]);

  const headerLabel = useMemo(() => pathLabel(pathname), [pathname]);
  const isAssistantRoute = pathname === '/assistant' || pathname.startsWith('/assistant/');

  if (!ready || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top,_rgba(34,211,238,0.12),_transparent_35%),linear-gradient(180deg,_#050816,_#02030a)] text-slate-200">
        <div className="space-y-4 text-center">
          <div className="mx-auto h-14 w-14 animate-spin rounded-full border border-white/10 border-t-cyan-300" />
          <p className="text-sm uppercase tracking-[0.35em] text-slate-400">Preparing workspace</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(56,189,248,0.16),_transparent_28%),radial-gradient(circle_at_top_right,_rgba(168,85,247,0.12),_transparent_22%),linear-gradient(180deg,_#030611,_#02040c)] text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-[1680px] gap-6 px-4 py-4 lg:px-6">
        <aside className="hidden w-80 shrink-0 lg:block">
          <motion.div initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} className="sticky top-4 space-y-6">
            <Card className="overflow-hidden p-0">
              <div className="border-b border-white/10 bg-gradient-to-br from-cyan-400/10 via-transparent to-fuchsia-400/10 px-6 py-6">
                <p className="text-xs uppercase tracking-[0.35em] text-cyan-200/70">AI Stack</p>
                <h1 className="mt-3 text-2xl font-semibold text-white">{getPortalTitle(user.role)}</h1>
                <p className="mt-2 text-sm leading-7 text-slate-400">{getPortalDescription(user.role)}</p>
              </div>
              <nav className="space-y-1 p-4">
                {navItems.map(({ href, label, icon: Icon }) => {
                  const active = pathname === href || pathname.startsWith(`${href}/`);
                  return (
                    <Link
                      key={href}
                      href={href}
                      className={cn(
                        'flex items-center justify-between rounded-2xl px-4 py-3 text-sm transition',
                        active ? 'bg-white/10 text-white shadow-lg shadow-cyan-500/10' : 'text-slate-400 hover:bg-white/5 hover:text-white',
                      )}
                    >
                      <span className="flex items-center gap-3">
                        <Icon className="size-4" />
                        {label}
                      </span>
                      <ChevronRight className="size-4 opacity-50" />
                    </Link>
                  );
                })}
              </nav>
            </Card>

            <Card>
              <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Signed in as</p>
              <p className="mt-3 text-lg font-semibold text-white">{user.full_name || user.email}</p>
              <p className="mt-1 text-sm text-slate-400">{user.email}</p>
              <div className="mt-4 flex items-center justify-between">
                <StatusBadge value={user.role} />
                <button
                  onClick={() => {
                    logout();
                    router.replace('/login');
                  }}
                  className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-200 transition hover:bg-white/10"
                >
                  <LogOut className="size-4" />
                  Logout
                </button>
              </div>
            </Card>
          </motion.div>
        </aside>

        <main className={cn('flex-1', isAssistantRoute ? 'pb-0' : 'pb-10')}>
          <div className="mb-4 overflow-x-auto lg:hidden">
            <div className="flex min-w-max gap-2 rounded-3xl border border-white/10 bg-slate-950/55 p-2 backdrop-blur-xl">
              {navItems.map(({ href, label, icon: Icon }) => {
                const active = pathname === href || pathname.startsWith(`${href}/`);
                return (
                  <Link
                    key={href}
                    href={href}
                    className={cn(
                      'inline-flex items-center gap-2 rounded-2xl px-4 py-2 text-sm transition',
                      active ? 'bg-white/10 text-white' : 'text-slate-400 hover:bg-white/5 hover:text-white',
                    )}
                  >
                    <Icon className="size-4" />
                    {label}
                  </Link>
                );
              })}
            </div>
          </div>
          {isAssistantRoute ? null : (
            <div className="sticky top-0 z-30 mb-6 rounded-3xl border border-white/10 bg-slate-950/55 px-5 py-4 backdrop-blur-xl">
              <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="text-xs uppercase tracking-[0.35em] text-slate-500">Operations</p>
                  <h2 className="mt-2 text-2xl font-semibold text-white">{headerLabel}</h2>
                </div>
              </div>
            </div>
          )}
          {children}
        </main>
      </div>
    </div>
  );
}
