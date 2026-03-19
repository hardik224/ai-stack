'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowDownToLine, ArrowLeft, Bot, FileText, LogOut, MessageSquare, Plus, SendHorizontal, Sparkles, UploadCloud } from 'lucide-react';
import Link from 'next/link';
import ReactMarkdown from 'react-markdown';

import { useAuth } from '@/components/auth-provider';
import { Card, EmptyState, ErrorState, MetricCard, SearchInput, SectionHeading, SkeletonCard, StatusBadge, TableShell, formatBytes, formatDateTime, formatNumber } from '@/components/ui';
import { downloadFile, fetchChatSessionDetail, fetchChatSessions, fetchFiles, fetchWorkspaceSummary, streamChat, uploadFiles } from '@/features/admin/data';
import type { ChatMessage, ChatMode, ChatSource, StreamChatEvent, UploadItem } from '@/features/admin/types';
import { cn } from '@/lib/utils';

const PAGE_SIZE = 20;

interface LocalChatMessage extends ChatMessage {
  isTransient?: boolean;
}

function useToken() {
  const { token } = useAuth();
  if (!token) throw new Error('Authentication token is unavailable.');
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

function QueryBoundary({ isLoading, error, onRetry, children }: { isLoading: boolean; error: unknown; onRetry?: () => void; children: React.ReactNode }) {
  if (isLoading) return <LoadingGrid />;
  if (error) {
    return <ErrorState title="Something went wrong" description={error instanceof Error ? error.message : 'Unknown request failure.'} onRetry={onRetry} />;
  }
  return <>{children}</>;
}

function PaginationControls({ page, pageSize, itemCount, onPrevious, onNext }: { page: number; pageSize: number; itemCount: number; onPrevious: () => void; onNext: () => void }) {
  const hasNext = itemCount >= pageSize;

  return (
    <div className="mt-5 flex items-center justify-between gap-4 rounded-2xl border border-white/10 bg-white/4 px-4 py-3 text-sm text-slate-300">
      <p>Page {page} | Showing {itemCount} of up to {pageSize}</p>
      <div className="flex items-center gap-2">
        <button onClick={onPrevious} disabled={page === 1} className="rounded-full border border-white/10 px-4 py-2 transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50">Previous</button>
        <button onClick={onNext} disabled={!hasNext} className="rounded-full border border-white/10 px-4 py-2 transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50">Next</button>
      </div>
    </div>
  );
}

function SharedUploadDialog() {
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
      queryClient.invalidateQueries({ queryKey: ['workspace-summary'] });
      queryClient.invalidateQueries({ queryKey: ['files'] });
      queryClient.invalidateQueries({ queryKey: ['uploads'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
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
      return merged
    });
  };

  return (
    <>
      <button onClick={() => setOpen(true)} className="inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-400/10 px-5 py-3 text-sm font-medium text-cyan-100 transition hover:bg-cyan-400/15"><UploadCloud className="size-4" />Upload files</button>
      {open ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/75 p-4 backdrop-blur-md">
          <Card className="w-full max-w-2xl p-6">
            <SectionHeading eyebrow="New upload" title="Add source files" description="Upload one or more PDFs, CSVs, or Excel files and the system will place them into the right managed knowledge space automatically." />
            <div className="mt-6 grid gap-4">
              <div className="rounded-2xl border border-cyan-300/10 bg-cyan-400/5 px-4 py-4 text-sm leading-6 text-slate-300">
                Drag and drop files here or browse from your device. The platform routes them automatically and starts ingestion in the background.
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

function normalizeAnswerContent(content: string, hideReferences = false) {
  let normalized = content.replace(/(\[S\d+\])(\s*[.,]?\s*\[S\d+\])+/g, (match) => {
    const labels = match.match(/\[S\d+\]/g) ?? [];
    return labels.filter((label, index) => index === 0 || label !== labels[index - 1]).join(' ');
  });

  if (hideReferences) {
    normalized = normalized
      .replace(/\s*\[S\d+\]/g, '')
      .replace(/\n{2,}(##?\s*Sources|Sources)\s*[\s\S]*$/i, '')
      .trim();
  }

  return normalized;
}

function MarkdownAnswer({ content, hideReferences = false }: { content: string; hideReferences?: boolean }) {
  const normalizedContent = normalizeAnswerContent(content, hideReferences);

  return (
    <div className="space-y-4 text-[15px] leading-8 text-slate-100">
      <ReactMarkdown
        components={{
          h1: ({ children }) => <h1 className="text-2xl font-semibold tracking-tight text-white">{children}</h1>,
          h2: ({ children }) => <h2 className="pt-2 text-xl font-semibold text-white">{children}</h2>,
          h3: ({ children }) => <h3 className="pt-1 text-lg font-semibold text-slate-100">{children}</h3>,
          p: ({ children }) => <p className="text-slate-200">{children}</p>,
          ul: ({ children }) => <ul className="list-disc space-y-2 pl-6 text-slate-200">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal space-y-2 pl-6 text-slate-200">{children}</ol>,
          li: ({ children }) => <li className="marker:text-cyan-300">{children}</li>,
          strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
          code: ({ children }) => <code className="rounded-lg bg-white/6 px-1.5 py-0.5 text-cyan-100">{children}</code>,
          blockquote: ({ children }) => <blockquote className="border-l-2 border-cyan-300/40 pl-4 italic text-slate-300">{children}</blockquote>,
        }}
      >
        {normalizedContent}
      </ReactMarkdown>
    </div>
  );
}

function MessageBubble({ message, viewerRole, onDownloadSource }: { message: LocalChatMessage; viewerRole?: string | null; onDownloadSource?: (source: ChatSource) => void }) {
  const isUser = message.role === 'user';
  const canShowSources = viewerRole !== 'user';
  const citedLabels = new Set(Array.from((message.content || '').matchAll(/\[(S\d+)\]/g)).map((match) => match[1]));
  const visibleSources = !isUser && canShowSources && message.sources?.length
    ? Array.from(
        message.sources
          .filter((source) => citedLabels.has(source.citation_label))
          .reduce((map, source) => {
            const key = source.file_id || source.file_name || source.chunk_id;
            if (!map.has(key)) {
              map.set(key, source);
            }
            return map;
          }, new Map<string, ChatSource>())
          .values(),
      )
    : [];

  return (
    <div className={cn('mx-auto flex w-full max-w-[880px]', isUser ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          isUser
            ? 'max-w-[78%] rounded-[28px] bg-[#303030] px-5 py-4 text-white shadow-[0_24px_60px_-36px_rgba(0,0,0,0.85)]'
            : 'w-full px-1 py-1 text-slate-100',
        )}
      >
        {!isUser ? (
          <div className="mb-4 flex items-center gap-3 text-xs uppercase tracking-[0.26em] text-slate-500">
            <span className="inline-flex size-8 items-center justify-center rounded-2xl border border-white/10 bg-white/5 text-slate-200">
              <Bot className="size-4" />
            </span>
            Assistant
            {message.status ? <StatusBadge value={message.status} /> : null}
          </div>
        ) : null}

        {isUser ? (
          <p className="whitespace-pre-wrap text-[15px] leading-8 text-white">{message.content}</p>
        ) : (
          <MarkdownAnswer content={message.content || '...'} />
        )}

        {!isUser && visibleSources.length ? (
          <div className="mt-6 border-t border-white/8 pt-4">
            <p className="text-[11px] uppercase tracking-[0.28em] text-slate-500">Sources</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {visibleSources.map((source) => (
                <button key={`${message.id}-${source.file_id || source.file_name || source.chunk_id}`} onClick={() => onDownloadSource?.(source)} disabled={!source.file_id} className="rounded-full border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-200 transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-60">
                  <span className="font-semibold text-white">[{source.citation_label}]</span> {source.file_name || 'Source'}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {message.error_message ? <p className="mt-4 text-sm text-rose-300">{message.error_message}</p> : null}
      </div>
    </div>
  );
}

function AssistantView() {
  const token = useToken();
  const { user, logout } = useAuth();
  const queryClient = useQueryClient();
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  const streamQueueRef = useRef<string[]>([]);
  const streamIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const assistantMessageIdRef = useRef<string | null>(null);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<LocalChatMessage[]>([]);
  const [draft, setDraft] = useState('');
  const [mode, setMode] = useState<ChatMode>('knowledge_qa');
  const [streaming, setStreaming] = useState(false);
  const [streamStatus, setStreamStatus] = useState('');
  const [streamError, setStreamError] = useState<string | null>(null);
  const [sessionSearch, setSessionSearch] = useState('');
  const [isNewChatDraft, setIsNewChatDraft] = useState(false);

  async function handleDownloadFile(fileId: string, fileName?: string | null) {
    if (!fileId) return;
    try {
      await downloadFile(token, fileId, fileName || 'download');
    } catch (error) {
      setStreamError(error instanceof Error ? error.message : 'Failed to download file.');
    }
  }

  const sessionsQuery = useQuery({
    queryKey: ['chat-sessions'],
    queryFn: () => fetchChatSessions(token, { limit: 50, offset: 0 }),
  });
  const detailQuery = useQuery({
    queryKey: ['chat-session-detail', selectedSessionId],
    queryFn: () => fetchChatSessionDetail(token, selectedSessionId as string),
    enabled: Boolean(selectedSessionId),
  });

  useEffect(() => {
    if (!selectedSessionId && !isNewChatDraft && sessionsQuery.data?.items?.length) {
      setSelectedSessionId(sessionsQuery.data.items[0].id);
    }
  }, [isNewChatDraft, selectedSessionId, sessionsQuery.data?.items]);

  useEffect(() => {
    if (!streaming && detailQuery.data?.messages) {
      setMessages(detailQuery.data.messages as LocalChatMessage[]);
    }
  }, [detailQuery.data?.messages, streaming]);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, streamStatus]);

  useEffect(() => {
    const textarea = composerRef.current;
    if (!textarea) return;
    textarea.style.height = '0px';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 120)}px`;
  }, [draft]);

  useEffect(
    () => () => {
      if (streamIntervalRef.current) {
        clearInterval(streamIntervalRef.current);
        streamIntervalRef.current = null;
      }
      streamQueueRef.current = [];
    },
    [],
  );

  const currentSession = selectedSessionId ? (sessionsQuery.data?.items.find((item) => item.id === selectedSessionId) ?? detailQuery.data?.session ?? null) : null;
  const filteredSessions = useMemo(
    () => (sessionsQuery.data?.items ?? []).filter((session) => [session.title, session.last_message_content].join(' ').toLowerCase().includes(sessionSearch.toLowerCase())),
    [sessionSearch, sessionsQuery.data?.items],
  );

  function stopStreamAnimation() {
    if (streamIntervalRef.current) {
      clearInterval(streamIntervalRef.current);
      streamIntervalRef.current = null;
    }
  }

  function enqueueStreamDelta(delta: string) {
    const pieces: string[] = [];
    let buffer = '';
    for (const char of delta) {
      buffer += char;
      if (/\s/.test(char) || buffer.length >= 3) {
        pieces.push(buffer);
        buffer = '';
      }
    }
    if (buffer) pieces.push(buffer);
    streamQueueRef.current.push(...pieces);
  }

  function flushStreamQueue(force = false) {
    if (force) {
      stopStreamAnimation();
      if (!streamQueueRef.current.length) return;
      const flushed = streamQueueRef.current.join('');
      streamQueueRef.current = [];
      setMessages((current) => current.map((message) => (message.id === assistantMessageIdRef.current ? { ...message, content: `${message.content}${flushed}` } : message)));
      return;
    }

    if (streamIntervalRef.current || !streamQueueRef.current.length) {
      return;
    }

    streamIntervalRef.current = setInterval(() => {
      const nextDelta = streamQueueRef.current.shift();
      if (!nextDelta) {
        stopStreamAnimation();
        return;
      }
      setMessages((current) => current.map((message) => (message.id === assistantMessageIdRef.current ? { ...message, content: `${message.content}${nextDelta}` } : message)));
      if (!streamQueueRef.current.length) {
        stopStreamAnimation();
      }
    }, 18);
  }

  function startNewChat() {
    stopStreamAnimation();
    streamQueueRef.current = [];
    assistantMessageIdRef.current = null;
    setIsNewChatDraft(true);
    setSelectedSessionId(null);
    setMessages([]);
    setDraft('');
    setStreamError(null);
    setStreamStatus('');
  }

  async function handleSend() {
    const content = draft.trim();
    if (!content || streaming) return;

    const userMessageId = `local-user-${Date.now()}`;
    const assistantMessageId = `local-assistant-${Date.now()}`;
    assistantMessageIdRef.current = assistantMessageId;
    let nextSessionId = selectedSessionId;

    stopStreamAnimation();
    streamQueueRef.current = [];
    setDraft('');
    setStreamError(null);
    setStreaming(true);
    setMessages((current) => [
      ...current,
      { id: userMessageId, session_id: selectedSessionId ?? 'pending', role: 'user', content, status: 'completed', created_at: new Date().toISOString(), sources: [], metadata: { mode } },
      { id: assistantMessageId, session_id: selectedSessionId ?? 'pending', role: 'assistant', content: '', status: 'streaming', created_at: new Date().toISOString(), sources: [], citation_count: 0, metadata: { mode }, isTransient: true },
    ]);

    try {
      await streamChat(
        token,
        {
          message: content,
          mode: user?.role === 'user' ? 'knowledge_qa' : mode,
          session_id: selectedSessionId,
        },
        {
          onComment: (comment) => {
            setStreamStatus(comment.replace(/\./g, ' '));
          },
          onEvent: (event: StreamChatEvent) => {
            switch (event.type) {
              case 'session.created': {
                nextSessionId = event.session_id ?? ((event.data?.session as { id?: string } | undefined)?.id ?? null) ?? nextSessionId;
                if (nextSessionId) setSelectedSessionId(nextSessionId);
                setIsNewChatDraft(false);
                break;
              }
              case 'retrieval.started':
                setStreamStatus('Searching your knowledge base...');
                break;
              case 'retrieval.completed':
                setStreamStatus('Grounding evidence and preparing the answer...');
                break;
              case 'generation.started':
                setStreamStatus('Streaming answer...');
                break;
              case 'content.delta': {
                const delta = typeof event.data?.delta === 'string' ? event.data.delta : '';
                if (!delta) break;
                enqueueStreamDelta(delta);
                flushStreamQueue();
                break;
              }
              case 'citations.completed': {
                const citations = Array.isArray(event.data?.citations) ? (event.data?.citations as ChatSource[]) : [];
                setMessages((current) => current.map((message) => (message.id === assistantMessageIdRef.current ? { ...message, sources: citations, citation_count: citations.length } : message)));
                break;
              }
              case 'message.saved':
                assistantMessageIdRef.current = event.message_id || assistantMessageIdRef.current;
                setMessages((current) => current.map((message) => (message.id === assistantMessageId || message.id === assistantMessageIdRef.current ? { ...message, id: event.message_id || message.id, status: 'completed', isTransient: false, sources: message.sources ?? [], citation_count: message.citation_count ?? 0 } : message)));
                break;
              case 'generation.completed':
                flushStreamQueue(true);
                setStreamStatus('Answer ready');
                assistantMessageIdRef.current = event.message_id || assistantMessageIdRef.current;
                setMessages((current) => current.map((message) => (message.id === assistantMessageId || message.id === event.message_id || message.id === assistantMessageIdRef.current ? { ...message, id: event.message_id || message.id, status: 'completed', isTransient: false, sources: message.sources ?? [], citation_count: message.citation_count ?? 0 } : message)));
                break;
              case 'error': {
                const detail = typeof event.data?.detail === 'string' ? event.data.detail : 'The chat request failed.';
                setStreamError(detail);
                setStreamStatus('Generation failed');
                flushStreamQueue(true);
                setMessages((current) => current.map((message) => (message.id === assistantMessageIdRef.current || message.id === assistantMessageId ? { ...message, status: 'failed', error_message: detail, isTransient: false } : message)));
                break;
              }
              default:
                break;
            }
          },
        },
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : 'The chat request failed.';
      setStreamError(message);
      flushStreamQueue(true);
      setMessages((current) => current.map((item) => (item.id === assistantMessageIdRef.current || item.id === assistantMessageId ? { ...item, status: 'failed', error_message: message, isTransient: false } : item)));
    } finally {
      setStreaming(false);
      if (!streamQueueRef.current.length) {
        stopStreamAnimation();
      }
      queryClient.invalidateQueries({ queryKey: ['chat-sessions'] });
      queryClient.invalidateQueries({ queryKey: ['chat-session-detail'] });
      queryClient.invalidateQueries({ queryKey: ['workspace-summary'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
      setTimeout(() => {
        if (nextSessionId) {
          setSelectedSessionId(nextSessionId);
          queryClient.invalidateQueries({ queryKey: ['chat-session-detail', nextSessionId] });
        }
      }, 150);
    }
  }

  return (
    <div className="grid h-screen w-full grid-cols-[260px_minmax(0,1fr)] bg-[#212121] text-slate-100">
      <aside className="flex min-h-0 flex-col border-r border-white/10 bg-[#171717]">
        <div className="px-4 pb-4 pt-3">
          <div className="mb-4 flex items-center justify-between gap-3 px-2">
            <div className="flex items-center gap-3">
              <div className="inline-flex size-9 items-center justify-center rounded-full border border-white/10 bg-white/5 text-white">
                <Bot className="size-4" />
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.28em] text-slate-500">AI Stack</p>
                <h1 className="text-lg font-semibold text-white">Assistant</h1>
              </div>
            </div>
            {user?.role !== 'user' ? (
              <Link
                href="/dashboard"
                className="inline-flex size-9 items-center justify-center rounded-full border border-white/10 bg-white/5 text-slate-300 transition hover:bg-white/10 hover:text-white"
                aria-label="Back to dashboard"
                title="Back to dashboard"
              >
                <ArrowLeft className="size-4" />
              </Link>
            ) : null}
          </div>
          <button onClick={startNewChat} className="flex w-full items-center gap-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm font-medium text-white transition hover:bg-white/10">
            <Plus className="size-4" />
            New chat
          </button>
          <div className="mt-3">
            <SearchInput value={sessionSearch} onChange={setSessionSearch} placeholder="Search chats" />
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-4">
          {sessionsQuery.isLoading ? (
            <div className="space-y-3">
              <SkeletonCard />
              <SkeletonCard />
            </div>
          ) : sessionsQuery.error ? (
            <ErrorState title="Could not load chats" description={sessionsQuery.error instanceof Error ? sessionsQuery.error.message : 'Unknown error'} onRetry={() => sessionsQuery.refetch()} />
          ) : filteredSessions.length ? (
            <div className="space-y-1.5">
              {filteredSessions.map((session) => {
                const active = session.id === selectedSessionId && !isNewChatDraft;
                return (
                  <button
                    key={session.id}
                    onClick={() => {
                      setIsNewChatDraft(false);
                      setSelectedSessionId(session.id);
                    }}
                    className={cn(
                      'w-full rounded-2xl px-3 py-3 text-left transition',
                      active ? 'bg-white/10 text-white' : 'text-slate-400 hover:bg-white/6 hover:text-white',
                    )}
                  >
                    <p className="truncate text-sm font-medium">{session.title || 'Untitled chat'}</p>
                    <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{session.last_message_content || 'Ready for the next grounded answer.'}</p>
                  </button>
                );
              })}
            </div>
          ) : (
            <EmptyState title="No chats found" description="Start a new conversation or try another search term." />
          )}
        </div>

        <div className="shrink-0 border-t border-white/10 bg-[#171717] px-3 py-2">
          <div className="flex items-center gap-2 rounded-xl px-1 py-1">
            <div className="inline-flex size-8 shrink-0 items-center justify-center rounded-full border border-white/10 bg-white/[0.06] text-xs font-semibold text-white">
              {(user?.full_name || user?.email || 'U').trim().slice(0, 1).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-white">{user?.full_name || 'Workspace user'}</p>
              <p className="truncate text-[11px] text-slate-500">{user?.email}</p>
            </div>
            <button
              onClick={() => {
                logout();
                window.location.href = '/login';
              }}
              className="inline-flex size-8 shrink-0 items-center justify-center rounded-full border border-white/10 bg-white/[0.03] text-slate-300 transition hover:bg-white/10 hover:text-white"
              aria-label="Logout"
              title="Logout"
            >
              <LogOut className="size-3.5" />
            </button>
          </div>
        </div>
      </aside>

      <section className="flex min-h-0 flex-col bg-[#212121]">
        <div className="shrink-0 border-b border-white/10 px-6 py-3">
          <div className="mx-auto flex w-full max-w-[880px] items-center justify-between gap-4">
            <div>
              <p className="text-sm font-medium text-white">{currentSession?.title || 'New chat'}</p>
            </div>
            <div className="flex items-center gap-2">
              {user?.role !== 'user' ? (
                <div className="inline-flex rounded-full bg-white/5 p-1">
                  {(['knowledge_qa', 'analysis'] as ChatMode[]).map((option) => (
                    <button
                      key={option}
                      onClick={() => setMode(option)}
                      className={cn('rounded-full px-3 py-1.5 text-xs transition', mode === option ? 'bg-white text-slate-950' : 'text-slate-400 hover:text-white')}
                    >
                      {option === 'knowledge_qa' ? 'Knowledge' : 'Analysis'}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto flex w-full max-w-[880px] flex-col gap-8 px-6 py-8">
            {detailQuery.isLoading && selectedSessionId && !messages.length ? (
              <div className="space-y-4">
                <SkeletonCard />
                <SkeletonCard />
              </div>
            ) : null}

            {!messages.length && !selectedSessionId ? (
              <div className="flex min-h-[48vh] items-center justify-center">
                <div className="max-w-2xl space-y-5 text-center">
                  <div className="mx-auto inline-flex size-14 items-center justify-center rounded-full border border-white/10 bg-white/5 text-white">
                    <Bot className="size-6" />
                  </div>
                  <h3 className="text-4xl font-semibold tracking-tight text-white">What can I help with?</h3>
                  <p className="text-base leading-8 text-slate-400">Ask grounded questions in natural language. The assistant searches your uploaded knowledge base, streams the answer live, and cites every supported claim.</p>
                </div>
              </div>
            ) : null}

            {messages.map((message) => <MessageBubble key={message.id} message={message} />)}
            <div ref={scrollRef} />
          </div>
        </div>

        <div className="shrink-0 border-t border-white/10 bg-[#212121] px-5 py-3">
          <div className="mx-auto w-full max-w-[880px]">
            <div className="flex items-center gap-3 rounded-[28px] border border-white/10 bg-[#2f2f2f] px-3 py-2.5 shadow-[0_24px_70px_-38px_rgba(0,0,0,0.9)]">
              <div className="inline-flex size-9 shrink-0 items-center justify-center rounded-full bg-white/5 text-slate-400">
                <Sparkles className="size-4" />
              </div>
              <textarea
                ref={composerRef}
                rows={1}
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    void handleSend();
                  }
                }}
                placeholder={user?.role === 'user' ? 'Ask anything from your uploaded knowledge base...' : 'Ask a grounded question, summarize documents, or analyze uploaded reports...'}
                className="max-h-[120px] min-h-[26px] flex-1 resize-none overflow-y-auto bg-transparent py-1 text-[15px] leading-7 text-white outline-none placeholder:text-slate-500"
              />
              <div className="flex shrink-0 items-center gap-2 self-end pb-0.5">
                <span className={cn('hidden text-xs sm:inline', streamError ? 'text-rose-300' : 'text-slate-500')}>
                  {streamError ? streamError : streaming ? 'Streaming...' : streamStatus || 'Enter to send'}
                </span>
                <button
                  onClick={() => void handleSend()}
                  disabled={streaming || !draft.trim()}
                  className="inline-flex items-center gap-2 rounded-full bg-white px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <SendHorizontal className="size-4" />
                  Send
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function WorkspaceDashboardView() {
  const token = useToken();
  const handleDownloadFile = async (fileId: string, fileName?: string | null) => {
    await downloadFile(token, fileId, fileName || 'download');
  };
  const summaryQuery = useQuery({ queryKey: ['workspace-summary'], queryFn: () => fetchWorkspaceSummary(token) });
  const filesQuery = useQuery({ queryKey: ['files', 1], queryFn: () => fetchFiles(token, { limit: 5, offset: 0 }) });
  const chatsQuery = useQuery({ queryKey: ['chat-sessions', 'dashboard'], queryFn: () => fetchChatSessions(token, { limit: 5, offset: 0 }) });

  return (
    <div className="space-y-6">
      <SectionHeading eyebrow="Workspace" title="Your knowledge activity" description="Monitor your uploads, ingestion progress, and recent grounded conversations from one streamlined workspace." action={<div className="flex items-center gap-3"><SharedUploadDialog /><Link href="/assistant" className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-5 py-3 text-sm text-slate-200 transition hover:bg-white/10"><Bot className="size-4" />Open assistant</Link></div>} />
      <QueryBoundary isLoading={summaryQuery.isLoading || filesQuery.isLoading || chatsQuery.isLoading} error={summaryQuery.error || filesQuery.error || chatsQuery.error} onRetry={() => { summaryQuery.refetch(); filesQuery.refetch(); chatsQuery.refetch(); }}>
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard title="Knowledge files" value={formatNumber(summaryQuery.data?.file_count)} helper={`${formatBytes(summaryQuery.data?.total_uploaded_bytes)} uploaded`} icon={<FileText className="size-5" />} href="/uploads" />
          <MetricCard title="Jobs" value={formatNumber(summaryQuery.data?.job_count)} helper={`${summaryQuery.data?.processing_jobs ?? 0} processing | ${summaryQuery.data?.queued_jobs ?? 0} queued`} icon={<UploadCloud className="size-5" />} href="/uploads" />
          <MetricCard title="Chat sessions" value={formatNumber(summaryQuery.data?.chat_session_count)} helper={`${summaryQuery.data?.message_count ?? 0} total messages`} icon={<MessageSquare className="size-5" />} href="/assistant" />
          <MetricCard title="Assistant replies" value={formatNumber(summaryQuery.data?.assistant_message_count)} helper={`${summaryQuery.data?.failed_message_count ?? 0} failed`} icon={<Bot className="size-5" />} href="/assistant" />
        </div>

        <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
          <Card>
            <div className="mb-5 flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Recent uploads</p>
                <h3 className="mt-2 text-xl font-semibold text-white">Your latest files</h3>
              </div>
              <Link href="/uploads" className="text-sm text-cyan-200 transition hover:text-cyan-100">View all</Link>
            </div>
            {filesQuery.data?.items?.length ? (
              <div className="space-y-3">
                {filesQuery.data.items.map((file) => (
                  <div key={file.id} className="rounded-2xl border border-white/8 bg-white/4 p-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-white">{file.original_name}</p>
                        <p className="mt-2 text-sm text-slate-400">{file.collection_name || 'Managed upload collection'} | {formatBytes(file.size_bytes)}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <StatusBadge value={file.latest_job_status || file.latest_job_stage || 'queued'} />
                        <button onClick={() => void handleDownloadFile(file.id, file.original_name)} className="inline-flex size-9 items-center justify-center rounded-full border border-white/10 bg-white/5 text-slate-300 transition hover:bg-white/10 hover:text-white" title="Download file" aria-label="Download file">
                          <ArrowDownToLine className="size-4" />
                        </button>
                      </div>
                    </div>
                    <p className="mt-3 text-xs text-slate-500">Uploaded {formatDateTime(file.created_at)}</p>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="No uploads yet" description="Upload your first PDF, CSV, or Excel to start building the knowledge base behind the assistant." />
            )}
          </Card>

          <Card>
            <div className="mb-5 flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Recent conversations</p>
                <h3 className="mt-2 text-xl font-semibold text-white">Chat activity</h3>
              </div>
              <Link href="/assistant" className="text-sm text-cyan-200 transition hover:text-cyan-100">Open assistant</Link>
            </div>
            {chatsQuery.data?.items?.length ? (
              <div className="space-y-3">
                {chatsQuery.data.items.map((session) => (
                  <Link key={session.id} href="/assistant" className="block rounded-2xl border border-white/8 bg-white/4 p-4 transition hover:bg-white/7">
                    <p className="text-sm font-semibold text-white">{session.title || 'Untitled chat'}</p>
                    <p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-400">{session.last_message_content || 'Ready for the next grounded answer.'}</p>
                    <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
                      <StatusBadge value={session.last_message_status || session.status} />
                      <span>{formatDateTime(session.updated_at)}</span>
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <EmptyState title="No conversations yet" description="Open the assistant and ask the first grounded question." />
            )}
          </Card>
        </div>
      </QueryBoundary>
    </div>
  );
}

function WorkspaceUploadsView() {
  const token = useToken();
  const handleDownloadFile = async (fileId: string, fileName?: string | null) => {
    await downloadFile(token, fileId, fileName || 'download');
  };
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const offset = (page - 1) * PAGE_SIZE;
  const filesQuery = useQuery({ queryKey: ['files', page], queryFn: () => fetchFiles(token, { limit: PAGE_SIZE, offset }) });
  const items = useMemo(() => (filesQuery.data?.items ?? []).filter((item) => [item.original_name, item.collection_name, item.latest_job_status, item.latest_job_stage].join(' ').toLowerCase().includes(search.toLowerCase())), [filesQuery.data?.items, search]);

  return (
    <div className="space-y-6">
      <SectionHeading eyebrow="Uploads" title="Your files" description="See every file you uploaded, the managed knowledge space it landed in, and the current ingestion state." action={<SharedUploadDialog />} />
      <Card>
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
          <SearchInput value={search} onChange={(value) => { setSearch(value); setPage(1); }} placeholder="Search files by name, collection, or status" />
          <div className="text-sm text-slate-400">Auto-managed collections keep uploads organized for you.</div>
        </div>
        <div className="mt-5">
          {filesQuery.isLoading ? (
            <LoadingGrid />
          ) : filesQuery.error ? (
            <ErrorState title="Could not load your files" description={filesQuery.error instanceof Error ? filesQuery.error.message : 'Unknown error'} onRetry={() => filesQuery.refetch()} />
          ) : items.length ? (
            <>
              <TableShell>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-white/10 text-left text-sm text-slate-300">
                    <thead className="bg-white/5 text-xs uppercase tracking-[0.25em] text-slate-500">
                      <tr>
                        <th className="px-5 py-4 font-medium">File</th>
                        <th className="px-5 py-4 font-medium">Collection</th>
                        <th className="px-5 py-4 font-medium">Size</th>
                        <th className="px-5 py-4 font-medium">Ingestion</th>
                        <th className="px-5 py-4 font-medium">Uploaded</th>
                        <th className="px-5 py-4 font-medium">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {items.map((item: UploadItem) => (
                        <tr key={item.id}>
                          <td className="px-5 py-4">
                            <div>
                              <p className="font-medium text-white">{item.original_name}</p>
                              <p className="mt-1 text-xs text-slate-500">{item.content_type}</p>
                            </div>
                          </td>
                          <td className="px-5 py-4 text-slate-300">{item.collection_name || 'Managed upload collection'}</td>
                          <td className="px-5 py-4 text-slate-300">{formatBytes(item.size_bytes)}</td>
                          <td className="px-5 py-4"><StatusBadge value={item.latest_job_status || item.latest_job_stage || 'queued'} /></td>
                          <td className="px-5 py-4 text-slate-400">{formatDateTime(item.created_at)}</td>
                          <td className="px-5 py-4"><button onClick={() => void handleDownloadFile(item.id, item.original_name)} className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-200 transition hover:bg-white/10"><ArrowDownToLine className="size-4" />Download</button></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </TableShell>
              <PaginationControls page={page} pageSize={PAGE_SIZE} itemCount={items.length} onPrevious={() => setPage((current) => Math.max(1, current - 1))} onNext={() => setPage((current) => current + 1)} />
            </>
          ) : (
            <EmptyState title="No uploaded files matched the current search" description="Try a broader search or upload a new PDF, CSV, or Excel file to start ingestion." />
          )}
        </div>
      </Card>
    </div>
  );
}

export function WorkspaceSectionIndexView({ section }: { section: string }) {
  switch (section) {
    case 'assistant':
      return <AssistantView />;
    case 'dashboard':
      return <WorkspaceDashboardView />;
    case 'uploads':
      return <WorkspaceUploadsView />;
    default:
      return <EmptyState title="Section unavailable" description="This area is not available for your current workspace role." />;
  }
}

export function WorkspaceSectionDetailView() {
  return <EmptyState title="No detail screen here" description="This workspace route does not currently expose a dedicated detail view." />;
}




