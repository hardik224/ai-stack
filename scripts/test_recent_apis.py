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
JOB_TIMEOUT_SECONDS = int(os.getenv('JOB_TIMEOUT_SECONDS', '180'))
POLL_INTERVAL_SECONDS = float(os.getenv('POLL_INTERVAL_SECONDS', '2'))
VERBOSE_HTTP = os.getenv('VERBOSE_HTTP', '1').strip().lower() not in {'0', 'false', 'no'}

ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@example.com')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'StrongPass123!')
INTERNAL_EMAIL = os.getenv('INTERNAL_EMAIL', 'internal@example.com')
INTERNAL_PASSWORD = os.getenv('INTERNAL_PASSWORD', 'StrongPass123!')
STANDARD_EMAIL = os.getenv('STANDARD_EMAIL', 'user@example.com')
STANDARD_PASSWORD = os.getenv('STANDARD_PASSWORD', 'StrongPass123!')

CSV_SEARCH_QUERY = os.getenv('CSV_SEARCH_QUERY', 'support mumbai premium onboarding')
PDF_SEARCH_QUERY = os.getenv('PDF_SEARCH_QUERY', 'qdrant embeddings retrieval pipeline')

MINIMAL_PDF_BYTES = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 300]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n4 0 obj<</Length 98>>stream\nBT /F1 12 Tf 40 220 Td (AI Stack retrieval pipeline uses embeddings and Qdrant search.) Tj ET\nendstream\nendobj\n5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\nxref\n0 6\n0000000000 65535 f \n0000000010 00000 n \n0000000061 00000 n \n0000000118 00000 n \n0000000245 00000 n \n0000000391 00000 n \ntrailer<</Size 6/Root 1 0 R>>\nstartxref\n461\n%%EOF"


@dataclass
class Result:
    status: str
    name: str
    detail: str


class RecentApiTestRunner:
    def __init__(self) -> None:
        self.results: list[Result] = []
        self.admin_token: str | None = None
        self.internal_token: str | None = None
        self.standard_token: str | None = None
        self.api_key: str | None = None
        self.admin_user_id: str | None = None
        self.internal_user_id: str | None = None
        self.standard_user_id: str | None = None
        self.collection_id: str | None = None
        self.uploads: list[dict[str, str]] = []

    def section(self, title: str) -> None:
        print(f"\n{'=' * 20} {title} {'=' * 20}", flush=True)

    def log_http_request(self, method: str, url: str, *, payload: Any | None = None, headers: dict[str, str] | None = None, enabled: bool = True) -> None:
        if not VERBOSE_HTTP or not enabled:
            return
        print(f"[HTTP] REQUEST  {method.upper()} {url}", flush=True)
        if headers:
            print(self.pretty_block('Request Headers', self.sanitize_headers(headers)), flush=True)
        if payload is not None:
            print(self.pretty_block('Request Body', payload), flush=True)

    def log_http_response(self, method: str, url: str, status_code: int, body: Any, *, enabled: bool = True) -> None:
        if not VERBOSE_HTTP or not enabled:
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
    def pretty_value(value: Any, max_len: int = 2000) -> str:
        if isinstance(value, (dict, list)):
            text = json.dumps(value, indent=2, default=str, ensure_ascii=True)
        else:
            text = str(value)
        return text if len(text) <= max_len else text[:max_len] + '\n...<truncated>...'

    def pretty_block(self, title: str, value: Any) -> str:
        return f"[HTTP] {title}:\n{self.pretty_value(value)}"

    def pass_(self, name: str, detail: str) -> None:
        self.results.append(Result('PASS', name, detail))
        print(f"[PASS] {name} -> {detail}", flush=True)

    def fail(self, name: str, detail: str) -> None:
        self.results.append(Result('FAIL', name, detail))
        print(f"[FAIL] {name} -> {detail}", flush=True)

    def skip(self, name: str, detail: str) -> None:
        self.results.append(Result('SKIP', name, detail))
        print(f"[SKIP] {name} -> {detail}", flush=True)

    def request_json(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        api_key: str | None = None,
        json_body: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
        expected_status: int | tuple[int, ...] | None = None,
        log_http: bool = True,
    ) -> tuple[int, Any, dict[str, str]]:
        url = f"{BASE_URL}{path}"
        headers = {'Accept': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        if api_key:
            headers['X-API-Key'] = api_key
        if extra_headers:
            headers.update(extra_headers)

        data = None
        if json_body is not None:
            data = json.dumps(json_body).encode('utf-8')
            headers['Content-Type'] = 'application/json'

        self.log_http_request(method, url, payload=json_body, headers=headers, enabled=log_http)
        req = request.Request(url, data=data, headers=headers, method=method.upper())
        return self._perform(req, expected_status, log_http=log_http)

    def request_multipart(
        self,
        path: str,
        *,
        token: str,
        fields: dict[str, str],
        files: dict[str, tuple[str, bytes, str]],
        expected_status: int | tuple[int, ...] | None = None,
        log_http: bool = True,
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
        self.log_http_request('POST', f"{BASE_URL}{path}", payload=payload, headers=headers, enabled=log_http)
        req = request.Request(f"{BASE_URL}{path}", data=bytes(body), headers=headers, method='POST')
        return self._perform(req, expected_status, log_http=log_http)

    def _perform(self, req: request.Request, expected_status: int | tuple[int, ...] | None, *, log_http: bool) -> tuple[int, Any, dict[str, str]]:
        expected: tuple[int, ...] | None = None
        if isinstance(expected_status, int):
            expected = (expected_status,)
        elif isinstance(expected_status, tuple):
            expected = expected_status

        try:
            with request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
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
        self.log_http_response(req.get_method(), req.full_url, status_code, parsed, enabled=log_http)
        if expected and status_code not in expected:
            raise RuntimeError(f'Expected {expected}, got {status_code}, body={self.pretty_value(parsed, max_len=800)}')
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

    def safe_json(
        self,
        method: str,
        path: str,
        label: str,
        *,
        token: str | None = None,
        api_key: str | None = None,
        json_body: dict[str, Any] | None = None,
        expected_status: int | tuple[int, ...] | None = None,
        log_http: bool = True,
    ) -> Any:
        try:
            status_code, body, _ = self.request_json(
                method,
                path,
                token=token,
                api_key=api_key,
                json_body=json_body,
                expected_status=expected_status,
                log_http=log_http,
            )
            self.pass_(label, f'status={status_code}')
            return body
        except RuntimeError as exc:
            self.fail(label, str(exc))
            return None

    def ensure_user(self, email: str, password: str, full_name: str, role: str, admin_token: str | None) -> str | None:
        payload = {'email': email, 'full_name': full_name, 'password': password, 'role': role}
        try:
            status_code, body, _ = self.request_json('POST', '/users', token=admin_token, json_body=payload, expected_status=(200, 409, 403))
        except RuntimeError as exc:
            self.fail(f'POST /users ({email})', str(exc))
            return None

        if status_code == 200:
            self.pass_(f'POST /users ({email})', f"created user id={body.get('id')}")
            return body.get('id')
        if status_code == 409:
            self.pass_(f'POST /users ({email})', 'user already exists')
            return None
        self.skip(f'POST /users ({email})', 'bootstrap route denied because users already exist and no valid admin token was supplied')
        return None

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

    def create_test_files(self) -> tuple[Path, Path]:
        temp_dir = Path(tempfile.mkdtemp(prefix='ai-stack-recent-api-test-'))
        csv_path = temp_dir / 'customers.csv'
        pdf_path = temp_dir / 'retrieval.pdf'
        csv_path.write_text(
            'team,city,tier,topic\nSupport,Mumbai,premium,onboarding\nSales,Delhi,standard,renewal\nEngineering,Pune,internal,vector search\n',
            encoding='utf-8',
        )
        pdf_path.write_bytes(MINIMAL_PDF_BYTES)
        self.pass_('Generated test files', str(temp_dir))
        return csv_path, pdf_path

    def upload_file(self, file_path: Path, content_type: str) -> dict[str, str] | None:
        try:
            status_code, body, _ = self.request_multipart(
                '/upload',
                token=self.internal_token,
                fields={'collection_id': self.collection_id},
                files={'file': (file_path.name, file_path.read_bytes(), content_type)},
                expected_status=200,
            )
        except RuntimeError as exc:
            self.fail(f'POST /upload ({file_path.name})', str(exc))
            return None

        self.pass_(f'POST /upload ({file_path.name})', f'status={status_code}')
        if not isinstance(body, dict):
            self.fail(f'Upload parse ({file_path.name})', 'response body was not JSON object')
            return None

        file_id = body.get('file', {}).get('id')
        job_id = body.get('job', {}).get('id')
        if not file_id or not job_id:
            self.fail(f'Upload ids ({file_path.name})', f'missing file_id/job_id in {self.pretty_value(body)}')
            return None

        record = {'file_id': file_id, 'job_id': job_id, 'filename': file_path.name}
        self.uploads.append(record)
        return record

    def wait_for_job(self, job_id: str, label: str) -> dict[str, Any] | None:
        deadline = time.time() + JOB_TIMEOUT_SECONDS
        while time.time() < deadline:
            try:
                _, body, _ = self.request_json('GET', f'/jobs/{job_id}', token=self.internal_token, expected_status=200, log_http=False)
            except RuntimeError as exc:
                self.fail(f'Poll /jobs/{job_id}', str(exc))
                return None

            if not isinstance(body, dict):
                self.fail(f'Poll /jobs/{job_id}', f'non-JSON body={self.pretty_value(body)}')
                return None

            job = body.get('job', {})
            progress = body.get('progress', {})
            status_value = job.get('status')
            stage_value = progress.get('current_stage') or job.get('current_stage')
            percent = progress.get('progress_percent', job.get('progress_percent'))
            print(f"[POLL] {label}: status={status_value} stage={stage_value} progress={percent}", flush=True)

            if status_value == 'completed':
                self.pass_(f'Job completion {label}', f'completed stage={stage_value}')
                return body
            if status_value == 'failed':
                self.fail(f'Job completion {label}', self.pretty_value(body, max_len=1200))
                return body
            time.sleep(POLL_INTERVAL_SECONDS)

        self.fail(f'Job completion {label}', f'timed out after {JOB_TIMEOUT_SECONDS}s')
        return None

    def assert_keys_present(self, label: str, body: dict[str, Any], required_keys: set[str]) -> None:
        missing = sorted(key for key in required_keys if key not in body)
        if missing:
            self.fail(label, f'missing keys={missing}')
        else:
            self.pass_(label, 'all expected keys are present')

    def assert_job_progress_shape(self, body: dict[str, Any], label: str) -> None:
        job = body.get('job', {})
        progress = body.get('progress', {})
        stages = body.get('stages', [])
        required_progress_keys = {
            'current_stage',
            'progress_percent',
            'progress_message',
            'total_chunks',
            'processed_chunks',
            'indexed_chunks',
            'started_at',
            'completed_at',
            'failed_at',
            'error_message',
        }
        self.assert_keys_present(f'{label} progress shape', progress, required_progress_keys)

        stage_names = {stage.get('stage_name') for stage in stages if isinstance(stage, dict)}
        expected_stages = {'queued', 'downloading', 'parsing', 'chunking', 'embedding', 'indexing', 'completed'}
        missing_stages = sorted(expected_stages - stage_names)
        if missing_stages:
            self.fail(f'{label} stage coverage', f'missing stages={missing_stages}')
        else:
            self.pass_(f'{label} stage coverage', 'all ingestion stages recorded')

        if job.get('indexed_chunks') == job.get('total_chunks') and job.get('status') == 'completed':
            self.pass_(f'{label} chunk counters', f"indexed={job.get('indexed_chunks')} total={job.get('total_chunks')}")
        else:
            self.fail(f'{label} chunk counters', f"unexpected counters status={job.get('status')} indexed={job.get('indexed_chunks')} total={job.get('total_chunks')}")

    def assert_file_detail_shape(self, body: dict[str, Any], label: str) -> None:
        summary = body.get('ingestion_summary', {})
        required_keys = {
            'status',
            'source_type',
            'page_count',
            'row_count',
            'total_chunks',
            'indexed_chunks',
            'last_ingested_job_id',
            'last_ingested_at',
            'error_message',
        }
        self.assert_keys_present(f'{label} ingestion summary', summary, required_keys)

    def assert_file_list_item_shape(self, body: dict[str, Any], label: str) -> None:
        items = body.get('items', []) if isinstance(body, dict) else []
        if not items:
            self.fail(label, 'no file items returned')
            return
        item = items[0]
        required_keys = {'id', 'original_name', 'source_type', 'ingestion_status', 'total_chunks', 'indexed_chunks', 'latest_job_id', 'latest_job_progress'}
        self.assert_keys_present(f'{label} first item shape', item, required_keys)

    def assert_admin_job_item_shape(self, body: dict[str, Any], label: str) -> None:
        items = body.get('items', []) if isinstance(body, dict) else []
        if not items:
            self.fail(label, 'no admin job items returned')
            return
        item = items[0]
        required_keys = {'id', 'file_id', 'status', 'current_stage', 'progress_percent', 'total_chunks', 'processed_chunks', 'indexed_chunks', 'progress_message'}
        self.assert_keys_present(f'{label} first item shape', item, required_keys)

    def assert_admin_process_item_shape(self, body: dict[str, Any], label: str) -> None:
        items = body.get('items', []) if isinstance(body, dict) else []
        if not items:
            self.fail(label, 'no admin process items returned')
            return
        item = items[0]
        required_keys = {'job_id', 'status', 'current_stage', 'progress_percent', 'worker_id', 'metadata'}
        self.assert_keys_present(f'{label} first item shape', item, required_keys)

    def assert_search_response_shape(self, body: dict[str, Any], label: str) -> None:
        items = body.get('items', []) if isinstance(body, dict) else []
        if not items:
            self.fail(label, f'no search hits returned: {self.pretty_value(body)}')
            return
        top = items[0]
        required_keys = {'chunk_id', 'file_id', 'filename', 'collection_id', 'chunk_index', 'source_type', 'score', 'text'}
        self.assert_keys_present(f'{label} top hit shape', top, required_keys)
        if 'page_number' in top or 'row_number' in top:
            self.pass_(f'{label} source positions', 'result includes page_number or row_number')
        else:
            self.fail(f'{label} source positions', self.pretty_value(top))

    def create_api_key(self) -> str | None:
        body = self.safe_json('POST', '/auth/api-keys', 'POST /auth/api-keys', token=self.admin_token, json_body={'name': f'recent-test-key-{uuid.uuid4().hex[:6]}'}, expected_status=200)
        if isinstance(body, dict) and body.get('api_key'):
            self.pass_('API key extraction', 'received raw api key for retrieval tests')
            return body['api_key']
        self.fail('API key extraction', f'unexpected api key response={self.pretty_value(body)}')
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

        me_body = self.safe_json('GET', '/auth/me', 'GET /auth/me', token=self.admin_token, expected_status=200)
        if isinstance(me_body, dict):
            self.admin_user_id = me_body.get('id')
            self.assert_keys_present('GET /auth/me shape', me_body, {'id', 'email', 'full_name', 'role', 'status', 'auth_type'})

        self.section('User Provisioning')
        self.ensure_user(INTERNAL_EMAIL, INTERNAL_PASSWORD, 'Internal User', 'internal_user', self.admin_token)
        self.ensure_user(STANDARD_EMAIL, STANDARD_PASSWORD, 'Standard User', 'user', self.admin_token)
        users_body = self.safe_json('GET', '/users', 'GET /users', token=self.admin_token, expected_status=200)
        if isinstance(users_body, dict):
            items = users_body.get('items', [])
            if items:
                self.assert_keys_present('GET /users first item shape', items[0], {'id', 'email', 'full_name', 'role', 'status'})
            for item in items:
                if item.get('email') == INTERNAL_EMAIL:
                    self.internal_user_id = item.get('id')
                if item.get('email') == STANDARD_EMAIL:
                    self.standard_user_id = item.get('id')

        self.section('Role Logins')
        self.internal_token = self.login(INTERNAL_EMAIL, INTERNAL_PASSWORD, 'internal_user')
        self.standard_token = self.login(STANDARD_EMAIL, STANDARD_PASSWORD, 'user')
        if not self.internal_token:
            return 1

        self.section('Collection Setup')
        collection_name = f'recent-ingestion-{uuid.uuid4().hex[:8]}'
        collection_body = self.safe_json('POST', '/collections', 'POST /collections', token=self.internal_token, json_body={'name': collection_name, 'visibility': 'internal'}, expected_status=200)
        if isinstance(collection_body, dict):
            self.collection_id = collection_body.get('id')
            self.assert_keys_present('POST /collections shape', collection_body, {'id', 'name', 'slug', 'visibility'})
        collections_body = self.safe_json('GET', '/collections', 'GET /collections', token=self.internal_token, expected_status=200)
        if isinstance(collections_body, dict):
            items = collections_body.get('items', []) if 'items' in collections_body else collections_body
            if isinstance(items, list) and items:
                self.assert_keys_present('GET /collections first item shape', items[0], {'id', 'name', 'slug', 'visibility'})

        self.section('API Key Setup')
        self.api_key = self.create_api_key()
        api_keys_body = self.safe_json('GET', '/auth/api-keys', 'GET /auth/api-keys', token=self.admin_token, expected_status=200)
        if isinstance(api_keys_body, dict):
            items = api_keys_body.get('items', [])
            if items:
                self.assert_keys_present('GET /auth/api-keys first item shape', items[0], {'id', 'name', 'key_prefix', 'scope'})

        self.section('Uploads And Processing')
        if not self.collection_id:
            self.fail('Collection prerequisite', 'collection_id missing, upload stage cannot continue')
            return 1

        csv_path, pdf_path = self.create_test_files()
        csv_upload = self.upload_file(csv_path, 'text/csv')
        pdf_upload = self.upload_file(pdf_path, 'application/pdf')

        for record in [csv_upload, pdf_upload]:
            if not record:
                continue
            job_body = self.wait_for_job(record['job_id'], record['filename'])
            if isinstance(job_body, dict):
                self.assert_job_progress_shape(job_body, f"GET /jobs/{record['job_id']}")
                admin_job_body = self.safe_json('GET', f"/admin/jobs/{record['job_id']}", f"GET /admin/jobs/{record['job_id']}", token=self.admin_token, expected_status=200)
                if isinstance(admin_job_body, dict) and isinstance(admin_job_body.get('job'), dict):
                    self.assert_keys_present(f"GET /admin/jobs/{record['job_id']} job shape", admin_job_body['job'], {'id', 'status', 'current_stage', 'progress_percent', 'total_chunks', 'processed_chunks', 'indexed_chunks', 'progress_message'})
                internal_job_body = self.safe_json('GET', f"/jobs/{record['job_id']}", f"GET /jobs/{record['job_id']}", token=self.internal_token, expected_status=200)
                if isinstance(internal_job_body, dict):
                    self.assert_job_progress_shape(internal_job_body, f"GET /jobs/{record['job_id']} repeat")
                file_body = self.safe_json('GET', f"/files/{record['file_id']}", f"GET /files/{record['file_id']}", token=self.internal_token, expected_status=200)
                if isinstance(file_body, dict):
                    self.assert_file_detail_shape(file_body, f"GET /files/{record['file_id']}")

        files_body = self.safe_json('GET', '/files', 'GET /files', token=self.internal_token, expected_status=200)
        if isinstance(files_body, dict):
            self.assert_file_list_item_shape(files_body, 'GET /files')

        self.section('Retrieval APIs')
        if self.collection_id:
            search_bearer_body = self.safe_json('POST', '/search', 'POST /search (bearer)', token=self.internal_token, json_body={'query': CSV_SEARCH_QUERY, 'collection_id': self.collection_id, 'limit': 5}, expected_status=200)
            if isinstance(search_bearer_body, dict):
                self.assert_search_response_shape(search_bearer_body, 'POST /search (bearer)')

            if self.api_key:
                search_api_key_body = self.safe_json('POST', '/search', 'POST /search (api key)', api_key=self.api_key, json_body={'query': CSV_SEARCH_QUERY, 'collection_id': self.collection_id, 'limit': 5}, expected_status=200)
                if isinstance(search_api_key_body, dict):
                    self.assert_search_response_shape(search_api_key_body, 'POST /search (api key)')

                retrieve_body = self.safe_json('POST', '/retrieve', 'POST /retrieve (api key)', api_key=self.api_key, json_body={'query': PDF_SEARCH_QUERY, 'collection_id': self.collection_id, 'limit': 5}, expected_status=200)
                if isinstance(retrieve_body, dict):
                    self.assert_search_response_shape(retrieve_body, 'POST /retrieve (api key)')
            else:
                self.skip('POST /search (api key)', 'api key was not created successfully')
                self.skip('POST /retrieve (api key)', 'api key was not created successfully')

            retrieve_bearer_body = self.safe_json('POST', '/retrieve', 'POST /retrieve (bearer)', token=self.internal_token, json_body={'query': PDF_SEARCH_QUERY, 'collection_id': self.collection_id, 'limit': 5}, expected_status=200)
            if isinstance(retrieve_bearer_body, dict):
                self.assert_search_response_shape(retrieve_bearer_body, 'POST /retrieve (bearer)')

        self.section('Admin Visibility')
        admin_users_body = self.safe_json('GET', '/admin/users', 'GET /admin/users', token=self.admin_token, expected_status=200)
        if isinstance(admin_users_body, dict):
            items = admin_users_body.get('items', [])
            if items:
                self.assert_keys_present('GET /admin/users first item shape', items[0], {'id', 'email', 'role', 'file_count', 'total_uploaded_bytes', 'job_count'})
        if self.admin_user_id:
            admin_user_body = self.safe_json('GET', f'/admin/users/{self.admin_user_id}', 'GET /admin/users/{id}', token=self.admin_token, expected_status=200)
            if isinstance(admin_user_body, dict):
                self.assert_keys_present('GET /admin/users/{id} shape', admin_user_body, {'id', 'email', 'role', 'file_count', 'total_uploaded_bytes', 'job_count'})

        self.safe_json('GET', '/admin/dashboard/summary', 'GET /admin/dashboard/summary', token=self.admin_token, expected_status=200)
        uploads_body = self.safe_json('GET', '/admin/uploads', 'GET /admin/uploads', token=self.admin_token, expected_status=200)
        if isinstance(uploads_body, dict):
            items = uploads_body.get('items', [])
            if items:
                self.assert_keys_present('GET /admin/uploads first item shape', items[0], {'id', 'original_name', 'collection_id', 'uploaded_by_user_id', 'latest_job_id', 'latest_job_stage', 'latest_job_progress'})
        self.safe_json('GET', '/admin/uploads/summary', 'GET /admin/uploads/summary', token=self.admin_token, expected_status=200)

        jobs_body = self.safe_json('GET', '/admin/jobs', 'GET /admin/jobs', token=self.admin_token, expected_status=200)
        if isinstance(jobs_body, dict):
            self.assert_admin_job_item_shape(jobs_body, 'GET /admin/jobs')
        self.safe_json('GET', '/admin/jobs/summary', 'GET /admin/jobs/summary', token=self.admin_token, expected_status=200)

        processes_body = self.safe_json('GET', '/admin/processes', 'GET /admin/processes', token=self.admin_token, expected_status=200)
        if isinstance(processes_body, dict):
            self.assert_admin_process_item_shape(processes_body, 'GET /admin/processes')
        self.safe_json('GET', '/admin/processes/summary', 'GET /admin/processes/summary', token=self.admin_token, expected_status=200)
        self.safe_json('GET', '/admin/activity/recent', 'GET /admin/activity/recent', token=self.admin_token, expected_status=200)

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



def main() -> int:
    runner = RecentApiTestRunner()
    return runner.run()


if __name__ == '__main__':
    raise SystemExit(main())
