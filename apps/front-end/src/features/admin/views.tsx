'use client';

import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { Activity, ArrowDownToLine, ArrowRight, Bot, Boxes, ChevronLeft, ChevronRight, Cpu, DatabaseZap, FileClock, Filter, FolderKanban, HardDriveDownload, MessageSquareText, Pencil, Power, ShieldCheck, Trash2, UploadCloud, UserPlus, Users } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis, Area, AreaChart } from 'recharts';
import ReactMarkdown from 'react-markdown';

import { useAuth } from '@/components/auth-provider';
import { Card, EmptyState, ErrorState, MetricCard, ProgressBar, SearchInput, SectionHeading, SkeletonCard, StatusBadge, TableShell, formatBytes, formatDateTime, formatNumber, titleize } from '@/components/ui';
import {
  activateLlmConfig,
  createLlmConfig,
  createUser,
  deleteChats,
  deleteCollections,
  deleteFiles,
  deleteJobs,
  deleteLlmConfig,
  deleteProcesses,
  deleteUsers,
  fetchActiveLlmConfig,
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
  fetchLlmConfigs,
  fetchProcessSummary,
  fetchProcesses,
  fetchUploads,
  fetchUploadSummary,
  updateLlmConfig,
  uploadFiles,
  downloadFile,
} from '@/features/admin/data';
import type { CreateUserPayload, LlmConfigItem, LlmConfigPayload, LlmProviderType, UserRole } from '@/features/admin/types';
import { cn } from '@/lib/utils';

const CHART_COLORS = ['#67e8f9', '#38bdf8', '#818cf8', '#a78bfa', '#f0abfc'];

const PAGE_SIZE = 20;

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

function StatGrid({ items }: { items: Array<{ title: string; value: string; helper?: string; icon: React.ReactNode; accent?: string; href?: string }> }) {
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


function PaginationControls({
  page,
  pageSize,
  itemCount,
  hasNext,
  onPrevious,
  onNext,
}: {
  page: number;
  pageSize: number;
  itemCount: number;
  hasNext?: boolean;
  onPrevious: () => void;
  onNext: () => void;
}) {
  const nextAvailable = hasNext ?? itemCount >= pageSize;

  return (
    <div className="mt-5 flex items-center justify-between gap-4 rounded-2xl border border-white/10 bg-white/4 px-4 py-3 text-sm text-slate-300">
      <p>Page {page} | Showing {itemCount} of up to {pageSize}</p>
      <div className="flex items-center gap-2">
        <button onClick={onPrevious} disabled={page === 1} className="inline-flex items-center gap-2 rounded-full border border-white/10 px-4 py-2 transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"><ChevronLeft className="size-4" />Previous</button>
        <button onClick={onNext} disabled={!nextAvailable} className="inline-flex items-center gap-2 rounded-full border border-white/10 px-4 py-2 transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50">Next<ChevronRight className="size-4" /></button>
      </div>
    </div>
  );
}

function SelectionToolbar({
  selectedCount,
  resourceLabel,
  onDelete,
  onClear,
}: {
  selectedCount: number;
  resourceLabel: string;
  onDelete: () => void;
  onClear: () => void;
}) {
  if (!selectedCount) return null;
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-rose-300/15 bg-rose-500/8 px-4 py-3 text-sm text-rose-50">
      <p>{selectedCount} {resourceLabel} selected</p>
      <div className="flex items-center gap-2">
        <button onClick={onClear} className="rounded-full border border-white/10 px-4 py-2 text-slate-200 transition hover:bg-white/5">Clear</button>
        <button onClick={onDelete} className="inline-flex items-center gap-2 rounded-full border border-rose-300/20 bg-rose-500/15 px-4 py-2 transition hover:bg-rose-500/20"><Trash2 className="size-4" />Delete selected</button>
      </div>
    </div>
  );
}

function UploadDialog() {
  const token = useToken();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [dragActive, setDragActive] = useState(false);

  const mutation = useMutation({
    mutationFn: () => {
      if (!files.length) throw new Error('At least one PDF, CSV, or Excel file is required.');
      return uploadFiles(token, files);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['uploads'] });
      queryClient.invalidateQueries({ queryKey: ['uploads-summary'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
      queryClient.invalidateQueries({ queryKey: ['job-summary'] });
      queryClient.invalidateQueries({ queryKey: ['collections'] });
      setOpen(false);
      setFiles([]);
      setDragActive(false);
    },
  });

  const addFiles = (incoming: FileList | File[] | null | undefined) => {
    if (!incoming) return;
    const next = Array.from(incoming).filter((file) => /\.(pdf|csv|xlsx|xls)$/i.test(file.name));
    setFiles((current) => {
      const merged = [...current];
      for (const file of next) {
        if (!merged.some((item) => item.name === file.name && item.size === file.size && item.lastModified === file.lastModified)) {
          merged.push(file);
        }
      }
      return merged;
    });
  };

  return (
    <>
      <button onClick={() => setOpen(true)} className="inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-400/10 px-5 py-3 text-sm font-medium text-cyan-100 transition hover:bg-cyan-400/15"><UploadCloud className="size-4" />Upload files</button>
      {open ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/75 p-4 backdrop-blur-md">
          <Card className="w-full max-w-2xl p-6">
            <SectionHeading eyebrow="New upload" title="Add source files" description="Upload one or more PDFs, CSVs, or Excel files and the system will place them into the right managed knowledge space automatically. You do not need to choose a collection." />
            <div className="mt-6 grid gap-4">
              <div className="rounded-2xl border border-cyan-300/10 bg-cyan-400/5 px-4 py-4 text-sm leading-6 text-slate-300">
                Files are routed into a system-managed upload collection automatically, so the ingestion pipeline can stay organized without asking the uploader to understand collections first.
              </div>
              <label
                onDragOver={(event) => {
                  event.preventDefault();
                  setDragActive(true);
                }}
                onDragLeave={() => setDragActive(false)}
                onDrop={(event) => {
                  event.preventDefault();
                  setDragActive(false);
                  addFiles(event.dataTransfer.files);
                }}
                className={cn(
                  'flex cursor-pointer flex-col items-center justify-center gap-3 rounded-2xl border border-dashed px-5 py-8 text-center transition',
                  dragActive ? 'border-cyan-300/40 bg-cyan-400/10 text-cyan-100' : 'border-white/10 bg-slate-950/70 text-slate-300 hover:bg-white/5',
                )}
              >
                <UploadCloud className="size-6" />
                <div>
                  <p className="text-sm font-medium text-white">Drag and drop PDF, CSV, or Excel files</p>
                  <p className="mt-1 text-xs text-slate-400">You can select and upload multiple files at the same time.</p>
                </div>
                <input type="file" accept=".pdf,.csv,.xlsx,.xls" multiple onChange={(event) => addFiles(event.target.files)} className="hidden" />
              </label>
              {files.length ? (
                <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-medium text-white">{files.length} file(s) ready</p>
                    <button onClick={() => setFiles([])} className="text-xs text-slate-400 transition hover:text-white">Clear all</button>
                  </div>
                  <div className="mt-3 space-y-2">
                    {files.map((file) => (
                      <div key={`${file.name}-${file.size}-${file.lastModified}`} className="flex items-center justify-between gap-3 rounded-xl border border-white/8 bg-white/[0.03] px-3 py-2 text-sm text-slate-300">
                        <span className="truncate">{file.name}</span>
                        <span className="shrink-0 text-xs text-slate-500">{formatBytes(file.size)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
            {mutation.error ? <p className="mt-4 text-sm text-rose-300">{mutation.error.message}</p> : null}
            <div className="mt-6 flex items-center justify-end gap-3">
              <button onClick={() => { setOpen(false); setFiles([]); setDragActive(false); }} className="rounded-full border border-white/10 px-5 py-3 text-sm text-slate-300 transition hover:bg-white/5">Cancel</button>
              <button onClick={() => mutation.mutate()} disabled={mutation.isPending || !files.length} className="rounded-full bg-gradient-to-r from-cyan-400 to-indigo-400 px-5 py-3 text-sm font-semibold text-slate-950 transition disabled:cursor-not-allowed disabled:opacity-60">{mutation.isPending ? `Uploading ${files.length} file(s)...` : `Start upload${files.length > 1 ? 's' : ''}`}</button>
            </div>
          </Card>
        </div>
      ) : null}
    </>
  );
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
  const router = useRouter();
  const dashboard = useQuery({ queryKey: ['dashboard-summary'], queryFn: () => fetchDashboardSummary(token) });
  const uploadSummary = useQuery({ queryKey: ['upload-summary'], queryFn: () => fetchUploadSummary(token) });
  const jobSummary = useQuery({ queryKey: ['job-summary'], queryFn: () => fetchJobSummary(token) });
  const processSummary = useQuery({ queryKey: ['process-summary'], queryFn: () => fetchProcessSummary(token) });
  const topUploaderData = (uploadSummary.data?.items ?? []).slice(0, 6).map((item) => ({
    ...item,
    ...getUserChartNames(item.full_name, item.email),
  }));
  const uploadLeaderboardData = (summary.data?.items ?? []).slice(0, 8).map((item) => ({
    ...item,
    ...getUserChartNames(item.full_name, item.email),
  }));
  const jobDistribution = [
    { name: 'Queued', value: jobSummary.data?.queued_jobs ?? 0, href: '/jobs' },
    { name: 'Processing', value: jobSummary.data?.processing_jobs ?? 0, href: '/jobs' },
    { name: 'Completed', value: jobSummary.data?.completed_jobs ?? 0, href: '/jobs' },
    { name: 'Failed', value: jobSummary.data?.failed_jobs ?? 0, href: '/jobs' },
  ];

  return (
    <div className="space-y-6">
      <SectionHeading eyebrow="Overview" title="Platform command center" description="Track ingestion health, user growth, chat volume, and operational pressure at a glance." />
      <QueryBoundary isLoading={dashboard.isLoading || uploadSummary.isLoading || jobSummary.isLoading || processSummary.isLoading} error={dashboard.error || uploadSummary.error || jobSummary.error || processSummary.error} onRetry={() => { dashboard.refetch(); uploadSummary.refetch(); jobSummary.refetch(); processSummary.refetch(); }}>
        <StatGrid items={[
          { title: 'Users', value: formatNumber(dashboard.data?.total_users), helper: `${dashboard.data?.admin_users ?? 0} admins | ${dashboard.data?.internal_users ?? 0} internal | ${dashboard.data?.standard_users ?? 0} standard`, icon: <Users className="size-5" />, href: '/users' },
          { title: 'Knowledge Files', value: formatNumber(dashboard.data?.total_files), helper: `${formatBytes(dashboard.data?.total_uploaded_bytes)} stored`, icon: <HardDriveDownload className="size-5" />, href: '/uploads' },
          { title: 'Jobs', value: formatNumber(dashboard.data?.total_jobs), helper: `${dashboard.data?.queue_depth ?? 0} waiting in queue`, icon: <Boxes className="size-5" />, href: '/jobs' },
          { title: 'Chats', value: formatNumber(dashboard.data?.total_chat_sessions), helper: `${dashboard.data?.total_chat_messages ?? 0} messages | ${dashboard.data?.total_chat_citations ?? 0} citations`, icon: <Bot className="size-5" />, href: '/chats' },
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
                <BarChart data={topUploaderData}>
                  <CartesianGrid stroke="rgba(148,163,184,0.08)" vertical={false} />
                  <XAxis dataKey="short_display_name" tick={{ fill: '#94a3b8', fontSize: 12 }} interval={0} angle={-20} height={70} />
                  <YAxis tick={{ fill: '#94a3b8', fontSize: 12 }} tickFormatter={(value) => `${Math.round(value / 1024)} KB`} />
                  <Tooltip
                    cursor={{ fill: 'rgba(255,255,255,0.03)' }}
                    contentStyle={{ background: '#020617', border: '1px solid rgba(148,163,184,0.1)', borderRadius: 18 }}
                    labelFormatter={(_, payload) => String(payload?.[0]?.payload?.display_name ?? '')}
                  />
                  <Bar dataKey="total_uploaded_bytes" radius={[10, 10, 0, 0]} cursor="pointer">
                    {topUploaderData.map((entry, index) => (
                      <Cell key={entry.user_id} fill={CHART_COLORS[index % CHART_COLORS.length]} className="cursor-pointer" onClick={() => router.push(`/users/${entry.user_id}`)} />
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
                  <Pie data={jobDistribution} dataKey="value" innerRadius={70} outerRadius={110} paddingAngle={5} cursor="pointer">
                    {jobDistribution.map((entry, index) => (<Cell key={entry.name} fill={CHART_COLORS[index % CHART_COLORS.length]} className="cursor-pointer" onClick={() => router.push(entry.href)} />))}
                  </Pie>
                  <Tooltip contentStyle={{ background: '#020617', border: '1px solid rgba(148,163,184,0.1)', borderRadius: 18 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <Link href="/processes" className="block"><Card className="bg-white/4 p-4 transition hover:border-cyan-300/20 hover:bg-white/8"><p className="text-sm text-slate-400">Running processes</p><p className="mt-2 text-2xl font-semibold text-white">{formatNumber(processSummary.data?.running_processes)}</p></Card></Link>
              <Link href="/jobs" className="block"><Card className="bg-white/4 p-4 transition hover:border-cyan-300/20 hover:bg-white/8"><p className="text-sm text-slate-400">Queue depth</p><p className="mt-2 text-2xl font-semibold text-white">{formatNumber(processSummary.data?.queue_depth)}</p></Card></Link>
            </div>
          </Card>
        </div>
      </QueryBoundary>
    </div>
  );
}

function UsersView() {
  const token = useToken();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState<string>('');
  const [page, setPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const offset = (page - 1) * PAGE_SIZE;
  const query = useQuery({ queryKey: ['admin-users', page], queryFn: () => fetchAdminUsers(token, { limit: PAGE_SIZE, offset }) });
  const users = useMemo(
    () =>
      (query.data?.items ?? []).filter((item) => {
        const matchesSearch = [item.email, item.full_name, item.role].join(' ').toLowerCase().includes(search.toLowerCase());
        const matchesRole = !roleFilter || item.role === roleFilter;
        return matchesSearch && matchesRole;
      }),
    [query.data?.items, roleFilter, search],
  );

  const deletion = useMutation({
    mutationFn: (ids: string[]) => deleteUsers(token, ids),
    onSuccess: () => {
      setSelectedIds([]);
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
    },
  });

  function toggleSelection(userId: string) {
    setSelectedIds((current) => current.includes(userId) ? current.filter((value) => value !== userId) : [...current, userId]);
  }

  function toggleSelectVisible() {
    const visibleIds = users.map((item) => item.id);
    const allSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedIds.includes(id));
    setSelectedIds(allSelected ? selectedIds.filter((id) => !visibleIds.includes(id)) : Array.from(new Set([...selectedIds, ...visibleIds])));
  }

  async function handleDelete(ids: string[]) {
    if (!ids.length) return;
    if (!window.confirm(`Delete ${ids.length} user(s)? This will also remove their dependent chats, files, jobs, and created collections.`)) return;
    await deletion.mutateAsync(ids);
  }

  return (
    <div className="space-y-6">
      <SectionHeading eyebrow="Identity" title="Users and access" description="Create users, review role assignment, and monitor operational footprint per account." action={<CreateUserDialog />} />
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
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="grid flex-1 gap-3 lg:grid-cols-[minmax(0,1fr)_220px]">
            <SearchInput value={search} onChange={(value) => { setSearch(value); setPage(1); }} placeholder="Search visible users by email, name, or role" />
            <select value={roleFilter} onChange={(event) => { setRoleFilter(event.target.value); setPage(1); }} className="rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none">
              <option value="">All roles</option>
              <option value="admin">Admin</option>
              <option value="internal_user">Internal User</option>
              <option value="user">User</option>
            </select>
          </div>
          <div className="flex items-center gap-3 text-sm text-slate-400">
            <span>Server pagination | {query.data?.items.length ?? 0} loaded on this page</span>
            <button onClick={toggleSelectVisible} className="rounded-full border border-white/10 px-4 py-2 text-sm text-slate-300 transition hover:bg-white/5">Select visible</button>
          </div>
        </div>
        <SelectionToolbar selectedCount={selectedIds.length} resourceLabel="users" onDelete={() => handleDelete(selectedIds)} onClear={() => setSelectedIds([])} />
        <div className="mt-5">
          <QueryBoundary isLoading={query.isLoading} error={query.error} onRetry={() => query.refetch()}>
            {users.length ? (
              <>
                <DataTable headers={['', 'User', 'Role', 'Uploads', 'Jobs', 'Chats', 'Last login', 'Actions']}>
                  {users.map((user) => (
                    <tr key={user.id} className="transition hover:bg-white/5">
                      <td className="px-5 py-4"><input type="checkbox" checked={selectedIds.includes(user.id)} onChange={() => toggleSelection(user.id)} /></td>
                      <td className="px-5 py-4"><p className="font-medium text-white">{user.full_name || 'Unnamed user'}</p><p className="mt-1 text-xs text-slate-500">{user.email}</p></td>
                      <td className="px-5 py-4"><StatusBadge value={user.role} /></td>
                      <td className="px-5 py-4 text-slate-300">{formatNumber(user.file_count)} files | {formatBytes(user.total_uploaded_bytes)}</td>
                      <td className="px-5 py-4 text-slate-300">{formatNumber(user.job_count)}</td>
                      <td className="px-5 py-4 text-slate-300">{formatNumber(user.chat_session_count)}</td>
                      <td className="px-5 py-4 text-slate-400">{formatDateTime(user.last_login_at)}</td>
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-3">
                          <Link href={`/users/${user.id}`} className="inline-flex items-center gap-2 text-cyan-200 hover:text-white">Details <ArrowRight className="size-4" /></Link>
                          <button onClick={() => handleDelete([user.id])} className="inline-flex items-center gap-2 rounded-full border border-rose-300/20 bg-rose-500/10 px-3 py-2 text-xs text-rose-100 transition hover:bg-rose-500/15"><Trash2 className="size-4" />Delete</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </DataTable>
                <PaginationControls page={page} pageSize={PAGE_SIZE} itemCount={query.data?.items.length ?? 0} onPrevious={() => setPage((current) => Math.max(1, current - 1))} onNext={() => setPage((current) => current + 1)} />
              </>
            ) : (
              <EmptyState title="No users matched the current filter" description="Try a broader search or move to another page." />
            )}
          </QueryBoundary>
        </div>
      </Card>
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
  const handleDownloadFile = async (fileId: string, fileName?: string | null) => {
    await downloadFile(token, fileId, fileName || 'download');
  };
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [page, setPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const offset = (page - 1) * PAGE_SIZE;
  const uploads = useQuery({ queryKey: ['uploads', page], queryFn: () => fetchUploads(token, { limit: PAGE_SIZE, offset }) });
  const summary = useQuery({ queryKey: ['uploads-summary'], queryFn: () => fetchUploadSummary(token) });
  const filtered = useMemo(
    () =>
      (uploads.data?.items ?? []).filter((item) => {
        const matchesSearch = [item.original_name, item.uploaded_by_email, item.collection_name, item.latest_job_status, item.latest_job_stage].join(' ').toLowerCase().includes(search.toLowerCase());
        const matchesStatus = !statusFilter || item.latest_job_status === statusFilter || item.latest_job_stage === statusFilter;
        return matchesSearch && matchesStatus;
      }),
    [search, statusFilter, uploads.data?.items],
  );
  const deletion = useMutation({
    mutationFn: (ids: string[]) => deleteFiles(token, ids),
    onSuccess: () => {
      setSelectedIds([]);
      queryClient.invalidateQueries({ queryKey: ['uploads'] });
      queryClient.invalidateQueries({ queryKey: ['uploads-summary'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
      queryClient.invalidateQueries({ queryKey: ['job-summary'] });
      queryClient.invalidateQueries({ queryKey: ['process-summary'] });
    },
  });

  function toggleSelection(fileId: string) {
    setSelectedIds((current) => current.includes(fileId) ? current.filter((value) => value !== fileId) : [...current, fileId]);
  }

  function toggleSelectVisible() {
    const visibleIds = filtered.map((item) => item.id);
    const allSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedIds.includes(id));
    setSelectedIds(allSelected ? selectedIds.filter((id) => !visibleIds.includes(id)) : Array.from(new Set([...selectedIds, ...visibleIds])));
  }

  async function handleDelete(ids: string[]) {
    if (!ids.length) return;
    if (!window.confirm(`Delete ${ids.length} file(s)? This removes file metadata, related jobs, chunks, and stored artifacts.`)) return;
    await deletion.mutateAsync(ids);
  }

  return (
    <div className="space-y-6">
      <SectionHeading eyebrow="Ingestion" title="Uploads and source files" description="Track user upload behavior, ingestion progress, and raw storage volume across the platform." action={<UploadDialog />} />
      <QueryBoundary isLoading={uploads.isLoading || summary.isLoading} error={uploads.error || summary.error} onRetry={() => { uploads.refetch(); summary.refetch(); }}>
        <div className="grid gap-5 md:grid-cols-3">
          <MetricCard title="Files tracked" value={formatNumber(filtered.length)} helper="Visible uploads on this page" icon={<FileClock className="size-5" />} />
          <MetricCard title="Top uploader bytes" value={formatBytes(Math.max(...(summary.data?.items ?? []).map((item) => item.total_uploaded_bytes), 0))} helper="Largest upload footprint by a single user" icon={<Users className="size-5" />} />
          <MetricCard title="Unique uploaders" value={formatNumber(summary.data?.items?.filter((item) => item.file_count > 0).length)} helper="Users with at least one stored file" icon={<HardDriveDownload className="size-5" />} />
        </div>
        <div className="grid gap-6 xl:grid-cols-[0.85fr_1.15fr]">
          <Card>
            <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Upload leaderboard</p>
            <div className="mt-6 h-80">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={uploadLeaderboardData}>
                  <defs>
                    <linearGradient id="uploadArea" x1="0" x2="0" y1="0" y2="1">
                      <stop offset="0%" stopColor="#67e8f9" stopOpacity={0.5} />
                      <stop offset="100%" stopColor="#67e8f9" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="rgba(148,163,184,0.08)" vertical={false} />
                  <XAxis dataKey="short_display_name" tick={{ fill: '#94a3b8', fontSize: 12 }} interval={0} angle={-20} height={70} />
                  <YAxis tick={{ fill: '#94a3b8', fontSize: 12 }} tickFormatter={(value) => `${Math.round(value / 1024)} KB`} />
                  <Tooltip
                    contentStyle={{ background: '#020617', border: '1px solid rgba(148,163,184,0.1)', borderRadius: 18 }}
                    labelFormatter={(_, payload) => String(payload?.[0]?.payload?.display_name ?? '')}
                  />
                  <Area type="monotone" dataKey="total_uploaded_bytes" stroke="#67e8f9" fill="url(#uploadArea)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Card>
          <Card>
            <div className="flex flex-col gap-4">
              <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_220px_auto] lg:items-center">
                <SearchInput value={search} onChange={(value) => { setSearch(value); setPage(1); }} placeholder="Search visible uploads, users, collections, or status" />
                <select value={statusFilter} onChange={(event) => { setStatusFilter(event.target.value); setPage(1); }} className="rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none">
                  <option value="">All statuses</option>
                  <option value="queued">Queued</option>
                  <option value="processing">Processing</option>
                  <option value="completed">Completed</option>
                  <option value="failed">Failed</option>
                  <option value="uploading">Uploading</option>
                  <option value="parsing">Parsing</option>
                  <option value="chunking">Chunking</option>
                  <option value="embedding">Embedding</option>
                  <option value="indexing">Indexing</option>
                </select>
                <button onClick={toggleSelectVisible} className="rounded-full border border-white/10 px-4 py-2 text-sm text-slate-300 transition hover:bg-white/5">Select visible</button>
              </div>
            </div>
            <SelectionToolbar selectedCount={selectedIds.length} resourceLabel="files" onDelete={() => handleDelete(selectedIds)} onClear={() => setSelectedIds([])} />
            <div className="mt-5">
              {filtered.length ? (
                <>
                  <DataTable headers={['', 'File', 'Owner', 'Collection', 'Stage', 'Progress', 'Size', 'Actions']}>
                    {filtered.map((item) => (
                      <tr key={item.id} className="transition hover:bg-white/5">
                        <td className="px-5 py-4"><input type="checkbox" checked={selectedIds.includes(item.id)} onChange={() => toggleSelection(item.id)} /></td>
                        <td className="px-5 py-4"><p className="font-medium text-white">{item.original_name}</p><p className="mt-1 text-xs text-slate-500">{formatDateTime(item.created_at)}</p></td>
                        <td className="px-5 py-4 text-slate-300">{item.uploaded_by_full_name || item.uploaded_by_email}</td>
                        <td className="px-5 py-4 text-slate-300">{item.collection_name || 'No collection'}</td>
                        <td className="px-5 py-4"><StatusBadge value={item.latest_job_stage || item.latest_job_status || 'unknown'} /></td>
                        <td className="px-5 py-4 min-w-40"><ProgressBar value={item.latest_job_progress ?? 0} /></td>
                        <td className="px-5 py-4 text-slate-300">{formatBytes(item.size_bytes)}</td>
                        <td className="px-5 py-4"><button onClick={() => handleDelete([item.id])} className="inline-flex items-center gap-2 rounded-full border border-rose-300/20 bg-rose-500/10 px-3 py-2 text-xs text-rose-100 transition hover:bg-rose-500/15"><Trash2 className="size-4" />Delete</button></td>
                      </tr>
                    ))}
                  </DataTable>
                  <PaginationControls page={page} pageSize={PAGE_SIZE} itemCount={uploads.data?.items.length ?? 0} onPrevious={() => setPage((current) => Math.max(1, current - 1))} onNext={() => setPage((current) => current + 1)} />
                </>
              ) : (
                <EmptyState title="No uploads matched the current filter" description="Try a broader search, another page, or upload a new file." />
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
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<string>('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const offset = (page - 1) * PAGE_SIZE;
  const jobs = useQuery({ queryKey: ['jobs', status, page], queryFn: () => fetchJobs(token, { limit: PAGE_SIZE, offset, status: status || undefined }) });
  const summary = useQuery({ queryKey: ['jobs-summary'], queryFn: () => fetchJobSummary(token) });
  const filteredJobs = useMemo(() => (jobs.data?.items ?? []).filter((job) => [job.file_name, job.collection_name, job.status, job.current_stage].join(' ').toLowerCase().includes(search.toLowerCase())), [jobs.data?.items, search]);
  const deletion = useMutation({
    mutationFn: (ids: string[]) => deleteJobs(token, ids),
    onSuccess: () => {
      setSelectedIds([]);
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      queryClient.invalidateQueries({ queryKey: ['jobs-summary'] });
      queryClient.invalidateQueries({ queryKey: ['uploads'] });
    },
  });

  function toggleSelection(jobId: string) {
    setSelectedIds((current) => current.includes(jobId) ? current.filter((value) => value !== jobId) : [...current, jobId]);
  }

  function toggleSelectVisible() {
    const visibleIds = filteredJobs.map((item) => item.id);
    const allSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedIds.includes(id));
    setSelectedIds(allSelected ? selectedIds.filter((id) => !visibleIds.includes(id)) : Array.from(new Set([...selectedIds, ...visibleIds])));
  }

  async function handleDelete(ids: string[]) {
    if (!ids.length) return;
    if (!window.confirm(`Delete ${ids.length} job(s)? This removes stage history and background task links for those jobs.`)) return;
    await deletion.mutateAsync(ids);
  }

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
              <button key={value || 'all'} onClick={() => { setStatus(value); setPage(1); }} className={cn('rounded-full px-4 py-2 text-sm transition', status === value ? 'bg-cyan-400 text-slate-950' : 'border border-white/10 bg-white/5 text-slate-300 hover:bg-white/10')}>
                {value ? titleize(value) : 'All'}
              </button>
            ))}
            <div className="min-w-72 flex-1"><SearchInput value={search} onChange={setSearch} placeholder="Search visible jobs by file, collection, status, or stage" /></div>
            <button onClick={toggleSelectVisible} className="rounded-full border border-white/10 px-4 py-2 text-sm text-slate-300 transition hover:bg-white/5">Select visible</button>
          </div>
          <SelectionToolbar selectedCount={selectedIds.length} resourceLabel="jobs" onDelete={() => handleDelete(selectedIds)} onClear={() => setSelectedIds([])} />
          <div className="mt-5">
            {filteredJobs.length ? (
              <>
                <DataTable headers={['', 'Job', 'Status', 'Chunks', 'Progress', 'Created', 'Actions']}>
                  {filteredJobs.map((job) => (
                    <tr key={job.id} className="transition hover:bg-white/5">
                      <td className="px-5 py-4"><input type="checkbox" checked={selectedIds.includes(job.id)} onChange={() => toggleSelection(job.id)} /></td>
                      <td className="px-5 py-4"><p className="font-medium text-white">{job.file_name}</p><p className="mt-1 text-xs text-slate-500">{job.collection_name || 'No collection'}</p></td>
                      <td className="px-5 py-4"><div className="flex flex-col gap-2"><StatusBadge value={job.status} /><StatusBadge value={job.current_stage} /></div></td>
                      <td className="px-5 py-4 text-slate-300">{formatNumber(job.processed_chunks)} / {formatNumber(job.total_chunks)}</td>
                      <td className="px-5 py-4 min-w-40"><ProgressBar value={job.progress_percent} /></td>
                      <td className="px-5 py-4 text-slate-400">{formatDateTime(job.created_at)}</td>
                      <td className="px-5 py-4"><div className="flex items-center gap-3"><Link href={`/jobs/${job.id}`} className="inline-flex items-center gap-2 text-cyan-200 hover:text-white">Details <ArrowRight className="size-4" /></Link><button onClick={() => handleDelete([job.id])} className="inline-flex items-center gap-2 rounded-full border border-rose-300/20 bg-rose-500/10 px-3 py-2 text-xs text-rose-100 transition hover:bg-rose-500/15"><Trash2 className="size-4" />Delete</button></div></td>
                    </tr>
                  ))}
                </DataTable>
                <PaginationControls page={page} pageSize={PAGE_SIZE} itemCount={jobs.data?.items.length ?? 0} onPrevious={() => setPage((current) => Math.max(1, current - 1))} onNext={() => setPage((current) => current + 1)} />
              </>
            ) : (
              <EmptyState title="No jobs available" description="Try a different filter, another page, or wait for new ingestion jobs." />
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
  const queryClient = useQueryClient();
  const summary = useQuery({ queryKey: ['process-summary'], queryFn: () => fetchProcessSummary(token) });
  const [status, setStatus] = useState<string>('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const offset = (page - 1) * PAGE_SIZE;
  const processes = useQuery({ queryKey: ['processes', status, page], queryFn: () => fetchProcesses(token, { limit: PAGE_SIZE, offset, status: status || undefined }) });
  const filtered = useMemo(() => (processes.data?.items ?? []).filter((process) => [process.task_type, process.status, process.current_stage, process.file_name, process.worker_id].join(' ').toLowerCase().includes(search.toLowerCase())), [processes.data?.items, search]);
  const deletion = useMutation({
    mutationFn: (ids: string[]) => deleteProcesses(token, ids),
    onSuccess: () => {
      setSelectedIds([]);
      queryClient.invalidateQueries({ queryKey: ['processes'] });
      queryClient.invalidateQueries({ queryKey: ['process-summary'] });
    },
  });

  function toggleSelection(processId: string) {
    setSelectedIds((current) => current.includes(processId) ? current.filter((value) => value !== processId) : [...current, processId]);
  }

  function toggleSelectVisible() {
    const visibleIds = filtered.map((item) => item.id);
    const allSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedIds.includes(id));
    setSelectedIds(allSelected ? selectedIds.filter((id) => !visibleIds.includes(id)) : Array.from(new Set([...selectedIds, ...visibleIds])));
  }

  async function handleDelete(ids: string[]) {
    if (!ids.length) return;
    if (!window.confirm(`Delete ${ids.length} process record(s)?`)) return;
    await deletion.mutateAsync(ids);
  }

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
        <Card>
          <div className="flex flex-wrap items-center gap-3">
            {['', 'queued', 'running', 'completed', 'failed'].map((value) => (
              <button key={value || 'all'} onClick={() => { setStatus(value); setPage(1); }} className={cn('rounded-full px-4 py-2 text-sm transition', status === value ? 'bg-cyan-400 text-slate-950' : 'border border-white/10 bg-white/5 text-slate-300 hover:bg-white/10')}>
                {value ? titleize(value) : 'All'}
              </button>
            ))}
            <div className="min-w-72 flex-1"><SearchInput value={search} onChange={setSearch} placeholder="Search visible processes by worker, file, task, or stage" /></div>
            <button onClick={toggleSelectVisible} className="rounded-full border border-white/10 px-4 py-2 text-sm text-slate-300 transition hover:bg-white/5">Select visible</button>
          </div>
          <SelectionToolbar selectedCount={selectedIds.length} resourceLabel="processes" onDelete={() => handleDelete(selectedIds)} onClear={() => setSelectedIds([])} />
          {filtered.length ? (
            <>
              <DataTable headers={['', 'Process', 'Status', 'Worker', 'Progress', 'File', 'Updated', 'Actions']}>
                {filtered.map((process) => (
                  <tr key={process.id} className="transition hover:bg-white/5">
                    <td className="px-5 py-4"><input type="checkbox" checked={selectedIds.includes(process.id)} onChange={() => toggleSelection(process.id)} /></td>
                    <td className="px-5 py-4"><p className="font-medium text-white">{titleize(process.task_type)}</p><p className="mt-1 text-xs text-slate-500">{titleize(process.current_stage)}</p></td>
                    <td className="px-5 py-4"><StatusBadge value={process.status} /></td>
                    <td className="px-5 py-4 text-slate-300">{process.worker_id || 'Unassigned'}</td>
                    <td className="px-5 py-4 min-w-40"><ProgressBar value={process.progress_percent} /></td>
                    <td className="px-5 py-4 text-slate-300">{process.file_name || 'Unknown file'}</td>
                    <td className="px-5 py-4 text-slate-400">{formatDateTime(process.updated_at || process.heartbeat_at)}</td>
                    <td className="px-5 py-4"><button onClick={() => handleDelete([process.id])} className="inline-flex items-center gap-2 rounded-full border border-rose-300/20 bg-rose-500/10 px-3 py-2 text-xs text-rose-100 transition hover:bg-rose-500/15"><Trash2 className="size-4" />Delete</button></td>
                  </tr>
                ))}
              </DataTable>
              <PaginationControls page={page} pageSize={PAGE_SIZE} itemCount={processes.data?.items.length ?? 0} onPrevious={() => setPage((current) => Math.max(1, current - 1))} onNext={() => setPage((current) => current + 1)} />
            </>
          ) : (
            <EmptyState title="No background processes found" description="Try a different filter or wait for workers to pick up new ingestion tasks." />
          )}
        </Card>
      </QueryBoundary>
    </div>
  );
}

function ActivityView() {
  const token = useToken();
  const [search, setSearch] = useState('');
  const [visibilityFilter, setVisibilityFilter] = useState('');
  const [page, setPage] = useState(1);
  const offset = (page - 1) * PAGE_SIZE;
  const query = useQuery({ queryKey: ['activity', page], queryFn: () => fetchActivity(token, { limit: PAGE_SIZE, offset }) });
  const items = useMemo(
    () =>
      (query.data?.items ?? []).filter((item) => {
        const matchesSearch = [item.activity_type, item.description, item.actor_email, item.target_type, item.target_id].join(' ').toLowerCase().includes(search.toLowerCase());
        const matchesVisibility = !visibilityFilter || item.visibility === visibilityFilter;
        return matchesSearch && matchesVisibility;
      }),
    [query.data?.items, search, visibilityFilter],
  );

  return (
    <div className="space-y-6">
      <SectionHeading eyebrow="Audit" title="Recent activity" description="Follow the most recent operational and user actions across authentication, uploads, jobs, and chat." />
      <Card>
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_220px] lg:items-center">
          <SearchInput value={search} onChange={(value) => { setSearch(value); setPage(1); }} placeholder="Search visible activity by actor, event type, target, or description" />
          <select value={visibilityFilter} onChange={(event) => { setVisibilityFilter(event.target.value); setPage(1); }} className="rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none">
            <option value="">All visibility</option>
            <option value="foreground">Foreground</option>
            <option value="background">Background</option>
            <option value="system">System</option>
          </select>
        </div>
        <div className="mt-5">
          <QueryBoundary isLoading={query.isLoading} error={query.error} onRetry={() => query.refetch()}>
            {items.length ? (
              <>
                <div className="space-y-4">
                  {items.map((item) => (
                    <motion.div key={item.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
                      <Card>
                        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                          <div>
                            <p className="text-xs uppercase tracking-[0.3em] text-slate-500">{titleize(item.activity_type)}</p>
                            <p className="mt-3 text-lg font-semibold text-white">{item.description}</p>
                            <p className="mt-2 text-sm text-slate-400">Actor: {item.actor_email || item.actor_user_id || 'System'} | Target: {item.target_type || 'n/a'}{item.target_id ? ` | ${item.target_id}` : ''}</p>
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
                <PaginationControls page={page} pageSize={PAGE_SIZE} itemCount={query.data?.items.length ?? 0} onPrevious={() => setPage((current) => Math.max(1, current - 1))} onNext={() => setPage((current) => current + 1)} />
              </>
            ) : (
              <EmptyState title="No recent activity" description="Try another page or a broader filter to inspect more recent operational events." />
            )}
          </QueryBoundary>
        </div>
      </Card>
    </div>
  );
}

function ChatsView() {
  const token = useToken();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [page, setPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const offset = (page - 1) * PAGE_SIZE;
  const query = useQuery({ queryKey: ['admin-chats', page], queryFn: () => fetchChats(token, { limit: PAGE_SIZE, offset }) });
  const items = useMemo(
    () =>
      (query.data?.items ?? []).filter((item) => {
        const matchesSearch = [item.title, item.user_email, item.user_full_name, item.latest_assistant_status].join(' ').toLowerCase().includes(search.toLowerCase());
        const matchesStatus = !statusFilter || item.latest_assistant_status === statusFilter;
        return matchesSearch && matchesStatus;
      }),
    [query.data?.items, search, statusFilter],
  );
  const deletion = useMutation({
    mutationFn: (ids: string[]) => deleteChats(token, ids),
    onSuccess: () => {
      setSelectedIds([]);
      queryClient.invalidateQueries({ queryKey: ['admin-chats'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
    },
  });

  function toggleSelection(sessionId: string) {
    setSelectedIds((current) => current.includes(sessionId) ? current.filter((value) => value !== sessionId) : [...current, sessionId]);
  }

  function toggleSelectVisible() {
    const visibleIds = items.map((item) => item.id);
    const allSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedIds.includes(id));
    setSelectedIds(allSelected ? selectedIds.filter((id) => !visibleIds.includes(id)) : Array.from(new Set([...selectedIds, ...visibleIds])));
  }

  async function handleDelete(ids: string[]) {
    if (!ids.length) return;
    if (!window.confirm(`Delete ${ids.length} chat session(s)? This removes their messages and citations.`)) return;
    await deletion.mutateAsync(ids);
  }

  return (
    <div className="space-y-6">
      <SectionHeading eyebrow="Chat audit" title="User chat sessions" description="Review grounded conversations in a read-only interface, including assistant message health and citation counts." />
      <Card>
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_220px_auto] lg:items-center">
          <SearchInput value={search} onChange={(value) => { setSearch(value); setPage(1); }} placeholder="Search visible sessions by title, user, or assistant status" />
          <select value={statusFilter} onChange={(event) => { setStatusFilter(event.target.value); setPage(1); }} className="rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none">
            <option value="">All assistant states</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="streaming">Streaming</option>
          </select>
          <button onClick={toggleSelectVisible} className="rounded-full border border-white/10 px-4 py-2 text-sm text-slate-300 transition hover:bg-white/5">Select visible</button>
        </div>
        <SelectionToolbar selectedCount={selectedIds.length} resourceLabel="chat sessions" onDelete={() => handleDelete(selectedIds)} onClear={() => setSelectedIds([])} />
        <div className="mt-5">
          <QueryBoundary isLoading={query.isLoading} error={query.error} onRetry={() => query.refetch()}>
            {items.length ? (
              <>
                <DataTable headers={['', 'Session', 'User', 'Messages', 'Assistant', 'Updated', 'Actions']}>
                  {items.map((session) => (
                    <tr key={session.id} className="transition hover:bg-white/5">
                      <td className="px-5 py-4"><input type="checkbox" checked={selectedIds.includes(session.id)} onChange={() => toggleSelection(session.id)} /></td>
                      <td className="px-5 py-4"><p className="font-medium text-white">{session.title}</p><p className="mt-1 text-xs text-slate-500">{session.id}</p></td>
                      <td className="px-5 py-4 text-slate-300">{session.user_full_name || session.user_email}</td>
                      <td className="px-5 py-4 text-slate-300">{formatNumber(session.message_count)} messages | {formatNumber(session.citation_count)} citations</td>
                      <td className="px-5 py-4"><StatusBadge value={session.latest_assistant_status || 'unknown'} /></td>
                      <td className="px-5 py-4 text-slate-400">{formatDateTime(session.updated_at)}</td>
                      <td className="px-5 py-4"><div className="flex items-center gap-3"><Link href={`/chats/${session.id}`} className="inline-flex items-center gap-2 text-cyan-200 hover:text-white">Open <ArrowRight className="size-4" /></Link><button onClick={() => handleDelete([session.id])} className="inline-flex items-center gap-2 rounded-full border border-rose-300/20 bg-rose-500/10 px-3 py-2 text-xs text-rose-100 transition hover:bg-rose-500/15"><Trash2 className="size-4" />Delete</button></div></td>
                    </tr>
                  ))}
                </DataTable>
                <PaginationControls page={page} pageSize={PAGE_SIZE} itemCount={query.data?.items.length ?? 0} onPrevious={() => setPage((current) => Math.max(1, current - 1))} onNext={() => setPage((current) => current + 1)} />
              </>
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
  const handleDownloadFile = async (fileId: string, fileName?: string | null) => {
    await downloadFile(token, fileId, fileName || 'download');
  };
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
                            <button key={`${message.id}-${source.file_id || source.file_name || source.chunk_id}`} onClick={() => void handleDownloadFile(source.file_id, source.file_name)} className="rounded-2xl border border-white/10 bg-slate-950/60 px-3 py-2 text-xs text-slate-300 transition hover:bg-white/5">
                              <span className="font-semibold text-cyan-200">[{source.citation_label}]</span> {source.file_name || source.file_id}
                            </button>
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


function createLlmFormState(config?: LlmConfigItem): LlmConfigPayload {
  return {
    name: config?.name ?? '',
    provider: config?.provider ?? 'anthropic',
    base_url: config?.base_url ?? '',
    api_key: '',
    clear_api_key: false,
    model: config?.model ?? '',
    timeout_seconds: config?.timeout_seconds ?? 180,
    max_output_tokens: config?.max_output_tokens ?? 1400,
    temperature: config?.temperature ?? 0.6,
    top_p: config?.top_p ?? 0.95,
    reasoning_effort: config?.reasoning_effort ?? '',
    is_enabled: config?.is_enabled ?? true,
    activate: config?.is_active ?? false,
    metadata: config?.metadata ?? {},
  };
}

function ModelsView() {
  const token = useToken();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [providerFilter, setProviderFilter] = useState<LlmProviderType | ''>('');
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState(false);
  const [editingConfig, setEditingConfig] = useState<LlmConfigItem | null>(null);
  const [form, setForm] = useState<LlmConfigPayload>(() => createLlmFormState());
  const configsQuery = useQuery({ queryKey: ['llm-configs'], queryFn: () => fetchLlmConfigs(token) });
  const activeQuery = useQuery({ queryKey: ['llm-active'], queryFn: () => fetchActiveLlmConfig(token) });

  const filteredItems = useMemo(
    () =>
      (configsQuery.data?.items ?? []).filter((item) => {
        const matchesSearch = [item.name, item.provider, item.model, item.base_url, item.api_key_masked].join(' ').toLowerCase().includes(search.toLowerCase());
        const matchesProvider = !providerFilter || item.provider === providerFilter;
        return matchesSearch && matchesProvider;
      }),
    [configsQuery.data?.items, providerFilter, search],
  );
  const pagedItems = useMemo(() => filteredItems.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE), [filteredItems, page]);

  const createMutation = useMutation({
    mutationFn: (payload: LlmConfigPayload) => createLlmConfig(token, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llm-configs'] });
      queryClient.invalidateQueries({ queryKey: ['llm-active'] });
      setOpen(false);
      setEditingConfig(null);
      setForm(createLlmFormState());
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ configId, payload }: { configId: string; payload: LlmConfigPayload }) => updateLlmConfig(token, configId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llm-configs'] });
      queryClient.invalidateQueries({ queryKey: ['llm-active'] });
      setOpen(false);
      setEditingConfig(null);
      setForm(createLlmFormState());
    },
  });

  const activateMutation = useMutation({
    mutationFn: (configId: string) => activateLlmConfig(token, configId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llm-configs'] });
      queryClient.invalidateQueries({ queryKey: ['llm-active'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (configId: string) => deleteLlmConfig(token, configId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llm-configs'] });
      queryClient.invalidateQueries({ queryKey: ['llm-active'] });
    },
  });

  function openCreateDialog() {
    setEditingConfig(null);
    setForm(createLlmFormState());
    setOpen(true);
  }

  function openEditDialog(config: LlmConfigItem) {
    setEditingConfig(config);
    setForm(createLlmFormState(config));
    setOpen(true);
  }

  async function handleSubmit() {
    if (!form.name.trim() || !form.model.trim()) return;
    if (editingConfig) {
      await updateMutation.mutateAsync({ configId: editingConfig.id, payload: form });
      return;
    }
    await createMutation.mutateAsync(form);
  }

  async function handleDelete(config: LlmConfigItem) {
    if (!window.confirm(`Delete LLM config '${config.name}'?`)) return;
    await deleteMutation.mutateAsync(config.id);
  }

  const active = activeQuery.data ?? configsQuery.data?.items.find((item) => item.is_active) ?? null;
  const pending = createMutation.isPending || updateMutation.isPending;

  return (
    <div className="space-y-6">
      <SectionHeading eyebrow="Inference control" title="Models and providers" description="Create cloud or self-hosted LLM configs, then switch the active provider for new chat requests without restarting the API." action={<button onClick={openCreateDialog} className="inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-400/10 px-5 py-3 text-sm font-medium text-cyan-100 transition hover:bg-cyan-400/15"><Cpu className="size-4" />Add model config</button>} />
      <QueryBoundary isLoading={configsQuery.isLoading || activeQuery.isLoading} error={configsQuery.error || activeQuery.error} onRetry={() => { configsQuery.refetch(); activeQuery.refetch(); }}>
        {active ? (
          <Card>
            <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Active runtime</p>
                <h3 className="mt-3 text-2xl font-semibold text-white">{active.name}</h3>
                <p className="mt-2 text-sm text-slate-400">{active.provider} | {active.model}</p>
                <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-400">Changes here apply to new `/chat` requests immediately. No API restart is required. Use `openai_compatible` for self-hosted providers like vLLM, Ollama bridges, or other OpenAI-style local inference servers.</p>
              </div>
              <div className="grid gap-3 text-sm text-slate-300">
                <div className="flex items-center gap-2"><StatusBadge value={active.is_active ? 'active' : 'inactive'} /><StatusBadge value={active.provider} /></div>
                <p>URL: <span className="text-white">{active.base_url || 'Provider default'}</span></p>
                <p>Key: <span className="text-white">{active.api_key_masked || 'Not set'}</span></p>
                <p>Tokens: <span className="text-white">{formatNumber(active.max_output_tokens)}</span> | Timeout: <span className="text-white">{active.timeout_seconds}s</span></p>
              </div>
            </div>
          </Card>
        ) : null}

        <Card>
          <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_220px] lg:items-center">
            <SearchInput value={search} onChange={(value) => { setSearch(value); setPage(1); }} placeholder="Search configs by name, provider, model, or base URL" />
            <select value={providerFilter} onChange={(event) => { setProviderFilter(event.target.value as LlmProviderType | ''); setPage(1); }} className="rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none">
              <option value="">All providers</option>
              <option value="anthropic">Anthropic</option>
              <option value="openai">OpenAI</option>
              <option value="gemini">Google Gemini</option>
              <option value="openai_compatible">OpenAI Compatible / Self-hosted</option>
            </select>
          </div>
          <div className="mt-5">
            {pagedItems.length ? (
              <>
                <div className="grid gap-5 xl:grid-cols-2">
                  {pagedItems.map((config) => (
                    <Card key={config.id} className="bg-white/4">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <div className="flex items-center gap-2">
                            <h3 className="text-xl font-semibold text-white">{config.name}</h3>
                            {config.is_active ? <StatusBadge value="active" /> : null}
                            {!config.is_enabled ? <StatusBadge value="disabled" /> : null}
                          </div>
                          <p className="mt-2 text-sm text-slate-400">{config.provider} | {config.model}</p>
                        </div>
                        <Cpu className="size-5 text-slate-400" />
                      </div>
                      <div className="mt-5 space-y-2 text-sm text-slate-300">
                        <p>Base URL: <span className="text-white">{config.base_url || 'Provider default'}</span></p>
                        <p>API Key: <span className="text-white">{config.api_key_masked || 'Not set'}</span></p>
                        <p>Timeout: <span className="text-white">{config.timeout_seconds}s</span> | Max tokens: <span className="text-white">{formatNumber(config.max_output_tokens)}</span></p>
                        <p>Temperature: <span className="text-white">{config.temperature}</span> | Top P: <span className="text-white">{config.top_p}</span></p>
                      </div>
                      <div className="mt-6 flex flex-wrap items-center gap-3">
                        {!config.is_active ? <button onClick={() => activateMutation.mutate(config.id)} disabled={activateMutation.isPending} className="inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-400/10 px-4 py-2 text-sm text-cyan-100 transition hover:bg-cyan-400/15 disabled:opacity-60"><Power className="size-4" />Activate</button> : null}
                        <button onClick={() => openEditDialog(config)} className="inline-flex items-center gap-2 rounded-full border border-white/10 px-4 py-2 text-sm text-slate-200 transition hover:bg-white/5"><Pencil className="size-4" />Edit</button>
                        <button onClick={() => handleDelete(config)} disabled={config.is_active || deleteMutation.isPending} className="inline-flex items-center gap-2 rounded-full border border-rose-300/20 bg-rose-500/10 px-4 py-2 text-sm text-rose-100 transition hover:bg-rose-500/15 disabled:cursor-not-allowed disabled:opacity-60"><Trash2 className="size-4" />Delete</button>
                      </div>
                    </Card>
                  ))}
                </div>
                <PaginationControls page={page} pageSize={PAGE_SIZE} itemCount={pagedItems.length} hasNext={page * PAGE_SIZE < filteredItems.length} onPrevious={() => setPage((current) => Math.max(1, current - 1))} onNext={() => setPage((current) => current + 1)} />
              </>
            ) : (
              <EmptyState title="No model configs matched the current filter" description="Create a provider config or broaden the search to inspect available runtime options." />
            )}
          </div>
        </Card>
      </QueryBoundary>

      {open ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/75 p-4 backdrop-blur-md">
          <Card className="w-full max-w-3xl p-6">
            <SectionHeading eyebrow="Runtime config" title={editingConfig ? 'Edit model config' : 'Create model config'} description="Switching the active config changes the LLM backend for new chat requests immediately. Use OpenAI Compatible for self-hosted endpoints like vLLM later." />
            <div className="mt-6 grid gap-4 md:grid-cols-2">
              <label className="grid gap-2 text-sm text-slate-300">
                <span className="text-xs uppercase tracking-[0.24em] text-slate-500">Display name</span>
                <input className="rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none" placeholder="Claude Production" value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} />
              </label>
              <label className="grid gap-2 text-sm text-slate-300">
                <span className="text-xs uppercase tracking-[0.24em] text-slate-500">Provider</span>
                <select value={form.provider} onChange={(event) => setForm((current) => ({ ...current, provider: event.target.value as LlmProviderType }))} className="rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none">
                  <option value="anthropic">Anthropic / Claude</option>
                  <option value="openai">OpenAI</option>
                  <option value="gemini">Google Gemini</option>
                  <option value="openai_compatible">OpenAI Compatible / Self-hosted</option>
                </select>
              </label>
              <label className="grid gap-2 text-sm text-slate-300 md:col-span-2">
                <span className="text-xs uppercase tracking-[0.24em] text-slate-500">Model name</span>
                <input className="rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none" placeholder="claude-sonnet-4-5" value={form.model} onChange={(event) => setForm((current) => ({ ...current, model: event.target.value }))} />
              </label>
              <label className="grid gap-2 text-sm text-slate-300 md:col-span-2">
                <span className="text-xs uppercase tracking-[0.24em] text-slate-500">Base URL</span>
                <input className="rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none" placeholder="Leave blank for Anthropic, OpenAI, or Gemini defaults, or add your self-hosted endpoint" value={form.base_url ?? ''} onChange={(event) => setForm((current) => ({ ...current, base_url: event.target.value }))} />
              </label>
              <label className="grid gap-2 text-sm text-slate-300 md:col-span-2">
                <span className="text-xs uppercase tracking-[0.24em] text-slate-500">API key</span>
                <input className="rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none" placeholder={editingConfig ? 'Leave blank to keep existing key' : 'Paste provider API key'} value={form.api_key ?? ''} onChange={(event) => setForm((current) => ({ ...current, api_key: event.target.value }))} />
              </label>
              <label className="grid gap-2 text-sm text-slate-300">
                <span className="text-xs uppercase tracking-[0.24em] text-slate-500">Timeout seconds</span>
                <input type="number" min={1} max={600} className="rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none" placeholder="180" value={form.timeout_seconds} onChange={(event) => setForm((current) => ({ ...current, timeout_seconds: Number(event.target.value || 0) }))} />
              </label>
              <label className="grid gap-2 text-sm text-slate-300">
                <span className="text-xs uppercase tracking-[0.24em] text-slate-500">Max output tokens</span>
                <input type="number" min={1} max={32768} className="rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none" placeholder="1400" value={form.max_output_tokens} onChange={(event) => setForm((current) => ({ ...current, max_output_tokens: Number(event.target.value || 0) }))} />
              </label>
              <label className="grid gap-2 text-sm text-slate-300">
                <span className="text-xs uppercase tracking-[0.24em] text-slate-500">Temperature</span>
                <input type="number" step="0.1" min={0} max={2} className="rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none" placeholder="0.4" value={form.temperature} onChange={(event) => setForm((current) => ({ ...current, temperature: Number(event.target.value || 0) }))} />
              </label>
              <label className="grid gap-2 text-sm text-slate-300">
                <span className="text-xs uppercase tracking-[0.24em] text-slate-500">Top P</span>
                <input type="number" step="0.05" min={0} max={1} className="rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none" placeholder="0.95" value={form.top_p} onChange={(event) => setForm((current) => ({ ...current, top_p: Number(event.target.value || 0) }))} />
              </label>
              <label className="grid gap-2 text-sm text-slate-300 md:col-span-2">
                <span className="text-xs uppercase tracking-[0.24em] text-slate-500">Reasoning effort</span>
                <input className="rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none" placeholder="Optional, only if your provider supports it" value={form.reasoning_effort ?? ''} onChange={(event) => setForm((current) => ({ ...current, reasoning_effort: event.target.value }))} />
              </label>
            </div>
            <div className="mt-5 flex flex-wrap items-center gap-4 text-sm text-slate-300">
              <label className="inline-flex items-center gap-2"><input type="checkbox" checked={form.is_enabled} onChange={(event) => setForm((current) => ({ ...current, is_enabled: event.target.checked }))} />Enabled</label>
              <label className="inline-flex items-center gap-2"><input type="checkbox" checked={form.activate} onChange={(event) => setForm((current) => ({ ...current, activate: event.target.checked }))} />Activate after save</label>
              {editingConfig ? <label className="inline-flex items-center gap-2"><input type="checkbox" checked={Boolean(form.clear_api_key)} onChange={(event) => setForm((current) => ({ ...current, clear_api_key: event.target.checked }))} />Clear stored API key</label> : null}
            </div>
            {createMutation.error || updateMutation.error ? <p className="mt-4 text-sm text-rose-300">{(createMutation.error || updateMutation.error)?.message}</p> : null}
            <div className="mt-6 flex items-center justify-end gap-3">
              <button onClick={() => { setOpen(false); setEditingConfig(null); setForm(createLlmFormState()); }} className="rounded-full border border-white/10 px-5 py-3 text-sm text-slate-300 transition hover:bg-white/5">Cancel</button>
              <button onClick={handleSubmit} disabled={pending || !form.name.trim() || !form.model.trim()} className="rounded-full bg-gradient-to-r from-cyan-400 to-indigo-400 px-5 py-3 text-sm font-semibold text-slate-950 transition disabled:cursor-not-allowed disabled:opacity-60">{pending ? 'Saving...' : editingConfig ? 'Save changes' : 'Create config'}</button>
            </div>
          </Card>
        </div>
      ) : null}
    </div>
  );
}

function CollectionsView() {
  const token = useToken();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [visibilityFilter, setVisibilityFilter] = useState('');
  const [page, setPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const query = useQuery({ queryKey: ['collections'], queryFn: () => fetchCollections(token) });
  const allItems = useMemo(() => (Array.isArray(query.data) ? query.data : query.data?.items ?? []), [query.data]);
  const filteredItems = useMemo(
    () =>
      allItems.filter((collection) => {
        const matchesSearch = [collection.name, collection.slug, collection.description].join(' ').toLowerCase().includes(search.toLowerCase());
        const matchesVisibility = !visibilityFilter || collection.visibility === visibilityFilter;
        return matchesSearch && matchesVisibility;
      }),
    [allItems, search, visibilityFilter],
  );
  const pagedItems = useMemo(() => filteredItems.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE), [filteredItems, page]);
  const deletion = useMutation({
    mutationFn: (ids: string[]) => deleteCollections(token, ids),
    onSuccess: () => {
      setSelectedIds([]);
      queryClient.invalidateQueries({ queryKey: ['collections'] });
      queryClient.invalidateQueries({ queryKey: ['uploads'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
    },
  });

  function toggleSelection(collectionId: string) {
    setSelectedIds((current) => current.includes(collectionId) ? current.filter((value) => value !== collectionId) : [...current, collectionId]);
  }

  function toggleSelectVisible() {
    const visibleIds = pagedItems.map((item) => item.id);
    const allSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedIds.includes(id));
    setSelectedIds(allSelected ? selectedIds.filter((id) => !visibleIds.includes(id)) : Array.from(new Set([...selectedIds, ...visibleIds])));
  }

  async function handleDelete(ids: string[]) {
    if (!ids.length) return;
    if (!window.confirm(`Delete ${ids.length} collection(s)? This will also remove their files, chunks, jobs, and stored artifacts.`)) return;
    await deletion.mutateAsync(ids);
  }

  return (
    <div className="space-y-6">
      <SectionHeading eyebrow="Knowledge spaces" title="Collections" description="Inspect and manage the collections currently available to admins and internal operators." />
      <Card>
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_220px_auto] lg:items-center">
          <SearchInput value={search} onChange={(value) => { setSearch(value); setPage(1); }} placeholder="Search collections by name, slug, or description" />
          <select value={visibilityFilter} onChange={(event) => { setVisibilityFilter(event.target.value); setPage(1); }} className="rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none">
            <option value="">All visibility</option>
            <option value="private">Private</option>
            <option value="internal">Internal</option>
            <option value="shared">Shared</option>
          </select>
          <button onClick={toggleSelectVisible} className="rounded-full border border-white/10 px-4 py-2 text-sm text-slate-300 transition hover:bg-white/5">Select visible</button>
        </div>
        <SelectionToolbar selectedCount={selectedIds.length} resourceLabel="collections" onDelete={() => handleDelete(selectedIds)} onClear={() => setSelectedIds([])} />
        <div className="mt-5">
          <QueryBoundary isLoading={query.isLoading} error={query.error} onRetry={() => query.refetch()}>
            {pagedItems.length ? (
              <>
                <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
                  {pagedItems.map((collection) => (
                    <Card key={collection.id}>
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex items-start gap-3">
                          <input type="checkbox" checked={selectedIds.includes(collection.id)} onChange={() => toggleSelection(collection.id)} className="mt-1" />
                          <div>
                            <p className="text-xs uppercase tracking-[0.3em] text-slate-500">{collection.visibility}</p>
                            <h3 className="mt-3 text-xl font-semibold text-white">{collection.name}</h3>
                          </div>
                        </div>
                        <FolderKanban className="size-5 text-slate-400" />
                      </div>
                      <p className="mt-4 text-sm leading-7 text-slate-400">{collection.description || 'No description provided for this collection.'}</p>
                      <div className="mt-4 space-y-2 text-xs text-slate-500">
                        <p>ID: {collection.id}</p>
                        <p>Slug: {collection.slug || 'n/a'}</p>
                        <p>Files: {formatNumber(collection.file_count ?? 0)}</p>
                      </div>
                      <div className="mt-5 flex items-center justify-end">
                        <button onClick={() => handleDelete([collection.id])} className="inline-flex items-center gap-2 rounded-full border border-rose-300/20 bg-rose-500/10 px-3 py-2 text-xs text-rose-100 transition hover:bg-rose-500/15"><Trash2 className="size-4" />Delete</button>
                      </div>
                    </Card>
                  ))}
                </div>
                <PaginationControls page={page} pageSize={PAGE_SIZE} itemCount={pagedItems.length} hasNext={page * PAGE_SIZE < filteredItems.length} onPrevious={() => setPage((current) => Math.max(1, current - 1))} onNext={() => setPage((current) => current + 1)} />
              </>
            ) : (
              <EmptyState title="No collections available" description="Try another page or broaden the filter to inspect more knowledge spaces." />
            )}
          </QueryBoundary>
        </div>
      </Card>
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
    case 'models':
      return <ModelsView />;
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


