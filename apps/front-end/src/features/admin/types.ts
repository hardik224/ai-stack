export type UserRole = 'admin' | 'internal_user' | 'user';

export interface AuthUser {
  id: string;
  email: string;
  full_name?: string | null;
  role: UserRole;
  status: string;
  auth_type?: string;
}

export interface LoginResponse {
  token_type: string;
  access_token: string;
  expires_at?: string;
  user: AuthUser;
}

export interface PaginatedResponse<T> {
  items: T[];
  limit: number;
  offset: number;
}

export interface DashboardSummary {
  total_users: number;
  admin_users: number;
  internal_users: number;
  standard_users: number;
  total_collections: number;
  total_files: number;
  total_uploaded_bytes: number;
  total_jobs: number;
  queued_jobs: number;
  processing_jobs: number;
  completed_jobs: number;
  failed_jobs: number;
  running_background_processes: number;
  total_chat_sessions: number;
  total_chat_messages: number;
  total_assistant_messages?: number;
  failed_assistant_messages?: number;
  total_chat_citations?: number;
  queue_depth?: number;
}

export interface AdminUserItem {
  id: string;
  email: string;
  full_name?: string | null;
  role: UserRole;
  status: string;
  created_at: string;
  updated_at?: string;
  last_login_at?: string | null;
  file_count: number;
  total_uploaded_bytes: number;
  job_count: number;
  completed_jobs?: number;
  failed_jobs?: number;
  chat_session_count: number;
  message_count: number;
  assistant_message_count: number;
  failed_assistant_message_count?: number;
}

export interface UploadItem {
  id: string;
  original_name: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
  minio_bucket?: string;
  minio_object_key?: string;
  collection_id?: string | null;
  collection_name?: string | null;
  uploaded_by_user_id: string;
  uploaded_by_email: string;
  uploaded_by_full_name?: string | null;
  latest_job_id?: string | null;
  latest_job_status?: string | null;
  latest_job_stage?: string | null;
  latest_job_progress?: number | null;
}

export interface UploadSummaryItem {
  user_id: string;
  email: string;
  full_name?: string | null;
  file_count: number;
  total_uploaded_bytes: number;
  last_upload_at?: string | null;
}

export interface JobItem {
  id: string;
  file_id: string;
  file_name: string;
  collection_id?: string | null;
  collection_name?: string | null;
  created_by: string;
  created_by_email: string;
  status: string;
  current_stage: string;
  progress_percent: number;
  total_chunks: number;
  processed_chunks: number;
  indexed_chunks: number;
  progress_message?: string | null;
  worker_id?: string | null;
  worker_heartbeat_at?: string | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  failed_at?: string | null;
  error_message?: string | null;
}

export interface JobStage {
  id: string;
  stage_name: string;
  stage_order: number;
  stage_status: string;
  progress_percent: number;
  details?: Record<string, unknown>;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface JobEvent {
  id: string;
  event_type: string;
  message: string;
  event_data?: Record<string, unknown>;
  created_at: string;
}

export interface BackgroundTask {
  id: string;
  job_id: string;
  task_type: string;
  status: string;
  current_stage: string;
  progress_percent: number;
  worker_id?: string | null;
  heartbeat_at?: string | null;
  metadata?: Record<string, unknown>;
  started_at?: string | null;
  completed_at?: string | null;
  failed_at?: string | null;
  error_message?: string | null;
}

export interface JobDetailResponse {
  job: JobItem;
  events: JobEvent[];
  stages: JobStage[];
  background_task?: BackgroundTask | null;
  progress?: {
    current_stage?: string;
    progress_percent?: number;
    progress_message?: string;
    total_chunks?: number;
    processed_chunks?: number;
    indexed_chunks?: number;
    started_at?: string | null;
    completed_at?: string | null;
    failed_at?: string | null;
    error_message?: string | null;
  };
}

export interface JobSummary {
  total_jobs: number;
  queued_jobs: number;
  processing_jobs: number;
  completed_jobs: number;
  failed_jobs: number;
  downloading_jobs?: number;
  parsing_jobs?: number;
  chunking_jobs?: number;
  embedding_jobs?: number;
  indexing_jobs?: number;
  queue_depth?: number;
}

export interface ProcessSummary {
  total_processes: number;
  queued_processes: number;
  running_processes: number;
  completed_processes: number;
  failed_processes: number;
  average_progress_percent: number;
  queue_depth?: number;
}

export interface ProcessItem extends BackgroundTask {
  file_id?: string | null;
  file_name?: string | null;
  created_by_email?: string | null;
  updated_at?: string | null;
}

export interface ActivityItem {
  id: string;
  actor_user_id?: string | null;
  activity_type: string;
  target_type?: string | null;
  target_id?: string | null;
  description: string;
  visibility: string;
  metadata?: Record<string, unknown>;
  created_at: string;
  actor_email?: string | null;
}

export interface ChatSessionItem {
  id: string;
  user_id: string;
  user_email?: string | null;
  user_full_name?: string | null;
  collection_id?: string | null;
  title: string;
  status: string;
  metadata?: Record<string, unknown>;
  last_message_at?: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
  assistant_message_count: number;
  failed_message_count?: number;
  failed_assistant_message_count?: number;
  citation_count?: number;
  latest_assistant_status?: string | null;
  last_message_role?: string | null;
  last_message_content?: string | null;
  last_message_status?: string | null;
}

export interface ChatSource {
  id?: string;
  message_id?: string;
  chunk_id: string;
  file_id: string;
  citation_label: string;
  rank?: number;
  score?: number;
  metadata?: Record<string, unknown>;
  page_number?: number | null;
  row_number?: number | null;
  file_name?: string | null;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  user_id?: string | null;
  role: 'user' | 'assistant';
  content: string;
  token_count?: number | null;
  metadata?: Record<string, unknown>;
  status: string;
  error_message?: string | null;
  created_at: string;
  updated_at?: string;
  user_email?: string | null;
  citation_count?: number;
  sources?: ChatSource[];
}

export interface ChatDetailResponse {
  session: ChatSessionItem;
  messages: ChatMessage[];
  sources?: ChatSource[];
}

export interface CollectionItem {
  id: string;
  name: string;
  slug?: string | null;
  description?: string | null;
  visibility: string;
  created_by?: string | null;
  created_at?: string;
}

export interface CreateUserPayload {
  email: string;
  full_name: string;
  password: string;
  role: UserRole;
}
