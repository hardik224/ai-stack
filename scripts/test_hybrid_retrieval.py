import json
import os
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, request


BASE_URL = os.getenv('BASE_URL', 'http://127.0.0.1:2000').rstrip('/')
TIMEOUT_SECONDS = int(os.getenv('TIMEOUT_SECONDS', '30'))
SSE_TIMEOUT_SECONDS = int(os.getenv('SSE_TIMEOUT_SECONDS', '240'))
JOB_TIMEOUT_SECONDS = int(os.getenv('JOB_TIMEOUT_SECONDS', '180'))
POLL_INTERVAL_SECONDS = float(os.getenv('POLL_INTERVAL_SECONDS', '2'))
VERBOSE_HTTP = os.getenv('VERBOSE_HTTP', '1').strip().lower() not in {'0', 'false', 'no'}
VERBOSE_SSE = os.getenv('VERBOSE_SSE', '1').strip().lower() not in {'0', 'false', 'no'}

ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@example.com')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'StrongPass123!')
INTERNAL_EMAIL = os.getenv('INTERNAL_EMAIL', 'internal@example.com')
INTERNAL_PASSWORD = os.getenv('INTERNAL_PASSWORD', 'StrongPass123!')

SEMANTIC_QUERY = os.getenv('SEMANTIC_QUERY', 'How should premium support onboarding escalation be handled?')
KEYWORD_QUERY = os.getenv('KEYWORD_QUERY', 'SOP-1042 premium onboarding escalation')
NUMERIC_QUERY = os.getenv('NUMERIC_QUERY', 'invoice 2025-000184 customer 48192')
CHAT_QUERY = os.getenv('CHAT_QUERY', 'What does SOP-1042 say about premium onboarding escalation?')


@dataclass
class Result:
    status: str
    name: str
    detail: str


class HybridRetrievalTestRunner:
    def __init__(self) -> None:
        self.results: list[Result] = []
        self.admin_token: str | None = None
        self.internal_token: str | None = None
        self.collection_id: str | None = None
        self.session_id: str | None = None
        self.uploads: list[dict[str, str]] = []

    def section(self, title: str) -> None:
        print(f"\n{'=' * 20} {title} {'=' * 20}", flush=True)

    def pass_(self, name: str, detail: str) -> None:
        self.results.append(Result('PASS', name, detail))
        print(f"[PASS] {name} -> {detail}", flush=True)

    def fail(self, name: str, detail: str) -> None:
        self.results.append(Result('FAIL', name, detail))
        print(f"[FAIL] {name} -> {detail}", flush=True)

    def skip(self, name: str, detail: str) -> None:
        self.results.append(Result('SKIP', name, detail))
        print(f"[SKIP] {name} -> {detail}", flush=True)

    def log_http_request(self, method: str, url: str, *, payload: Any | None = None, headers: dict[str, str] | None = None) -> None:
        if not VERBOSE_HTTP:
            return
        print(f"[HTTP] REQUEST  {method.upper()} {url}", flush=True)
        if headers:
            print(self.pretty_block('Request Headers', self.sanitize_headers(headers)), flush=True)
        if payload is not None:
            print(self.pretty_block('Request Body', payload), flush=True)

    def log_http_response(self, method: str, url: str, status_code: int, body: Any) -> None:
        if not VERBOSE_HTTP:
            return
        print(f"[HTTP] RESPONSE {method.upper()} {url} -> {status_code}", flush=True)
        print(self.pretty_block('Response Body', body), flush=True)

    @staticmethod
    def sanitize_headers(headers: dict[str, str]) -> dict[str, str]:
        sanitized = dict(headers)
        if 'Authorization' in sanitized:
            sanitized['Authorization'] = 'Bearer ***redacted***'
        if 'X-API-Key' in sanitized:
            sanitized['X-API-Key'] = '***redacted***'
        return sanitized

    @staticmethod
    def pretty_value(value: Any, max_len: int = 2200) -> str:
        if isinstance(value, (dict, list)):
            text = json.dumps(value, indent=2, default=str, ensure_ascii=True)
        else:
            text = str(value)
        return text if len(text) <= max_len else text[:max_len] + '\n...<truncated>...'

    def pretty_block(self, title: str, value: Any) -> str:
        return f"[HTTP] {title}:\n{self.pretty_value(value)}"

    def request_json(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        json_body: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
        expected_status: int | tuple[int, ...] | None = None,
        timeout_seconds: int = TIMEOUT_SECONDS,
        log_http: bool = True,
    ) -> tuple[int, Any, dict[str, str]]:
        url = f"{BASE_URL}{path}"
        headers = {'Accept': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        if extra_headers:
            headers.update(extra_headers)

        data = None
        if json_body is not None:
            data = json.dumps(json_body).encode('utf-8')
            headers['Content-Type'] = 'application/json'

        if log_http:
            self.log_http_request(method, url, payload=json_body, headers=headers)
        req = request.Request(url, data=data, headers=headers, method=method.upper())
        return self._perform(req, expected_status=expected_status, timeout_seconds=timeout_seconds, log_http=log_http)

    def request_multipart(
        self,
        path: str,
        *,
        token: str,
        fields: dict[str, str],
        files: dict[str, tuple[str, bytes, str]],
        expected_status: int | tuple[int, ...] | None = None,
    ) -> tuple[int, Any, dict[str, str]]:
        boundary = f'----AiStackBoundary{uuid.uuid4().hex}'
        body = bytearray()

        for key, value in fields.items():
            body.extend(f'--{boundary}\r\n'.encode('utf-8'))
            body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode('utf-8'))
            body.extend(str(value).encode('utf-8'))
            body.extend(b'\r\n')

        for field_name, (filename, file_bytes, content_type) in files.items():
            body.extend(f'--{boundary}\r\n'.encode('utf-8'))
            body.extend(f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode('utf-8'))
            body.extend(f'Content-Type: {content_type}\r\n\r\n'.encode('utf-8'))
            body.extend(file_bytes)
            body.extend(b'\r\n')

        body.extend(f'--{boundary}--\r\n'.encode('utf-8'))
        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {token}',
            'Content-Type': f'multipart/form-data; boundary={boundary}',
        }
        payload = {
            'fields': fields,
            'files': {
                name: {
                    'filename': details[0],
                    'content_type': details[2],
                    'size_bytes': len(details[1]),
                }
                for name, details in files.items()
            },
        }
        self.log_http_request('POST', f"{BASE_URL}{path}", payload=payload, headers=headers)
        req = request.Request(f"{BASE_URL}{path}", data=bytes(body), headers=headers, method='POST')
        return self._perform(req, expected_status=expected_status, timeout_seconds=TIMEOUT_SECONDS, log_http=True)

    def _perform(
        self,
        req: request.Request,
        *,
        expected_status: int | tuple[int, ...] | None,
        timeout_seconds: int,
        log_http: bool,
    ) -> tuple[int, Any, dict[str, str]]:
        expected = None
        if isinstance(expected_status, int):
            expected = (expected_status,)
        elif isinstance(expected_status, tuple):
            expected = expected_status

        try:
            with request.urlopen(req, timeout=timeout_seconds) as response:
                status_code = response.getcode()
                raw = response.read()
                headers = dict(response.info())
        except error.HTTPError as exc:
            status_code = exc.code
            raw = exc.read()
            headers = dict(exc.headers)
        except Exception as exc:
            raise RuntimeError(f'Request failed before HTTP response: {exc}') from exc

        parsed = self.parse_body(raw)
        if log_http:
            self.log_http_response(req.get_method(), req.full_url, status_code, parsed)
        if expected and status_code not in expected:
            raise RuntimeError(f'Expected {expected}, got {status_code}, body={self.pretty_value(parsed, max_len=900)}')
        return status_code, parsed, headers

    @staticmethod
    def parse_body(raw: bytes) -> Any:
        text = raw.decode('utf-8', errors='replace') if raw else ''
        if not text:
            return ''
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    def safe_json(self, method: str, path: str, label: str, **kwargs) -> Any:
        try:
            status_code, body, _ = self.request_json(method, path, **kwargs)
            self.pass_(label, f'status={status_code}')
            return body
        except RuntimeError as exc:
            self.fail(label, str(exc))
            return None

    def ensure_user(self, email: str, password: str, full_name: str, role: str, admin_token: str | None) -> None:
        payload = {'email': email, 'full_name': full_name, 'password': password, 'role': role}
        try:
            status_code, body, _ = self.request_json('POST', '/users', token=admin_token, json_body=payload, expected_status=(200, 409, 403))
        except RuntimeError as exc:
            self.fail(f'POST /users ({email})', str(exc))
            return

        if status_code == 200:
            self.pass_(f'POST /users ({email})', f"created id={body.get('id')}")
        elif status_code == 409:
            self.pass_(f'POST /users ({email})', 'user already exists')
        else:
            self.skip(f'POST /users ({email})', 'bootstrap route denied because users already exist')

    def login(self, email: str, password: str, label: str) -> str | None:
        try:
            _, body, _ = self.request_json('POST', '/auth/login', json_body={'email': email, 'password': password}, expected_status=200)
        except RuntimeError as exc:
            self.fail(f'POST /auth/login ({label})', str(exc))
            return None

        if not isinstance(body, dict) or not body.get('access_token'):
            self.fail(f'POST /auth/login ({label})', f'unexpected body={self.pretty_value(body)}')
            return None

        self.pass_(f'POST /auth/login ({label})', 'login succeeded')
        return body['access_token']

    def create_collection(self) -> None:
        body = self.safe_json(
            'POST',
            '/collections',
            'POST /collections',
            token=self.internal_token,
            json_body={'name': f'hybrid-retrieval-{uuid.uuid4().hex[:8]}', 'visibility': 'internal'},
            expected_status=200,
        )
        if isinstance(body, dict):
            self.collection_id = body.get('id')

    def create_test_files(self) -> tuple[Path, Path]:
        temp_dir = Path(tempfile.mkdtemp(prefix='ai-stack-hybrid-test-'))
        csv_path = temp_dir / 'customer_report.csv'
        pdf_path = temp_dir / 'SOP-1042-onboarding.pdf'

        csv_path.write_text(
            '\n'.join(
                [
                    'customer_id,invoice_id,plan,city,status,risk_note',
                    '48192,2025-000184,premium,Mumbai,delayed,"Escalation risk is high when onboarding ticket misses the 2 hour SLA."',
                    '48193,2025-000185,standard,Delhi,on_track,"No escalation needed."',
                    '48210,2025-000211,premium,Pune,review,"Customer requested callback before activation."',
                ]
            )
            + '\n',
            encoding='utf-8',
        )

        pdf_bytes = build_pdf_bytes(
            [
                'SOP-1042 Premium Support Onboarding Escalation Procedure',
                'Step 1 verify account ownership and confirm the premium plan.',
                'Step 2 create the onboarding ticket within 2 business hours.',
                'Step 3 escalate to the onboarding manager if the ticket breaches the SLA.',
                'Step 4 cite customer_id and invoice_id when escalating operational risk.',
            ]
        )
        pdf_path.write_bytes(pdf_bytes)
        self.pass_('Generated hybrid test files', str(temp_dir))
        return csv_path, pdf_path

    def upload_and_wait(self, file_path: Path, content_type: str) -> None:
        try:
            _, body, _ = self.request_multipart(
                '/upload',
                token=self.internal_token,
                fields={'collection_id': self.collection_id},
                files={'file': (file_path.name, file_path.read_bytes(), content_type)},
                expected_status=200,
            )
            self.pass_(f'POST /upload ({file_path.name})', 'uploaded')
        except RuntimeError as exc:
            self.fail(f'POST /upload ({file_path.name})', str(exc))
            return

        if not isinstance(body, dict):
            self.fail(f'Upload body ({file_path.name})', 'response was not JSON object')
            return

        file_id = body.get('file', {}).get('id')
        job_id = body.get('job', {}).get('id')
        if not file_id or not job_id:
            self.fail(f'Upload ids ({file_path.name})', self.pretty_value(body))
            return

        self.uploads.append({'file_id': file_id, 'job_id': job_id, 'filename': file_path.name})
        self.wait_for_job(job_id, file_path.name)

    def wait_for_job(self, job_id: str, label: str) -> None:
        deadline = time.time() + JOB_TIMEOUT_SECONDS
        while time.time() < deadline:
            try:
                _, body, _ = self.request_json('GET', f'/jobs/{job_id}', token=self.internal_token, expected_status=200, log_http=False)
            except RuntimeError as exc:
                self.fail(f'Poll /jobs/{job_id}', str(exc))
                return

            job = body.get('job', {}) if isinstance(body, dict) else {}
            progress = body.get('progress', {}) if isinstance(body, dict) else {}
            print(
                f"[POLL] {label}: status={job.get('status')} stage={progress.get('current_stage') or job.get('current_stage')} progress={progress.get('progress_percent')}",
                flush=True,
            )
            if job.get('status') == 'completed':
                self.pass_(f'Job completion {label}', 'completed')
                return
            if job.get('status') == 'failed':
                self.fail(f'Job completion {label}', self.pretty_value(body))
                return
            time.sleep(POLL_INTERVAL_SECONDS)

        self.fail(f'Job completion {label}', f'timed out after {JOB_TIMEOUT_SECONDS}s')

    def assert_keys_present(self, label: str, body: dict[str, Any], required_keys: set[str]) -> None:
        missing = sorted(key for key in required_keys if key not in body)
        if missing:
            self.fail(label, f'missing keys={missing}')
        else:
            self.pass_(label, 'all expected keys are present')

    def assert_retrieval_shape(self, body: dict[str, Any], label: str) -> None:
        self.assert_keys_present(
            f'{label} response shape',
            body,
            {
                'query',
                'normalized_query',
                'expanded_query',
                'top_k',
                'fetch_k',
                'filters',
                'items',
                'timings',
                'dedupe',
                'stats',
                'paths',
                'fusion',
                'rerank',
                'evidence_assessment',
            },
        )
        timings = body.get('timings', {})
        self.assert_keys_present(
            f'{label} timings shape',
            timings,
            {
                'query_embedding_ms',
                'vector_search_ms',
                'keyword_search_ms',
                'fusion_ms',
                'rerank_ms',
                'context_assembly_ms',
                'total_ms',
            },
        )
        items = body.get('items', [])
        if not items:
            self.fail(f'{label} items', 'no retrieval hits returned')
            return
        top = items[0]
        self.assert_keys_present(
            f'{label} top hit shape',
            top,
            {
                'chunk_id',
                'file_id',
                'filename',
                'collection_id',
                'chunk_index',
                'source_type',
                'text',
                'score',
                'vector_score',
                'keyword_score',
                'fused_score',
                'rerank_score',
                'citation_label',
                'rank',
                'retrieval_sources',
            },
        )

    def assert_result_contains(self, body: dict[str, Any], label: str, expected_substring: str) -> None:
        haystack = '\n'.join(
            [
                (item.get('filename') or '') + '\n' + (item.get('text') or '')
                for item in body.get('items', [])
                if isinstance(item, dict)
            ]
        ).lower()
        if expected_substring.lower() in haystack:
            self.pass_(label, f'found "{expected_substring}" in retrieval results')
        else:
            self.fail(label, f'"{expected_substring}" not found in retrieval results')

    def request_sse(self, *, token: str, json_body: dict[str, Any], label: str) -> list[dict[str, Any]] | None:
        url = f'{BASE_URL}/chat'
        headers = {
            'Accept': 'text/event-stream',
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        }
        data = json.dumps(json_body).encode('utf-8')
        self.log_http_request('POST', url, payload=json_body, headers=headers)
        req = request.Request(url, data=data, headers=headers, method='POST')

        try:
            with request.urlopen(req, timeout=SSE_TIMEOUT_SECONDS) as response:
                status_code = response.getcode()
                if status_code != 200:
                    raise RuntimeError(f'SSE endpoint returned status={status_code}')
                print(f'[HTTP] RESPONSE POST {url} -> {status_code}', flush=True)
                events = self._read_sse_events(response)
        except error.HTTPError as exc:
            body = exc.read().decode('utf-8', errors='replace')
            self.fail(label, f'HTTP {exc.code}: {body}')
            return None
        except Exception as exc:
            self.fail(label, f'SSE failed: {exc}')
            return None

        self.pass_(label, f'events={len(events)}')
        return events

    def _read_sse_events(self, response) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        current_event = 'message'
        data_lines: list[str] = []

        for raw_line in response:
            line = raw_line.decode('utf-8', errors='replace').rstrip('\r\n')
            if not line:
                if data_lines:
                    data_text = '\n'.join(data_lines)
                    try:
                        parsed = json.loads(data_text)
                    except json.JSONDecodeError:
                        parsed = data_text
                    entry = {'event': current_event, 'data': parsed}
                    events.append(entry)
                    if VERBOSE_SSE:
                        print(f"[SSE] {current_event} -> {self.pretty_value(parsed, max_len=700)}", flush=True)
                    event_type = parsed.get('type') if isinstance(parsed, dict) else None
                    if current_event == 'error' or event_type == 'error':
                        break
                    if current_event == 'generation.completed' or event_type == 'generation.completed':
                        break
                current_event = 'message'
                data_lines = []
                continue

            if line.startswith(':'):
                if VERBOSE_SSE:
                    print(f'[SSE] COMMENT {line[1:].strip()}', flush=True)
                continue
            if line.startswith('event:'):
                current_event = line.split(':', 1)[1].strip()
                continue
            if line.startswith('data:'):
                data_lines.append(line.split(':', 1)[1].lstrip())
                continue

        return events

    def assert_chat_events(self, events: list[dict[str, Any]], label: str) -> None:
        event_names = [event['event'] for event in events]
        required = ['session.created', 'retrieval.started', 'retrieval.completed', 'generation.started', 'citations.completed', 'message.saved', 'generation.completed']
        missing = [name for name in required if name not in event_names]
        if missing:
            self.fail(f'{label} event sequence', f'missing events={missing}')
        else:
            self.pass_(f'{label} event sequence', 'required SSE events present')

        content_count = event_names.count('content.delta')
        if content_count >= 1:
            self.pass_(f'{label} content streaming', f'content.delta count={content_count}')
        else:
            self.fail(f'{label} content streaming', 'no content.delta events received')

        retrieval_event = next((event for event in events if event['event'] == 'retrieval.completed'), None)
        if retrieval_event and isinstance(retrieval_event.get('data'), dict):
            data = retrieval_event['data'].get('data', {}) if isinstance(retrieval_event['data'].get('data'), dict) else {}
            self.assert_keys_present(
                f'{label} retrieval payload',
                data,
                {'count', 'candidate_count', 'dedupe_removed_count', 'filters', 'timings', 'citations', 'evidence_assessment'},
            )
        else:
            self.fail(f'{label} retrieval payload', 'retrieval.completed event missing or malformed')

    def extract_session_id(self, events: list[dict[str, Any]]) -> str | None:
        for event in events:
            data = event.get('data', {})
            if isinstance(data, dict):
                if data.get('session_id'):
                    return data['session_id']
                nested = data.get('data', {})
                if isinstance(nested, dict):
                    session = nested.get('session', {})
                    if isinstance(session, dict) and session.get('id'):
                        return session['id']
        return None

    def run(self) -> int:
        self.section('Health')
        self.safe_json('GET', '/health', 'GET /health', expected_status=200)
        self.safe_json('GET', '/db-health', 'GET /db-health', expected_status=200)

        self.section('Bootstrap And Auth')
        self.ensure_user(ADMIN_EMAIL, ADMIN_PASSWORD, 'Platform Admin', 'admin', None)
        self.admin_token = self.login(ADMIN_EMAIL, ADMIN_PASSWORD, 'admin')
        if not self.admin_token:
            print('\nAdmin login failed. Re-run with valid ADMIN_EMAIL and ADMIN_PASSWORD if your DB is not empty.', flush=True)
            return 1
        self.ensure_user(INTERNAL_EMAIL, INTERNAL_PASSWORD, 'Internal User', 'internal_user', self.admin_token)
        self.internal_token = self.login(INTERNAL_EMAIL, INTERNAL_PASSWORD, 'internal_user')
        if not self.internal_token:
            return 1

        self.section('Collection And Uploads')
        self.create_collection()
        if not self.collection_id:
            self.fail('Collection prerequisite', 'collection_id missing; stopping')
            return 1
        csv_path, pdf_path = self.create_test_files()
        self.upload_and_wait(csv_path, 'text/csv')
        self.upload_and_wait(pdf_path, 'application/pdf')

        self.section('Hybrid Search')
        semantic_body = self.safe_json(
            'POST',
            '/search',
            'POST /search semantic hybrid',
            token=self.internal_token,
            json_body={
                'query': SEMANTIC_QUERY,
                'collection_id': self.collection_id,
                'top_k': 5,
                'enable_vector': True,
                'enable_keyword': True,
                'enable_rerank': True,
                'debug': True,
            },
            expected_status=200,
        )
        if isinstance(semantic_body, dict):
            self.assert_retrieval_shape(semantic_body, 'POST /search semantic hybrid')
            paths = semantic_body.get('paths', {})
            if paths.get('vector_enabled') and paths.get('keyword_enabled'):
                self.pass_('Hybrid semantic paths', 'vector and keyword retrieval both enabled')
            else:
                self.fail('Hybrid semantic paths', self.pretty_value(paths))
            self.assert_result_contains(semantic_body, 'Hybrid semantic evidence', 'premium')

        keyword_body = self.safe_json(
            'POST',
            '/retrieve',
            'POST /retrieve keyword only',
            token=self.internal_token,
            json_body={
                'query': KEYWORD_QUERY,
                'collection_id': self.collection_id,
                'top_k': 5,
                'enable_vector': False,
                'enable_keyword': True,
                'enable_rerank': True,
                'debug': True,
            },
            expected_status=200,
        )
        if isinstance(keyword_body, dict):
            self.assert_retrieval_shape(keyword_body, 'POST /retrieve keyword only')
            paths = keyword_body.get('paths', {})
            if paths.get('vector_enabled') is False and paths.get('keyword_enabled') is True:
                self.pass_('Keyword-only paths', 'keyword retrieval ran without vector path')
            else:
                self.fail('Keyword-only paths', self.pretty_value(paths))
            self.assert_result_contains(keyword_body, 'Keyword-only evidence', 'sop-1042')

        numeric_body = self.safe_json(
            'POST',
            '/search',
            'POST /search numeric hybrid',
            token=self.internal_token,
            json_body={
                'query': NUMERIC_QUERY,
                'collection_id': self.collection_id,
                'top_k': 5,
                'enable_vector': True,
                'enable_keyword': True,
                'enable_rerank': True,
                'debug': True,
            },
            expected_status=200,
        )
        if isinstance(numeric_body, dict):
            self.assert_retrieval_shape(numeric_body, 'POST /search numeric hybrid')
            self.assert_result_contains(numeric_body, 'Numeric evidence', '48192')
            self.assert_result_contains(numeric_body, 'Invoice evidence', '2025-000184')

        self.section('Grounded Chat')
        chat_events = self.request_sse(
            token=self.internal_token,
            json_body={
                'mode': 'knowledge_qa',
                'message': CHAT_QUERY,
                'collection_id': self.collection_id,
            },
            label='POST /chat hybrid grounding',
        )
        if chat_events:
            self.assert_chat_events(chat_events, 'POST /chat hybrid grounding')
            self.session_id = self.extract_session_id(chat_events)
            if self.session_id:
                self.pass_('Hybrid chat session extraction', f'session_id={self.session_id}')
            else:
                self.fail('Hybrid chat session extraction', 'session_id not found in SSE events')

        self.section('Chat Session Detail')
        if self.session_id:
            detail_body = self.safe_json('GET', f'/chat/sessions/{self.session_id}', 'GET /chat/sessions/{id}', token=self.internal_token, expected_status=200)
            if isinstance(detail_body, dict):
                messages = detail_body.get('messages', [])
                if messages:
                    self.pass_('GET /chat/sessions/{id} messages', f'message_count={len(messages)}')
                else:
                    self.fail('GET /chat/sessions/{id} messages', 'no messages returned')
                assistant_messages = [message for message in messages if message.get('role') == 'assistant']
                sourced_messages = [message for message in assistant_messages if message.get('sources')]
                if sourced_messages:
                    self.pass_('Assistant citations persisted', f'assistant_messages_with_sources={len(sourced_messages)}')
                else:
                    self.fail('Assistant citations persisted', 'assistant messages had no persisted sources')

        self.section('Summary')
        pass_count = sum(1 for item in self.results if item.status == 'PASS')
        fail_count = sum(1 for item in self.results if item.status == 'FAIL')
        skip_count = sum(1 for item in self.results if item.status == 'SKIP')
        print(f'PASS={pass_count} FAIL={fail_count} SKIP={skip_count}', flush=True)
        if fail_count:
            print('\nFailed checks:', flush=True)
            for item in self.results:
                if item.status == 'FAIL':
                    print(f'- {item.name}: {item.detail}', flush=True)
        return 1 if fail_count else 0


def build_pdf_bytes(lines: list[str]) -> bytes:
    def escape_pdf_text(text: str) -> str:
        return text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')

    stream_lines = ['BT', '/F1 12 Tf', '50 720 Td']
    for index, line in enumerate(lines):
        if index == 0:
            stream_lines.append(f'({escape_pdf_text(line)}) Tj')
        else:
            stream_lines.append('T*')
            stream_lines.append(f'({escape_pdf_text(line)}) Tj')
    stream_lines.append('ET')
    stream_data = '\n'.join(stream_lines).encode('utf-8')

    objects = [
        b'1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n',
        b'2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n',
        b'3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n',
        f'4 0 obj<</Length {len(stream_data)}>>stream\n'.encode('utf-8') + stream_data + b'\nendstream\nendobj\n',
        b'5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n',
    ]

    content = bytearray(b'%PDF-1.4\n')
    offsets = [0]
    for obj in objects:
        offsets.append(len(content))
        content.extend(obj)

    xref_start = len(content)
    content.extend(f'xref\n0 {len(objects) + 1}\n'.encode('utf-8'))
    content.extend(b'0000000000 65535 f \n')
    for offset in offsets[1:]:
        content.extend(f'{offset:010d} 00000 n \n'.encode('utf-8'))
    content.extend(
        f'trailer<</Size {len(objects) + 1}/Root 1 0 R>>\nstartxref\n{xref_start}\n%%EOF'.encode('utf-8')
    )
    return bytes(content)


def main() -> int:
    runner = HybridRetrievalTestRunner()
    return runner.run()


if __name__ == '__main__':
    raise SystemExit(main())
