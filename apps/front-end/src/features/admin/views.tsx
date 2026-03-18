'use client';

import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { Activity, ArrowRight, Bot, Boxes, DatabaseZap, FileClock, Filter, FolderKanban, HardDriveDownload, MessageSquareText, ShieldCheck, UserPlus, Users } from 'lucide-react';
import Link from 'next/link';
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis, Area, AreaChart } from 'recharts';
import ReactMarkdown from 'react-markdown';

import { useAuth } from '@/components/auth-provider';
import { Card, EmptyState, ErrorState, MetricCard, ProgressBar, SearchInput, SectionHeading, SkeletonCard, StatusBadge, TableShell, formatBytes, formatDateTime, formatNumber, titleize } from '@/components/ui';
import {
  createUser,
  fetchActivity,
  fetchAdminUser,
  fetchAdminUsers,
  fetchChatDetail,
  fetchChats,
  fetchCollections,
  fetchDashboardSummary,
  fetchJobDetail,
  fetchJobs,
  fetchJobSummary,
  fetchProcessSummary,
  fetchProcesses,
  fetchUploads,
  fetchUploadSummary,
} from '@/features/admin/data';
import type { CreateUserPayload, UserRole } from '@/features/admin/types';
import { cn } from '@/lib/utils';

const CHART_COLORS = ['#67e8f9', '#38bdf8', '#818cf8', '#a78bfa', '#f0abfc'];

function useToken() {
  const { token } = useAuth();
  if (!token) {
    throw new Error('Authentication token is unavailable.');
  }
  return token;
}

function LoadingGrid() {
  return (
    <div className="grid gap-5 xl:grid-cols-3">
      <SkeletonCard />
      <SkeletonCard />
      <SkeletonCard />
    </div>
  );
}

function StatGrid({ items }: { items: Array<{ title: string; value: string; helper?: string; icon: React.ReactNode; accent?: string }> }) {
  return (
    <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => (
        <MetricCard key={item.title} {...item} />
      ))}
    </div>
  );
}

function DataTable({ headers, children }: { headers: string[]; children: React.ReactNode }) {
  return (
    <TableShell>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-white/10 text-left text-sm text-slate-300">
          <thead className="bg-white/5 text-xs uppercase tracking-[0.25em] text-slate-500">
            <tr>
              {headers.map((header) => (
                <th key={header} className="px-5 py-4 font-medium">{header}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">{children}</tbody>
        </table>
      </div>
    </TableShell>
  );
}

function QueryBoundary({ isLoading, error, onRetry, children }: { isLoading: boolean; error: unknown; onRetry?: () => void; children: React.ReactNode }) {
  if (isLoading) return <LoadingGrid />;
  if (error) {
    return <ErrorState title="Something went wrong" description={error instanceof Error ? error.message : 'Unknown request failure.'} onRetry={onRetry} />;
  }
  return <>{children}</>;
}

function RoleSelect({ value, onChange }: { value: UserRole; onChange: (role: UserRole) => void }) {
  return (
    <select value={value} onChange={(event) => onChange(event.target.value as UserRole)} className="rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-slate-100 outline-none">
      <option value="admin">Admin</option>
      <option value="internal_user">Internal User</option>
      <option value="user">User</option>
    </select>
  );
}

function CreateUserDialog() {
  const token = useToken();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<CreateUserPayload>({ email: '', full_name: '', password: 'StrongPass123!', role: 'internal_user' });

  const mutation = useMutation({
    mutationFn: (payload: CreateUserPayload) => createUser(token, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
      setOpen(false);
      setForm({ email: '', full_name: '', password: 'StrongPass123!', role: 'internal_user' });
    },
  });

  return (
    <>
      <button onClick={() => setOpen(true)} className="inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-400/10 px-5 py-3 text-sm font-medium text-cyan-100 transition hover:bg-cyan-400/15">
        <UserPlus className="size-4" />
        Create user
      </button>
      {open ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4 backdrop-blur-md">
          <Card className="w-full max-w-xl p-6">
            <SectionHeading eyebrow="Provisioning" title="Create a new platform user" description="The current backend supports role assignment during user creation. Editing roles later still needs a dedicated backend update endpoint." />
            <div className="mt-6 grid gap-4 md:grid-cols-2">
              <input className="rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none" placeholder="Full name" value={form.full_name} onChange={(event) => setForm((current) => ({ ...current, full_name: event.target.value }))} />
              <input className="rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none" placeholder="Email address" value={form.email} onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))} />
              <input className="rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none" placeholder="Temporary password" value={form.password} onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))} />
              <RoleSelect value={form.role} onChange={(role) => setForm((current) => ({ ...current, role }))} />
            </div>
            {mutation.error ? <p className="mt-4 text-sm text-rose-300">{mutation.error.message}</p> : null}
            <div className="mt-6 flex items-center justify-end gap-3">
              <button onClick={() => setOpen(false)} className="rounded-full border border-white/10 px-5 py-3 text-sm text-slate-300 transition hover:bg-white/5">Cancel</button>
              <button onClick={() => mutation.mutate(form)} disabled={mutation.isPending || !form.email || !form.full_name || !form.password} className="rounded-full bg-gradient-to-r from-cyan-400 to-indigo-400 px-5 py-3 text-sm font-semibold text-slate-950 transition disabled:cursor-not-allowed disabled:opacity-60">
                {mutation.isPending ? 'Creating...' : 'Create user'}
              </button>
            </div>
          </Card>
        </div>
      ) : null}
    </>
  );
}

function DashboardView() {
  const token = useToken();
  const dashboard = useQuery({ queryKey: ['dashboard-summary'], queryFn: () => fetchDashboardSummary(token) });
  const uploadSummary = useQuery({ queryKey: ['upload-summary'], queryFn: () => fetchUploadSummary(token) });
  const jobSummary = useQuery({ queryKey: ['job-summary'], queryFn: () => fetchJobSummary(token) });
  const processSummary = useQuery({ queryKey: ['process-summary'], queryFn: () => fetchProcessSummary(token) });

  return (
    <div className="space-y-6">
      <SectionHeading eyebrow="Overview" title="Platform command center" description="Track ingestion health, user growth, chat volume, and operational pressure at a glance." />
      <QueryBoundary isLoading={dashboard.isLoading || uploadSummary.isLoading || jobSummary.isLoading || processSummary.isLoading} error={dashboard.error || uploadSummary.error || jobSummary.error || processSummary.error} onRetry={() => { dashboard.refetch(); uploadSummary.refetch(); jobSummary.refetch(); processSummary.refetch(); }}>
        <StatGrid items={[
          { title: 'Users', value: formatNumber(dashboard.data?.total_users), helper: `${dashboard.data?.admin_users ?? 0} admins | ${dashboard.data?.internal_users ?? 0} internal`, icon: <Users className="size-5" /> },
          { title: 'Knowledge Files', value: formatNumber(dashboard.data?.total_files), helper: formatBytes(dashboard.data?.total_uploaded_bytes), icon: <HardDriveDownload className="size-5" /> },
          { title: 'Jobs', value: formatNumber(dashboard.data?.total_jobs), helper: `${dashboard.data?.queue_depth ?? 0} waiting in queue`, icon: <Boxes className="size-5" /> },
          { title: 'Chats', value: formatNumber(dashboard.data?.total_chat_sessions), helper: `${dashboard.data?.total_chat_messages ?? 0} messages tracked`, icon: <Bot className="size-5" /> },
        ]} />
        <div className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
          <Card>
            <div className="mb-6 flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Upload load</p>
                <h3 className="mt-2 text-xl font-semibold text-white">Top uploading users</h3>
              </div>
              <StatusBadge value="active" />
            </div>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={(uploadSummary.data?.items ?? []).slice(0, 6)}>
                  <CartesianGrid stroke="rgba(148,163,184,0.08)" vertical={false} />
                  <XAxis dataKey="email" tick={{ fill: '#94a3b8', fontSize: 12 }} interval={0} angle={-20} height={70} />
                  <YAxis tick={{ fill: '#94a3b8', fontSize: 12 }} tickFormatter={(value) => `${Math.round(value / 1024)} KB`} />
                  <Tooltip cursor={{ fill: 'rgba(255,255,255,0.03)' }} contentStyle={{ background: '#020617', border: '1px solid rgba(148,163,184,0.1)', borderRadius: 18 }} />
                  <Bar dataKey="total_uploaded_bytes" radius={[10, 10, 0, 0]}>
                    {(uploadSummary.data?.items ?? []).slice(0, 6).map((entry, index) => (
                      <Cell key={entry.user_id} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
          <Card>
            <div className="mb-6">
              <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Job posture</p>
              <h3 className="mt-2 text-xl font-semibold text-white">Ingestion distribution</h3>
            </div>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={[{ name: 'Queued', value: jobSummary.data?.queued_jobs ?? 0 }, { name: 'Processing', value: jobSummary.data?.processing_jobs ?? 0 }, { name: 'Completed', value: jobSummary.data?.completed_jobs ?? 0 }, { name: 'Failed', value: jobSummary.data?.failed_jobs ?? 0 }]} dataKey="value" innerRadius={70} outerRadius={110} paddingAngle={5}>
                    {CHART_COLORS.map((color) => (<Cell key={color} fill={color} />))}
                  </Pie>
                  <Tooltip contentStyle={{ background: '#020617', border: '1px solid rgba(148,163,184,0.1)', borderRadius: 18 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <Card className="bg-white/4 p-4"><p className="text-sm text-slate-400">Running processes</p><p className="mt-2 text-2xl font-semibold text-white">{formatNumber(processSummary.data?.running_processes)}</p></Card>
              <Card className="bg-white/4 p-4"><p className="text-sm text-slate-400">Queue depth</p><p className="mt-2 text-2xl font-semibold text-white">{formatNumber(processSummary.data?.queue_depth)}</p></Card>
            </div>
          </Card>
        </div>
      </QueryBoundary>
    </div>
  );
}

function UsersView() {
  const token = useToken();
  const [search, setSearch] = useState('');
  const query = useQuery({ queryKey: ['admin-users'], queryFn: () => fetchAdminUsers(token, { limit: 100, offset: 0 }) });
  const users = useMemo(() => (query.data?.items ?? []).filter((item) => [item.email, item.full_name, item.role].join(' ').toLowerCase().includes(search.toLowerCase())), [query.data?.items, search]);

  return (
    <div className="space-y-6">
      <SectionHeading eyebrow="Identity" title="Users and access" description="Create users, review role assignment, and monitor operational footprint per account." action={<CreateUserDialog />} />
      <div className="grid gap-5 xl:grid-cols-[0.95fr_1.05fr]">
        <Card>
          <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Access matrix</p>
          <div className="mt-6 grid gap-4 md:grid-cols-3">
            {[
              { role: 'admin', description: 'Full visibility across users, jobs, processes, uploads, and chat audit trails.' },
              { role: 'internal_user', description: 'Operational access to collections, uploads, and owned grounded chat workflows.' },
              { role: 'user', description: 'Standard product access with lower operational surface area.' },
            ].map((item) => (
              <Card key={item.role} className="bg-white/4 p-4">
                <StatusBadge value={item.role} />
                <p className="mt-4 text-sm leading-7 text-slate-400">{item.description}</p>
              </Card>
            ))}
          </div>
          <div className="mt-5 rounded-2xl border border-amber-300/15 bg-amber-400/8 p-4 text-sm leading-7 text-amber-50/90">Current backend gap: existing APIs support role selection during creation, but not editing an existing user role. The portal surfaces that clearly instead of pretending updates will persist.</div>
        </Card>
        <Card>
          <SearchInput value={search} onChange={setSearch} placeholder="Search users by email, name, or role" />
          <div className="mt-5">
            <QueryBoundary isLoading={query.isLoading} error={query.error} onRetry={() => query.refetch()}>
              {users.length ? (
                <DataTable headers={['User', 'Role', 'Uploads', 'Jobs', 'Chats', 'Last login', 'Inspect']}>
                  {users.map((user) => (
                    <tr key={user.id} className="transition hover:bg-white/5">
                      <td className="px-5 py-4"><p className="font-medium text-white">{user.full_name || 'Unnamed user'}</p><p className="mt-1 text-xs text-slate-500">{user.email}</p></td>
                      <td className="px-5 py-4"><StatusBadge value={user.role} /></td>
                      <td className="px-5 py-4 text-slate-300">{formatNumber(user.file_count)} files | {formatBytes(user.total_uploaded_bytes)}</td>
                      <td className="px-5 py-4 text-slate-300">{formatNumber(user.job_count)}</td>
                      <td className="px-5 py-4 text-slate-300">{formatNumber(user.chat_session_count)}</td>
                      <td className="px-5 py-4 text-slate-400">{formatDateTime(user.last_login_at)}</td>
                      <td className="px-5 py-4"><Link href={`/users/${user.id}`} className="inline-flex items-center gap-2 text-cyan-200 hover:text-white">Details <ArrowRight className="size-4" /></Link></td>
                    </tr>
                  ))}
                </DataTable>
              ) : (
                <EmptyState title="No users matched the current filter" description="Try a broader search or create a new user from the admin portal." />
              )}
            </QueryBoundary>
          </div>
        </Card>
      </div>
    </div>
  );
}

function UserDetailView({ id }: { id: string }) {
  const token = useToken();
  const query = useQuery({ queryKey: ['admin-user', id], queryFn: () => fetchAdminUser(token, id) });

  return (
    <div className="space-y-6">
      <SectionHeading eyebrow="User detail" title="User operational profile" description="Inspect activity, upload volume, and chat usage for this account." action={<Link href="/users" className="rounded-full border border-white/10 px-4 py-3 text-sm text-slate-300 transition hover:bg-white/5">Back to users</Link>} />
      <QueryBoundary isLoading={query.isLoading} error={query.error} onRetry={() => query.refetch()}>
        {query.data ? (
          <>
            <StatGrid items={[
              { title: 'Uploads', value: formatNumber(query.data.file_count), helper: formatBytes(query.data.total_uploaded_bytes), icon: <HardDriveDownload className="size-5" /> },
              { title: 'Jobs', value: formatNumber(query.data.job_count), helper: `${query.data.completed_jobs ?? 0} completed | ${query.data.failed_jobs ?? 0} failed`, icon: <Boxes className="size-5" /> },
              { title: 'Chats', value: formatNumber(query.data.chat_session_count), helper: `${query.data.message_count} total messages`, icon: <MessageSquareText className="size-5" /> },
              { title: 'Role', value: titleize(query.data.role), helper: query.data.status, icon: <ShieldCheck className="size-5" /> },
            ]} />
            <div className="grid gap-6 xl:grid-cols-[0.8fr_1.2fr]">
              <Card>
                <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Identity</p>
                <div className="mt-5 space-y-4 text-sm text-slate-300">
                  <div><span className="text-slate-500">Name</span><p className="mt-1 text-white">{query.data.full_name || 'Unnamed user'}</p></div>
                  <div><span className="text-slate-500">Email</span><p className="mt-1 text-white">{query.data.email}</p></div>
                  <div><span className="text-slate-500">Role</span><div className="mt-2"><StatusBadge value={query.data.role} /></div></div>
                  <div><span className="text-slate-500">Last login</span><p className="mt-1 text-white">{formatDateTime(query.data.last_login_at)}</p></div>
                </div>
              </Card>
              <Card>
                <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Role and access management</p>
                <h3 className="mt-3 text-xl font-semibold text-white">Read-only until backend role update API exists</h3>
                <p className="mt-3 text-sm leading-7 text-slate-400">This portal shows the user's current role clearly, but avoids fake controls. The current backend only supports role assignment while creating a user.</p>
                <div className="mt-5 grid gap-4 md:grid-cols-2">
                  <Card className="bg-white/4 p-4"><p className="text-sm text-slate-400">Assistant messages</p><p className="mt-2 text-2xl font-semibold text-white">{formatNumber(query.data.assistant_message_count)}</p></Card>
                  <Card className="bg-white/4 p-4"><p className="text-sm text-slate-400">Failed assistant replies</p><p className="mt-2 text-2xl font-semibold text-white">{formatNumber(query.data.failed_assistant_message_count)}</p></Card>
                </div>
              </Card>
            </div>
          </>
        ) : null}
      </QueryBoundary>
    </div>
  );
}

function UploadsView() {
  const token = useToken();
  const [search, setSearch] = useState('');
  const uploads = useQuery({ queryKey: ['uploads'], queryFn: () => fetchUploads(token, { limit: 100, offset: 0 }) });
  const summary = useQuery({ queryKey: ['uploads-summary'], queryFn: () => fetchUploadSummary(token) });
  const filtered = useMemo(() => (uploads.data?.items ?? []).filter((item) => [item.original_name, item.uploaded_by_email, item.collection_name, item.latest_job_status].join(' ').toLowerCase().includes(search.toLowerCase())), [search, uploads.data?.items]);

  return (
    <div className="space-y-6">
      <SectionHeading eyebrow="Ingestion" title="Uploads and source files" description="Track user upload behavior, ingestion progress, and raw storage volume across the platform." />
      <QueryBoundary isLoading={uploads.isLoading || summary.isLoading} error={uploads.error || summary.error} onRetry={() => { uploads.refetch(); summary.refetch(); }}>
        <div className="grid gap-5 md:grid-cols-3">
          <MetricCard title="Files tracked" value={formatNumber(filtered.length)} helper="Most recent 100 uploads" icon={<FileClock className="size-5" />} />
          <MetricCard title="Top uploader bytes" value={formatBytes(Math.max(...(summary.data?.items ?? []).map((item) => item.total_uploaded_bytes), 0))} helper="Largest upload footprint by a single user" icon={<Users className="size-5" />} />
          <MetricCard title="Unique uploaders" value={formatNumber(summary.data?.items?.filter((item) => item.file_count > 0).length)} helper="Users with at least one stored file" icon={<HardDriveDownload className="size-5" />} />
        </div>
        <div className="grid gap-6 xl:grid-cols-[0.85fr_1.15fr]">
          <Card>
            <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Upload leaderboard</p>
            <div className="mt-6 h-80">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={(summary.data?.items ?? []).slice(0, 8)}>
                  <defs>
                    <linearGradient id="uploadArea" x1="0" x2="0" y1="0" y2="1">
                      <stop offset="0%" stopColor="#67e8f9" stopOpacity={0.5} />
                      <stop offset="100%" stopColor="#67e8f9" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="rgba(148,163,184,0.08)" vertical={false} />
                  <XAxis dataKey="email" tick={{ fill: '#94a3b8', fontSize: 12 }} interval={0} angle={-20} height={70} />
                  <YAxis tick={{ fill: '#94a3b8', fontSize: 12 }} tickFormatter={(value) => `${Math.round(value / 1024)} KB`} />
                  <Tooltip contentStyle={{ background: '#020617', border: '1px solid rgba(148,163,184,0.1)', borderRadius: 18 }} />
                  <Area type="monotone" dataKey="total_uploaded_bytes" stroke="#67e8f9" fill="url(#uploadArea)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Card>
          <Card>
            <SearchInput value={search} onChange={setSearch} placeholder="Search uploads, users, collections, or status" />
            <div className="mt-5">
              {filtered.length ? (
                <DataTable headers={['File', 'Owner', 'Collection', 'Stage', 'Progress', 'Size']}>
                  {filtered.map((item) => (
                    <tr key={item.id} className="transition hover:bg-white/5">
                      <td className="px-5 py-4"><p className="font-medium text-white">{item.original_name}</p><p className="mt-1 text-xs text-slate-500">{formatDateTime(item.created_at)}</p></td>
                      <td className="px-5 py-4 text-slate-300">{item.uploaded_by_full_name || item.uploaded_by_email}</td>
                      <td className="px-5 py-4 text-slate-300">{item.collection_name || 'No collection'}</td>
                      <td className="px-5 py-4"><StatusBadge value={item.latest_job_stage || item.latest_job_status || 'unknown'} /></td>
                      <td className="px-5 py-4 min-w-40"><ProgressBar value={item.latest_job_progress ?? 0} /></td>
                      <td className="px-5 py-4 text-slate-300">{formatBytes(item.size_bytes)}</td>
                    </tr>
                  ))}
                </DataTable>
              ) : (
                <EmptyState title="No uploads matched the current filter" description="Try a broader search or wait for new ingestion jobs to appear." />
              )}
            </div>
          </Card>
        </div>
      </QueryBoundary>
    </div>
  );
}

function JobsView() {
  const token = useToken();
  const [status, setStatus] = useState<string>('');
  const jobs = useQuery({ queryKey: ['jobs', status], queryFn: () => fetchJobs(token, { limit: 100, offset: 0, status: status || undefined }) });
  const summary = useQuery({ queryKey: ['jobs-summary'], queryFn: () => fetchJobSummary(token) });

  return (
    <div className="space-y-6">
      <SectionHeading eyebrow="Pipeline" title="Jobs and ingestion status" description="Inspect queue pressure, chunking progress, indexing health, and worker outcomes across the ingestion lifecycle." />
      <QueryBoundary isLoading={jobs.isLoading || summary.isLoading} error={jobs.error || summary.error} onRetry={() => { jobs.refetch(); summary.refetch(); }}>
        <StatGrid items={[
          { title: 'Queued', value: formatNumber(summary.data?.queued_jobs), helper: `${summary.data?.queue_depth ?? 0} waiting in Redis`, icon: <FileClock className="size-5" /> },
          { title: 'Processing', value: formatNumber(summary.data?.processing_jobs), helper: `${summary.data?.embedding_jobs ?? 0} embedding`, icon: <Boxes className="size-5" /> },
          { title: 'Completed', value: formatNumber(summary.data?.completed_jobs), helper: `${summary.data?.indexing_jobs ?? 0} indexing right now`, icon: <ShieldCheck className="size-5" /> },
          { title: 'Failed', value: formatNumber(summary.data?.failed_jobs), helper: `${summary.data?.parsing_jobs ?? 0} parsing`, icon: <Activity className="size-5" /> },
        ]} />
        <Card>
          <div className="flex flex-wrap items-center gap-3">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-300"><Filter className="size-4" />Status filter</div>
            {['', 'queued', 'processing', 'completed', 'failed'].map((value) => (
              <button key={value || 'all'} onClick={() => setStatus(value)} className={cn('rounded-full px-4 py-2 text-sm transition', status === value ? 'bg-cyan-400 text-slate-950' : 'border border-white/10 bg-white/5 text-slate-300 hover:bg-white/10')}>
                {value ? titleize(value) : 'All'}
              </button>
            ))}
          </div>
          <div className="mt-5">
            {(jobs.data?.items ?? []).length ? (
              <DataTable headers={['Job', 'Status', 'Chunks', 'Progress', 'Created', 'Inspect']}>
                {(jobs.data?.items ?? []).map((job) => (
                  <tr key={job.id} className="transition hover:bg-white/5">
                    <td className="px-5 py-4"><p className="font-medium text-white">{job.file_name}</p><p className="mt-1 text-xs text-slate-500">{job.collection_name || 'No collection'}</p></td>
                    <td className="px-5 py-4"><div className="flex flex-col gap-2"><StatusBadge value={job.status} /><StatusBadge value={job.current_stage} /></div></td>
                    <td className="px-5 py-4 text-slate-300">{formatNumber(job.processed_chunks)} / {formatNumber(job.total_chunks)}</td>
                    <td className="px-5 py-4 min-w-40"><ProgressBar value={job.progress_percent} /></td>
                    <td className="px-5 py-4 text-slate-400">{formatDateTime(job.created_at)}</td>
                    <td className="px-5 py-4"><Link href={`/jobs/${job.id}`} className="inline-flex items-center gap-2 text-cyan-200 hover:text-white">Details <ArrowRight className="size-4" /></Link></td>
                  </tr>
                ))}
              </DataTable>
            ) : (
              <EmptyState title="No jobs available" description="Upload a file or clear the current status filter to see more ingestion jobs." />
            )}
          </div>
        </Card>
      </QueryBoundary>
    </div>
  );
}

function JobDetailView({ id }: { id: string }) {
  const token = useToken();
  const query = useQuery({ queryKey: ['job-detail', id], queryFn: () => fetchJobDetail(token, id) });

  return (
    <div className="space-y-6">
      <SectionHeading eyebrow="Job detail" title="Processing timeline" description="Inspect stage-by-stage progress, worker metadata, and event history for a single ingestion job." action={<Link href="/jobs" className="rounded-full border border-white/10 px-4 py-3 text-sm text-slate-300 transition hover:bg-white/5">Back to jobs</Link>} />
      <QueryBoundary isLoading={query.isLoading} error={query.error} onRetry={() => query.refetch()}>
        {query.data ? (
          <>
            <StatGrid items={[
              { title: 'Status', value: titleize(query.data.job.status), helper: query.data.job.current_stage, icon: <Boxes className="size-5" /> },
              { title: 'Chunks processed', value: `${formatNumber(query.data.job.processed_chunks)} / ${formatNumber(query.data.job.total_chunks)}`, helper: `${formatNumber(query.data.job.indexed_chunks)} indexed`, icon: <DatabaseZap className="size-5" /> },
              { title: 'Worker', value: query.data.job.worker_id || 'Pending assignment', helper: query.data.job.worker_heartbeat_at ? `heartbeat ${formatDateTime(query.data.job.worker_heartbeat_at)}` : 'No heartbeat yet', icon: <Activity className="size-5" /> },
              { title: 'File', value: query.data.job.file_name, helper: query.data.job.collection_name || 'No collection', icon: <FolderKanban className="size-5" /> },
            ]} />
            <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
              <Card>
                <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Progress snapshot</p>
                <div className="mt-4"><ProgressBar value={query.data.progress?.progress_percent ?? query.data.job.progress_percent} /></div>
                <p className="mt-4 text-sm leading-7 text-slate-400">{query.data.progress?.progress_message || query.data.job.progress_message || 'No progress message was recorded.'}</p>
                <div className="mt-5 grid gap-3 text-sm text-slate-300">
                  <div className="flex justify-between"><span className="text-slate-500">Started</span><span>{formatDateTime(query.data.progress?.started_at)}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">Completed</span><span>{formatDateTime(query.data.progress?.completed_at)}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">Failed</span><span>{formatDateTime(query.data.progress?.failed_at)}</span></div>
                </div>
              </Card>
              <Card>
                <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Stage timeline</p>
                <div className="mt-5 space-y-4">
                  {query.data.stages.map((stage) => (
                    <div key={stage.id} className="rounded-2xl border border-white/10 bg-white/4 p-4">
                      <div className="flex items-center justify-between gap-4">
                        <div>
                          <p className="font-medium text-white">{titleize(stage.stage_name)}</p>
                          <p className="mt-1 text-xs text-slate-500">{formatDateTime(stage.started_at)} to {formatDateTime(stage.completed_at)}</p>
                        </div>
                        <StatusBadge value={stage.stage_status} />
                      </div>
                      <div className="mt-4"><ProgressBar value={stage.progress_percent} /></div>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
            <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
              <Card>
                <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Background task</p>
                {query.data.background_task ? (
                  <div className="mt-5 space-y-3 text-sm text-slate-300">
                    <div className="flex justify-between"><span className="text-slate-500">Task type</span><span>{titleize(query.data.background_task.task_type)}</span></div>
                    <div className="flex justify-between"><span className="text-slate-500">Status</span><StatusBadge value={query.data.background_task.status} /></div>
                    <div className="flex justify-between"><span className="text-slate-500">Current stage</span><span>{titleize(query.data.background_task.current_stage)}</span></div>
                    <div className="flex justify-between"><span className="text-slate-500">Worker</span><span>{query.data.background_task.worker_id || 'None'}</span></div>
                  </div>
                ) : (
                  <EmptyState title="No background task metadata" description="This job has not published background task details yet." />
                )}
              </Card>
              <Card>
                <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Event log</p>
                <div className="mt-5 space-y-3">
                  {query.data.events.length ? query.data.events.map((event) => (
                    <div key={event.id} className="rounded-2xl border border-white/10 bg-white/4 p-4">
                      <div className="flex items-center justify-between gap-4">
                        <p className="font-medium text-white">{titleize(event.event_type)}</p>
                        <p className="text-xs text-slate-500">{formatDateTime(event.created_at)}</p>
                      </div>
                      <p className="mt-2 text-sm leading-7 text-slate-400">{event.message}</p>
                    </div>
                  )) : <EmptyState title="No events recorded" description="Job events will appear here as workers publish progress updates." />}
                </div>
              </Card>
            </div>
          </>
        ) : null}
      </QueryBoundary>
    </div>
  );
}

function ProcessesView() {
  const token = useToken();
  const summary = useQuery({ queryKey: ['process-summary'], queryFn: () => fetchProcessSummary(token) });
  const processes = useQuery({ queryKey: ['processes'], queryFn: () => fetchProcesses(token, { limit: 100, offset: 0 }) });

  return (
    <div className="space-y-6">
      <SectionHeading eyebrow="Workers" title="Background processes" description="See what the ingestion workers are doing right now, how much work remains, and which jobs are under active execution." />
      <QueryBoundary isLoading={summary.isLoading || processes.isLoading} error={summary.error || processes.error} onRetry={() => { summary.refetch(); processes.refetch(); }}>
        <StatGrid items={[
          { title: 'Running', value: formatNumber(summary.data?.running_processes), helper: `${summary.data?.queued_processes ?? 0} queued`, icon: <Activity className="size-5" /> },
          { title: 'Completed', value: formatNumber(summary.data?.completed_processes), helper: `${summary.data?.failed_processes ?? 0} failed`, icon: <ShieldCheck className="size-5" /> },
          { title: 'Average progress', value: `${Math.round(summary.data?.average_progress_percent ?? 0)}%`, helper: 'Across all tracked processes', icon: <DatabaseZap className="size-5" /> },
          { title: 'Queue depth', value: formatNumber(summary.data?.queue_depth), helper: 'Redis ingestion queue length', icon: <Boxes className="size-5" /> },
        ]} />
        {(processes.data?.items ?? []).length ? (
          <DataTable headers={['Process', 'Status', 'Worker', 'Progress', 'File', 'Updated']}>
            {(processes.data?.items ?? []).map((process) => (
              <tr key={process.id} className="transition hover:bg-white/5">
                <td className="px-5 py-4"><p className="font-medium text-white">{titleize(process.task_type)}</p><p className="mt-1 text-xs text-slate-500">{titleize(process.current_stage)}</p></td>
                <td className="px-5 py-4"><StatusBadge value={process.status} /></td>
                <td className="px-5 py-4 text-slate-300">{process.worker_id || 'Unassigned'}</td>
                <td className="px-5 py-4 min-w-40"><ProgressBar value={process.progress_percent} /></td>
                <td className="px-5 py-4 text-slate-300">{process.file_name || 'Unknown file'}</td>
                <td className="px-5 py-4 text-slate-400">{formatDateTime(process.updated_at || process.heartbeat_at)}</td>
              </tr>
            ))}
          </DataTable>
        ) : (
          <EmptyState title="No background processes found" description="Once workers pick up ingestion tasks, their live process records will appear here." />
        )}
      </QueryBoundary>
    </div>
  );
}

function ActivityView() {
  const token = useToken();
  const query = useQuery({ queryKey: ['activity'], queryFn: () => fetchActivity(token, { limit: 50 }) });

  return (
    <div className="space-y-6">
      <SectionHeading eyebrow="Audit" title="Recent activity" description="Follow the most recent operational and user actions across authentication, uploads, jobs, and chat." />
      <QueryBoundary isLoading={query.isLoading} error={query.error} onRetry={() => query.refetch()}>
        {(query.data?.items ?? []).length ? (
          <div className="space-y-4">
            {query.data?.items.map((item) => (
              <motion.div key={item.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
                <Card>
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div>
                      <p className="text-xs uppercase tracking-[0.3em] text-slate-500">{titleize(item.activity_type)}</p>
                      <p className="mt-3 text-lg font-semibold text-white">{item.description}</p>
                      <p className="mt-2 text-sm text-slate-400">Actor: {item.actor_email || item.actor_user_id || 'System'} | Target: {item.target_type || 'n/a'}</p>
                    </div>
                    <div className="flex items-center gap-3">
                      <StatusBadge value={item.visibility} />
                      <span className="text-sm text-slate-500">{formatDateTime(item.created_at)}</span>
                    </div>
                  </div>
                </Card>
              </motion.div>
            ))}
          </div>
        ) : (
          <EmptyState title="No recent activity" description="Activity logs will surface here as users and background systems interact with the stack." />
        )}
      </QueryBoundary>
    </div>
  );
}

function ChatsView() {
  const token = useToken();
  const [search, setSearch] = useState('');
  const query = useQuery({ queryKey: ['admin-chats'], queryFn: () => fetchChats(token, { limit: 100, offset: 0 }) });
  const items = useMemo(() => (query.data?.items ?? []).filter((item) => [item.title, item.user_email, item.user_full_name, item.latest_assistant_status].join(' ').toLowerCase().includes(search.toLowerCase())), [query.data?.items, search]);

  return (
    <div className="space-y-6">
      <SectionHeading eyebrow="Chat audit" title="User chat sessions" description="Review grounded conversations in a read-only interface, including assistant message health and citation counts." />
      <Card>
        <SearchInput value={search} onChange={setSearch} placeholder="Search sessions by title, user, or assistant status" />
        <div className="mt-5">
          <QueryBoundary isLoading={query.isLoading} error={query.error} onRetry={() => query.refetch()}>
            {items.length ? (
              <DataTable headers={['Session', 'User', 'Messages', 'Assistant', 'Updated', 'Inspect']}>
                {items.map((session) => (
                  <tr key={session.id} className="transition hover:bg-white/5">
                    <td className="px-5 py-4"><p className="font-medium text-white">{session.title}</p><p className="mt-1 text-xs text-slate-500">{session.id}</p></td>
                    <td className="px-5 py-4 text-slate-300">{session.user_full_name || session.user_email}</td>
                    <td className="px-5 py-4 text-slate-300">{formatNumber(session.message_count)} messages | {formatNumber(session.citation_count)} citations</td>
                    <td className="px-5 py-4"><StatusBadge value={session.latest_assistant_status || 'unknown'} /></td>
                    <td className="px-5 py-4 text-slate-400">{formatDateTime(session.updated_at)}</td>
                    <td className="px-5 py-4"><Link href={`/chats/${session.id}`} className="inline-flex items-center gap-2 text-cyan-200 hover:text-white">Open <ArrowRight className="size-4" /></Link></td>
                  </tr>
                ))}
              </DataTable>
            ) : (
              <EmptyState title="No chat sessions yet" description="Once users start asking grounded questions, session transcripts will appear here." />
            )}
          </QueryBoundary>
        </div>
      </Card>
    </div>
  );
}

function ChatDetailView({ id }: { id: string }) {
  const token = useToken();
  const query = useQuery({ queryKey: ['admin-chat-detail', id], queryFn: () => fetchChatDetail(token, id) });

  return (
    <div className="space-y-6">
      <SectionHeading eyebrow="Transcript" title="Read-only chat session" description="Inspect the full grounded exchange, message statuses, and persisted sources in a chat-native layout." action={<Link href="/chats" className="rounded-full border border-white/10 px-4 py-3 text-sm text-slate-300 transition hover:bg-white/5">Back to chats</Link>} />
      <QueryBoundary isLoading={query.isLoading} error={query.error} onRetry={() => query.refetch()}>
        {query.data ? (
          <div className="grid gap-6 xl:grid-cols-[0.72fr_1.28fr]">
            <Card>
              <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Session snapshot</p>
              <div className="mt-5 space-y-4 text-sm text-slate-300">
                <div><span className="text-slate-500">Title</span><p className="mt-1 text-white">{query.data.session.title}</p></div>
                <div><span className="text-slate-500">User</span><p className="mt-1 text-white">{query.data.session.user_full_name || query.data.session.user_email}</p></div>
                <div><span className="text-slate-500">Messages</span><p className="mt-1 text-white">{formatNumber(query.data.session.message_count)}</p></div>
                <div><span className="text-slate-500">Updated</span><p className="mt-1 text-white">{formatDateTime(query.data.session.updated_at)}</p></div>
              </div>
            </Card>
            <Card>
              <div className="space-y-4">
                {query.data.messages.map((message) => (
                  <div key={message.id} className={cn('flex', message.role === 'assistant' ? 'justify-start' : 'justify-end')}>
                    <div className={cn('max-w-3xl rounded-[2rem] border px-5 py-4 shadow-xl', message.role === 'assistant' ? 'border-white/10 bg-white/6 text-slate-100' : 'border-cyan-300/20 bg-cyan-400/10 text-cyan-50')}>
                      <div className="mb-3 flex items-center justify-between gap-4">
                        <div className="flex items-center gap-2">
                          <StatusBadge value={message.role} />
                          <StatusBadge value={message.status} />
                        </div>
                        <p className="text-xs text-slate-500">{formatDateTime(message.created_at)}</p>
                      </div>
                      <div className="prose prose-invert max-w-none prose-p:text-slate-200 prose-strong:text-white prose-headings:text-white">
                        <ReactMarkdown>{message.content || '_No content captured._'}</ReactMarkdown>
                      </div>
                      {message.sources?.length ? (
                        <div className="mt-4 flex flex-wrap gap-2 border-t border-white/10 pt-4">
                          {message.sources.map((source) => (
                            <div key={`${message.id}-${source.citation_label}-${source.chunk_id}`} className="rounded-2xl border border-white/10 bg-slate-950/60 px-3 py-2 text-xs text-slate-300">
                              <span className="font-semibold text-cyan-200">[{source.citation_label}]</span> {source.file_name || source.file_id}
                              {source.page_number ? ` | page ${source.page_number}` : ''}
                              {source.row_number ? ` | row ${source.row_number}` : ''}
                            </div>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        ) : null}
      </QueryBoundary>
    </div>
  );
}

function CollectionsView() {
  const token = useToken();
  const query = useQuery({ queryKey: ['collections'], queryFn: () => fetchCollections(token) });
  const items = useMemo(() => (Array.isArray(query.data) ? query.data : query.data?.items ?? []), [query.data]);

  return (
    <div className="space-y-6">
      <SectionHeading eyebrow="Knowledge spaces" title="Collections" description="A quick read-only view of the collections currently available to admins and internal operators." />
      <QueryBoundary isLoading={query.isLoading} error={query.error} onRetry={() => query.refetch()}>
        {items.length ? (
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {items.map((collection) => (
              <Card key={collection.id}>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.3em] text-slate-500">{collection.visibility}</p>
                    <h3 className="mt-3 text-xl font-semibold text-white">{collection.name}</h3>
                  </div>
                  <FolderKanban className="size-5 text-slate-400" />
                </div>
                <p className="mt-4 text-sm leading-7 text-slate-400">{collection.description || 'No description provided for this collection.'}</p>
                <p className="mt-4 text-xs text-slate-500">ID: {collection.id}</p>
              </Card>
            ))}
          </div>
        ) : (
          <EmptyState title="No collections available" description="Collections created through the current API will show up here for admin review." />
        )}
      </QueryBoundary>
    </div>
  );
}

export function SectionIndexView({ section }: { section: string }) {
  switch (section) {
    case 'dashboard':
      return <DashboardView />;
    case 'users':
      return <UsersView />;
    case 'uploads':
      return <UploadsView />;
    case 'jobs':
      return <JobsView />;
    case 'processes':
      return <ProcessesView />;
    case 'activity':
      return <ActivityView />;
    case 'chats':
      return <ChatsView />;
    case 'collections':
      return <CollectionsView />;
    default:
      return <EmptyState title="Unknown admin section" description="This route does not map to a configured admin view yet." />;
  }
}

export function SectionDetailView({ section, id }: { section: string; id: string }) {
  switch (section) {
    case 'users':
      return <UserDetailView id={id} />;
    case 'jobs':
      return <JobDetailView id={id} />;
    case 'chats':
      return <ChatDetailView id={id} />;
    default:
      return <EmptyState title="No detail view available" description="This section does not currently expose an admin detail screen." />;
  }
}
