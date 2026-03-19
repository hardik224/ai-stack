'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bot, FileText, MessageSquare, Plus, SendHorizontal, Sparkles, UploadCloud } from 'lucide-react';
import Link from 'next/link';
import ReactMarkdown from 'react-markdown';

import { useAuth } from '@/components/auth-provider';
import { Card, EmptyState, ErrorState, MetricCard, SearchInput, SectionHeading, SkeletonCard, StatusBadge, TableShell, formatBytes, formatDateTime, formatNumber } from '@/components/ui';
import { fetchChatSessionDetail, fetchChatSessions, fetchFiles, fetchWorkspaceSummary, streamChat, uploadFile } from '@/features/admin/data';
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
  const [file, setFile] = useState<File | null>(null);

  const mutation = useMutation({
    mutationFn: () => {
      if (!file) throw new Error('A PDF or CSV file is required.');
      return uploadFile(token, { file });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspace-summary'] });
      queryClient.invalidateQueries({ queryKey: ['files'] });
      queryClient.invalidateQueries({ queryKey: ['uploads'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
      setOpen(false);
      setFile(null);
    },
  });

  return (
    <>
      <button onClick={() => setOpen(true)} className="inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-400/10 px-5 py-3 text-sm font-medium text-cyan-100 transition hover:bg-cyan-400/15"><UploadCloud className="size-4" />Upload file</button>
      {open ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/75 p-4 backdrop-blur-md">
          <Card className="w-full max-w-2xl p-6">
            <SectionHeading eyebrow="New upload" title="Add a source file" description="Upload a PDF or CSV and the system will place it into the right managed knowledge space automatically." />
            <div className="mt-6 grid gap-4">
              <div className="rounded-2xl border border-cyan-300/10 bg-cyan-400/5 px-4 py-4 text-sm leading-6 text-slate-300">
                You only need to upload the document. The platform automatically routes it into the proper managed collection and starts ingestion in the background.
              </div>
              <input type="file" accept=".pdf,.csv" onChange={(event) => setFile(event.target.files?.[0] ?? null)} className="rounded-2xl border border-dashed border-white/10 bg-slate-950/70 px-4 py-6 text-sm text-slate-300 outline-none" />
            </div>
            {mutation.error ? <p className="mt-4 text-sm text-rose-300">{mutation.error.message}</p> : null}
            <div className="mt-6 flex items-center justify-end gap-3">
              <button onClick={() => setOpen(false)} className="rounded-full border border-white/10 px-5 py-3 text-sm text-slate-300 transition hover:bg-white/5">Cancel</button>
              <button onClick={() => mutation.mutate()} disabled={mutation.isPending || !file} className="rounded-full bg-gradient-to-r from-cyan-400 to-indigo-400 px-5 py-3 text-sm font-semibold text-slate-950 transition disabled:cursor-not-allowed disabled:opacity-60">{mutation.isPending ? 'Uploading...' : 'Start upload'}</button>
            </div>
          </Card>
        </div>
      ) : null}
    </>
  );
}

function MarkdownAnswer({ content }: { content: string }) {
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
        {content}
      </ReactMarkdown>
    </div>
  );
}

function MessageBubble({ message }: { message: LocalChatMessage }) {
  const isUser = message.role === 'user';

  return (
    <div className={cn('flex w-full', isUser ? 'justify-end' : 'justify-start')}>
      <div className={cn('max-w-[92%] rounded-[28px] border px-5 py-4 shadow-[0_20px_60px_-35px_rgba(15,23,42,0.95)] backdrop-blur-xl md:max-w-[82%]', isUser ? 'border-cyan-300/20 bg-gradient-to-br from-cyan-400/14 to-sky-400/8 text-white' : 'border-white/10 bg-white/6 text-slate-100')}>
        <div className="mb-3 flex items-center justify-between gap-4">
          <div className="inline-flex items-center gap-2 text-xs uppercase tracking-[0.28em] text-slate-400">
            <span className={cn('inline-flex size-8 items-center justify-center rounded-2xl border', isUser ? 'border-cyan-300/20 bg-cyan-400/12 text-cyan-100' : 'border-white/10 bg-white/5 text-slate-200')}>
              {isUser ? <span className="text-sm font-semibold">You</span> : <Bot className="size-4" />}
            </span>
            {isUser ? 'You' : 'Assistant'}
          </div>
          <div className="flex items-center gap-2">
            {message.status ? <StatusBadge value={message.status} /> : null}
          </div>
        </div>
        {isUser ? <p className="whitespace-pre-wrap text-[15px] leading-8 text-white">{message.content}</p> : <MarkdownAnswer content={message.content || '...'} />}
        {!isUser && message.sources?.length ? (
          <div className="mt-5 border-t border-white/8 pt-4">
            <p className="text-xs uppercase tracking-[0.28em] text-slate-500">Sources</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {message.sources.map((source) => (
                <div key={`${message.id}-${source.citation_label}-${source.chunk_id}`} className="rounded-2xl border border-cyan-300/10 bg-cyan-400/6 px-3 py-2 text-xs text-cyan-50">
                  <span className="font-semibold text-cyan-100">[{source.citation_label}]</span> {source.file_name || 'Source'}
                  {source.page_number ? ` | p.${source.page_number}` : ''}
                  {source.row_number ? ` | row ${source.row_number}` : ''}
                </div>
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
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const scrollRef = useRef<HTMLDivElement | null>(null);
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

  useEffect(() => () => {
    if (streamIntervalRef.current) {
      clearInterval(streamIntervalRef.current);
      streamIntervalRef.current = null;
    }
    streamQueueRef.current = [];
  }, []);

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

  function flushStreamQueue(force = false) {
    if (force) {
      stopStreamAnimation();
      if (!streamQueueRef.current.length) return;
      const flushed = streamQueueRef.current.join('');
      streamQueueRef.current = [];
      setMessages((current) => current.map((message) => message.id === assistantMessageIdRef.current ? { ...message, content: `${message.content}${flushed}` } : message));
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
      setMessages((current) => current.map((message) => message.id === assistantMessageIdRef.current ? { ...message, content: `${message.content}${nextDelta}` } : message));
      if (!streamQueueRef.current.length) {
        stopStreamAnimation();
      }
    }, 18);
  }

  function startNewChat() {
    stopStreamAnimation();
    streamQueueRef.current = [];
    setIsNewChatDraft(true);
    setSelectedSessionId(null);
    setMessages([]);
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
      { id: assistantMessageId, session_id: selectedSessionId ?? 'pending', role: 'assistant', content: '', status: 'streaming', created_at: new Date().toISOString(), sources: [], metadata: { mode }, isTransient: true },
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
                streamQueueRef.current.push(delta);
                flushStreamQueue();
                break;
              }
              case 'citations.completed': {
                const citations = Array.isArray(event.data?.citations) ? (event.data?.citations as ChatSource[]) : [];
                setMessages((current) => current.map((message) => message.id === assistantMessageIdRef.current ? { ...message, sources: citations } : message));
                break;
              }
              case 'message.saved':
                assistantMessageIdRef.current = event.message_id || assistantMessageIdRef.current;
                setMessages((current) => current.map((message) => message.id === assistantMessageId || message.id === assistantMessageIdRef.current ? { ...message, id: event.message_id || message.id, status: 'completed', isTransient: false } : message));
                break;
              case 'generation.completed':
                flushStreamQueue(true);
                setStreamStatus('Answer ready');
                assistantMessageIdRef.current = event.message_id || assistantMessageIdRef.current;
                setMessages((current) => current.map((message) => message.id === assistantMessageId || message.id === event.message_id || message.id === assistantMessageIdRef.current ? { ...message, id: event.message_id || message.id, status: 'completed', isTransient: false } : message));
                break;
              case 'error': {
                const detail = typeof event.data?.detail === 'string' ? event.data.detail : 'The chat request failed.';
                setStreamError(detail);
                setStreamStatus('Generation failed');
                flushStreamQueue(true);
                setMessages((current) => current.map((message) => message.id === assistantMessageIdRef.current || message.id === assistantMessageId ? { ...message, status: 'failed', error_message: detail, isTransient: false } : message));
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
      setMessages((current) => current.map((item) => item.id === assistantMessageIdRef.current || item.id === assistantMessageId ? { ...item, status: 'failed', error_message: message, isTransient: false } : item));
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
    <div className="grid min-h-[78vh] gap-0 overflow-hidden rounded-[32px] border border-white/10 bg-[#111214]/90 shadow-[0_50px_160px_-70px_rgba(15,23,42,0.98)] xl:grid-cols-[320px_minmax(0,1fr)]">
      <aside className="border-r border-white/8 bg-[#17181a]/92">
        <div className="border-b border-white/8 px-4 py-4">
          <button onClick={startNewChat} className="flex w-full items-center justify-center gap-2 rounded-2xl border border-white/10 bg-white/6 px-4 py-3 text-sm font-medium text-white transition hover:bg-white/10"><Plus className="size-4" />New chat</button>
          <div className="mt-3">
            <SearchInput value={sessionSearch} onChange={setSessionSearch} placeholder="Search chats" />
          </div>
        </div>
        <div className="max-h-[calc(78vh-96px)] overflow-y-auto p-3">
          {sessionsQuery.isLoading ? (
            <div className="space-y-3">
              <SkeletonCard />
              <SkeletonCard />
            </div>
          ) : sessionsQuery.error ? (
            <ErrorState title="Could not load chats" description={sessionsQuery.error instanceof Error ? sessionsQuery.error.message : 'Unknown error'} onRetry={() => sessionsQuery.refetch()} />
          ) : filteredSessions.length ? (
            <div className="space-y-2">
              {filteredSessions.map((session) => {
                const active = session.id === selectedSessionId;
                return (
                  <button key={session.id} onClick={() => { setIsNewChatDraft(false); setSelectedSessionId(session.id); }} className={cn('w-full rounded-2xl px-4 py-3 text-left transition', active ? 'bg-white/10 text-white' : 'text-slate-400 hover:bg-white/6 hover:text-white')}>
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
      </aside>

      <section className="flex min-h-[78vh] flex-col bg-[#212121]">
        <div className="border-b border-white/8 px-6 py-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-slate-500">AI Stack Assistant</p>
              <h2 className="mt-2 text-xl font-semibold text-white">{currentSession?.title || 'New chat'}</h2>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {user?.role !== 'user' ? (
                <div className="inline-flex rounded-full border border-white/10 bg-white/5 p-1">
                  {(['knowledge_qa', 'analysis'] as ChatMode[]).map((option) => (
                    <button key={option} onClick={() => setMode(option)} className={cn('rounded-full px-4 py-2 text-sm transition', mode === option ? 'bg-white text-slate-950' : 'text-slate-400 hover:text-white')}>
                      {option === 'knowledge_qa' ? 'Knowledge Q&A' : 'Analysis'}
                    </button>
                  ))}
                </div>
              ) : null}
              <StatusBadge value={streaming ? 'processing' : 'active'} />
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-8">
          <div className="mx-auto flex w-full max-w-4xl flex-col gap-8">
            {detailQuery.isLoading && selectedSessionId && !messages.length ? (
              <div className="space-y-4">
                <SkeletonCard />
                <SkeletonCard />
              </div>
            ) : null}

            {!messages.length && !selectedSessionId ? (
              <div className="flex min-h-[46vh] items-center justify-center">
                <div className="max-w-2xl space-y-5 text-center">
                  <div className="mx-auto inline-flex rounded-3xl border border-white/10 bg-white/5 p-4 text-slate-200"><Bot className="size-7" /></div>
                  <h3 className="text-4xl font-semibold tracking-tight text-white">What can I help you find?</h3>
                  <p className="text-base leading-8 text-slate-400">Ask grounded questions in natural language. The assistant searches your uploaded knowledge base, streams the answer live, and shows citations for every supported claim.</p>
                </div>
              </div>
            ) : null}

            {messages.map((message) => <MessageBubble key={message.id} message={message} />)}
            <div ref={scrollRef} />
          </div>
        </div>

        <div className="border-t border-white/8 bg-[#212121] px-6 py-5">
          <div className="mx-auto w-full max-w-4xl">
            <div className="mb-3 flex flex-wrap items-center gap-2 text-sm text-slate-400">
              {streamStatus ? <span>{streamStatus}</span> : <span>Live SSE streaming | Structured markdown | Citation-aware answers</span>}
              {streamError ? <span className="text-rose-300">{streamError}</span> : null}
            </div>
            <div className="rounded-[28px] border border-white/10 bg-[#2a2a2a] p-3 shadow-[0_20px_50px_-35px_rgba(0,0,0,0.9)]">
              <textarea
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    void handleSend();
                  }
                }}
                placeholder={user?.role === 'user' ? 'Ask anything from your uploaded knowledge base...' : 'Ask a grounded question, summarize documents, or analyze uploaded reports...'}
                className="min-h-28 w-full resize-none bg-transparent px-3 py-3 text-[15px] leading-7 text-white outline-none placeholder:text-slate-500"
              />
              <div className="mt-3 flex items-center justify-between gap-3 px-2 pb-1">
                <div className="flex items-center gap-2 text-xs uppercase tracking-[0.28em] text-slate-500">
                  <Sparkles className="size-4" />
                  Fast stream experience
                </div>
                <button onClick={() => void handleSend()} disabled={streaming || !draft.trim()} className="inline-flex items-center gap-2 rounded-full bg-white px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60">
                  <SendHorizontal className="size-4" />
                  {streaming ? 'Streaming...' : 'Send'}
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
                      <div>
                        <p className="text-sm font-semibold text-white">{file.original_name}</p>
                        <p className="mt-2 text-sm text-slate-400">{file.collection_name || 'Managed upload collection'} | {formatBytes(file.size_bytes)}</p>
                      </div>
                      <StatusBadge value={file.latest_job_status || file.latest_job_stage || 'queued'} />
                    </div>
                    <p className="mt-3 text-xs text-slate-500">Uploaded {formatDateTime(file.created_at)}</p>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="No uploads yet" description="Upload your first PDF or CSV to start building the knowledge base behind the assistant." />
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
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </TableShell>
              <PaginationControls page={page} pageSize={PAGE_SIZE} itemCount={items.length} onPrevious={() => setPage((current) => Math.max(1, current - 1))} onNext={() => setPage((current) => current + 1)} />
            </>
          ) : (
            <EmptyState title="No uploaded files matched the current search" description="Try a broader search or upload a new PDF/CSV to start ingestion." />
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
