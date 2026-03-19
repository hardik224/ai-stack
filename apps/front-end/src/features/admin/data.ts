import type {
  ActivityItem,
  AuthUser,
  ChatDetailResponse,
  ChatSessionItem,
  CollectionItem,
  CreateUserPayload,
  DashboardSummary,
  DeleteResponse,
  JobDetailResponse,
  JobItem,
  JobSummary,
  LlmConfigItem,
  LlmConfigListResponse,
  LlmConfigPayload,
  LoginResponse,
  PaginatedResponse,
  ProcessItem,
  ProcessSummary,
  StreamChatEvent,
  StreamChatRequest,
  UploadItem,
  UploadSummaryItem,
  AdminUserItem,
  WorkspaceSummary,
} from '@/features/admin/types';

const API_PREFIX = process.env.NEXT_PUBLIC_API_PROXY_PREFIX || '/proxy';
const TOKEN_KEY = 'ai-stack.admin.token';

export class ApiError extends Error {
  status: number;
  payload: unknown;

  constructor(message: string, status: number, payload: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.payload = payload;
  }
}

function buildUrl(path: string, query?: Record<string, string | number | boolean | undefined | null>) {
  const url = new URL(path, 'http://localhost');
  Object.entries(query ?? {}).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return;
    url.searchParams.set(key, String(value));
  });
  return `${url.pathname}${url.search}`;
}

function resolveRequestPath(path: string) {
  return path.startsWith('http') || path.startsWith(API_PREFIX) ? path : `${API_PREFIX}${path}`;
}

function parseTextPayload(text: string) {
  let payload: unknown = text;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = text;
  }
  return payload;
}

async function requestJson<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set('Accept', 'application/json');
  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(resolveRequestPath(path), {
    ...init,
    headers,
    cache: 'no-store',
  });

  const text = await response.text();
  const payload = parseTextPayload(text);

  if (!response.ok) {
    const message = typeof payload === 'object' && payload && 'detail' in payload ? String((payload as { detail: string }).detail) : `Request failed with status ${response.status}`;
    throw new ApiError(message, response.status, payload);
  }

  return payload as T;
}

async function requestForm<T>(path: string, formData: FormData, token?: string): Promise<T> {
  const headers = new Headers();
  headers.set('Accept', 'application/json');
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(resolveRequestPath(path), {
    method: 'POST',
    headers,
    body: formData,
    cache: 'no-store',
  });

  const text = await response.text();
  const payload = parseTextPayload(text);

  if (!response.ok) {
    const message = typeof payload === 'object' && payload && 'detail' in payload ? String((payload as { detail: string }).detail) : `Request failed with status ${response.status}`;
    throw new ApiError(message, response.status, payload);
  }

  return payload as T;
}

export function getStoredToken() {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token: string) {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearStoredToken() {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(TOKEN_KEY);
}

export async function login(email: string, password: string) {
  return requestJson<LoginResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}

export async function fetchMe(token: string) {
  return requestJson<AuthUser>('/auth/me', { method: 'GET' }, token);
}

export async function fetchWorkspaceSummary(token: string) {
  return requestJson<WorkspaceSummary>('/auth/workspace-summary', { method: 'GET' }, token);
}

export async function fetchDashboardSummary(token: string) {
  return requestJson<DashboardSummary>('/admin/dashboard/summary', { method: 'GET' }, token);
}

export async function fetchAdminUsers(token: string, query?: { limit?: number; offset?: number }) {
  return requestJson<PaginatedResponse<AdminUserItem>>(buildUrl('/admin/users', query), { method: 'GET' }, token);
}

export async function fetchAdminUser(token: string, userId: string) {
  return requestJson<AdminUserItem>(`/admin/users/${userId}`, { method: 'GET' }, token);
}

export async function createUser(token: string, payload: CreateUserPayload) {
  return requestJson<AdminUserItem>('/users', { method: 'POST', body: JSON.stringify(payload) }, token);
}

export async function fetchUploads(token: string, query?: { limit?: number; offset?: number }) {
  return requestJson<PaginatedResponse<UploadItem>>(buildUrl('/admin/uploads', query), { method: 'GET' }, token);
}

export async function fetchUploadSummary(token: string) {
  return requestJson<{ items: UploadSummaryItem[] }>('/admin/uploads/summary', { method: 'GET' }, token);
}

export async function fetchJobs(token: string, query?: { limit?: number; offset?: number; status?: string }) {
  return requestJson<PaginatedResponse<JobItem> & { status?: string }>(buildUrl('/admin/jobs', query), { method: 'GET' }, token);
}

export async function fetchJobSummary(token: string) {
  return requestJson<JobSummary>('/admin/jobs/summary', { method: 'GET' }, token);
}

export async function fetchJobDetail(token: string, jobId: string) {
  return requestJson<JobDetailResponse>(`/admin/jobs/${jobId}`, { method: 'GET' }, token);
}

export async function fetchProcesses(token: string, query?: { limit?: number; offset?: number; status?: string }) {
  return requestJson<PaginatedResponse<ProcessItem> & { status?: string }>(buildUrl('/admin/processes', query), { method: 'GET' }, token);
}

export async function fetchProcessSummary(token: string) {
  return requestJson<ProcessSummary>('/admin/processes/summary', { method: 'GET' }, token);
}

export async function fetchActivity(token: string, query?: { limit?: number; offset?: number }) {
  return requestJson<{ items: ActivityItem[]; limit: number; offset: number }>(buildUrl('/admin/activity/recent', query), { method: 'GET' }, token);
}

export async function fetchChats(token: string, query?: { limit?: number; offset?: number }) {
  return requestJson<PaginatedResponse<ChatSessionItem>>(buildUrl('/admin/chats', query), { method: 'GET' }, token);
}

export async function fetchChatDetail(token: string, sessionId: string) {
  return requestJson<ChatDetailResponse>(`/admin/chats/${sessionId}`, { method: 'GET' }, token);
}

export async function fetchChatSessions(token: string, query?: { limit?: number; offset?: number }) {
  return requestJson<PaginatedResponse<ChatSessionItem>>(buildUrl('/chat/sessions', query), { method: 'GET' }, token);
}

export async function fetchChatSessionDetail(token: string, sessionId: string) {
  return requestJson<ChatDetailResponse>(`/chat/sessions/${sessionId}`, { method: 'GET' }, token);
}

export async function fetchCollections(token: string) {
  return requestJson<{ items?: CollectionItem[] } | CollectionItem[]>('/collections', { method: 'GET' }, token);
}

export async function fetchFiles(token: string, query?: { limit?: number; offset?: number }) {
  return requestJson<PaginatedResponse<UploadItem>>(buildUrl('/files', query), { method: 'GET' }, token);
}

export async function fetchLlmConfigs(token: string) {
  return requestJson<LlmConfigListResponse>('/admin/llm/configs', { method: 'GET' }, token);
}

export async function fetchActiveLlmConfig(token: string) {
  return requestJson<LlmConfigItem>('/admin/llm/active', { method: 'GET' }, token);
}

export async function createLlmConfig(token: string, payload: LlmConfigPayload) {
  return requestJson<LlmConfigItem>('/admin/llm/configs', { method: 'POST', body: JSON.stringify(payload) }, token);
}

export async function updateLlmConfig(token: string, configId: string, payload: LlmConfigPayload) {
  return requestJson<LlmConfigItem>(`/admin/llm/configs/${configId}`, { method: 'PUT', body: JSON.stringify(payload) }, token);
}

export async function activateLlmConfig(token: string, configId: string) {
  return requestJson<LlmConfigItem>(`/admin/llm/configs/${configId}/activate`, { method: 'POST' }, token);
}

export async function deleteLlmConfig(token: string, configId: string) {
  return requestJson<DeleteResponse>(`/admin/llm/configs/${configId}`, { method: 'DELETE' }, token);
}

export async function uploadFile(token: string, payload: { file: File }) {
  const formData = new FormData();
  formData.set('file', payload.file);
  return requestForm<{ file: UploadItem; job: { id: string; status: string }; message: string; collection?: { id: string; name: string; auto_assigned: boolean; created_now: boolean } }>('/upload', formData, token);
}

export async function deleteUsers(token: string, ids: string[]) {
  return requestJson<DeleteResponse>('/admin/users/bulk-delete', { method: 'POST', body: JSON.stringify({ ids }) }, token);
}

export async function deleteFiles(token: string, ids: string[]) {
  return requestJson<DeleteResponse>('/admin/files/bulk-delete', { method: 'POST', body: JSON.stringify({ ids }) }, token);
}

export async function deleteJobs(token: string, ids: string[]) {
  return requestJson<DeleteResponse>('/admin/jobs/bulk-delete', { method: 'POST', body: JSON.stringify({ ids }) }, token);
}

export async function deleteProcesses(token: string, ids: string[]) {
  return requestJson<DeleteResponse>('/admin/processes/bulk-delete', { method: 'POST', body: JSON.stringify({ ids }) }, token);
}

export async function deleteChats(token: string, ids: string[]) {
  return requestJson<DeleteResponse>('/admin/chats/bulk-delete', { method: 'POST', body: JSON.stringify({ ids }) }, token);
}

export async function deleteCollections(token: string, ids: string[]) {
  return requestJson<DeleteResponse>('/admin/collections/bulk-delete', { method: 'POST', body: JSON.stringify({ ids }) }, token);
}

function parseSseEventBlock(block: string): { comment?: string; event?: string; data?: string } | null {
  const lines = block.split(/\r?\n/);
  let eventName: string | undefined;
  const dataLines: string[] = [];

  for (const line of lines) {
    if (!line) continue;
    if (line.startsWith(':')) {
      return { comment: line.slice(1).trim() };
    }
    if (line.startsWith('event:')) {
      eventName = line.slice(6).trim();
      continue;
    }
    if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trim());
    }
  }

  if (!eventName && dataLines.length === 0) return null;
  return { event: eventName, data: dataLines.join('\n') };
}

export async function streamChat(
  token: string,
  payload: StreamChatRequest,
  handlers: {
    onEvent?: (event: StreamChatEvent) => void;
    onComment?: (comment: string) => void;
  } = {},
) {
  const headers = new Headers();
  headers.set('Accept', 'text/event-stream');
  headers.set('Content-Type', 'application/json');
  headers.set('Authorization', `Bearer ${token}`);

  const response = await fetch(resolveRequestPath('/chat'), {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
    cache: 'no-store',
  });

  if (!response.ok) {
    const text = await response.text();
    const payloadError = parseTextPayload(text);
    const message = typeof payloadError === 'object' && payloadError && 'detail' in payloadError ? String((payloadError as { detail: string }).detail) : `Request failed with status ${response.status}`;
    throw new ApiError(message, response.status, payloadError);
  }

  if (!response.body) {
    throw new ApiError('SSE response body is unavailable.', 500, null);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });

    const parts = buffer.split(/\r?\n\r?\n/);
    buffer = parts.pop() ?? '';

    for (const block of parts) {
      const parsed = parseSseEventBlock(block.trim());
      if (!parsed) continue;
      if (parsed.comment) {
        handlers.onComment?.(parsed.comment);
        continue;
      }
      const eventPayload = parsed.data ? parseTextPayload(parsed.data) : {};
      handlers.onEvent?.(eventPayload as StreamChatEvent);
    }

    if (done) break;
  }

  if (buffer.trim()) {
    const parsed = parseSseEventBlock(buffer.trim());
    if (parsed?.comment) handlers.onComment?.(parsed.comment);
    else if (parsed?.data) handlers.onEvent?.(parseTextPayload(parsed.data) as StreamChatEvent);
  }
}
