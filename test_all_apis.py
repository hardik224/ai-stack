import json
import os
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, request


BASE_URL = os.getenv('BASE_URL', 'http://127.0.0.1:2000').rstrip('/')
TIMEOUT_SECONDS = int(os.getenv('TIMEOUT_SECONDS', '30'))
JOB_TIMEOUT_SECONDS = int(os.getenv('JOB_TIMEOUT_SECONDS', '90'))
POLL_INTERVAL_SECONDS = float(os.getenv('POLL_INTERVAL_SECONDS', '2'))

ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@example.com')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'StrongPass123!')
INTERNAL_EMAIL = os.getenv('INTERNAL_EMAIL', 'internal@example.com')
INTERNAL_PASSWORD = os.getenv('INTERNAL_PASSWORD', 'StrongPass123!')
STANDARD_EMAIL = os.getenv('STANDARD_EMAIL', 'user@example.com')
STANDARD_PASSWORD = os.getenv('STANDARD_PASSWORD', 'StrongPass123!')

MINIMAL_PDF_BYTES = b"%PDF-1.1\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R >>\nendobj\n4 0 obj\n<< /Length 44 >>\nstream\nBT /F1 12 Tf 50 150 Td (AI Stack Test PDF) Tj ET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000202 00000 n \ntrailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n296\n%%EOF\n"


@dataclass
class Result:
    status: str
    name: str
    detail: str


class ApiTestRunner:
    def __init__(self) -> None:
        self.results: list[Result] = []
        self.admin_token: str | None = None
        self.internal_token: str | None = None
        self.standard_token: str | None = None
        self.admin_user_id: str | None = None
        self.internal_user_id: str | None = None
        self.collection_id: str | None = None
        self.file_id: str | None = None
        self.job_id: str | None = None
        self.upload_job_ids: list[str] = []

    def section(self, title: str) -> None:
        print(f"\n=== {title} ===", flush=True)

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
        json_body: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
        expected_status: int | tuple[int, ...] | None = None,
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

        req = request.Request(url, data=data, headers=headers, method=method.upper())
        return self._perform(req, expected_status)

    def request_multipart(
        self,
        path: str,
        *,
        token: str,
        fields: dict[str, str],
        files: dict[str, tuple[str, bytes, str]],
        expected_status: int | tuple[int, ...] | None = None,
    ) -> tuple[int, Any, dict[str, str]]:
        boundary = f"----AiStackBoundary{uuid.uuid4().hex}"
        body = bytearray()

        for key, value in fields.items():
            body.extend(f"--{boundary}\r\n".encode('utf-8'))
            body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode('utf-8'))
            body.extend(str(value).encode('utf-8'))
            body.extend(b"\r\n")

        for field_name, (filename, file_bytes, content_type) in files.items():
            body.extend(f"--{boundary}\r\n".encode('utf-8'))
            body.extend(
                f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode('utf-8')
            )
            body.extend(f"Content-Type: {content_type}\r\n\r\n".encode('utf-8'))
            body.extend(file_bytes)
            body.extend(b"\r\n")

        body.extend(f"--{boundary}--\r\n".encode('utf-8'))
        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {token}',
            'Content-Type': f'multipart/form-data; boundary={boundary}',
        }
        req = request.Request(f"{BASE_URL}{path}", data=bytes(body), headers=headers, method='POST')
        return self._perform(req, expected_status)

    def _perform(self, req: request.Request, expected_status: int | tuple[int, ...] | None) -> tuple[int, Any, dict[str, str]]:
        expected = None
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
            raise RuntimeError(f"Request failed before HTTP response: {exc}") from exc

        parsed = self._parse_body(raw, headers)
        if expected and status_code not in expected:
            raise RuntimeError(f"Expected {expected}, got {status_code}, body={self.preview(parsed)}")
        return status_code, parsed, headers

    @staticmethod
    def _parse_body(raw: bytes, headers: dict[str, str]) -> Any:
        text = raw.decode('utf-8', errors='replace') if raw else ''
        if not text:
            return text

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    @staticmethod
    def preview(value: Any, max_len: int = 240) -> str:
        if isinstance(value, (dict, list)):
            text = json.dumps(value, default=str)
        else:
            text = str(value)
        return text if len(text) <= max_len else text[:max_len] + '...'

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
        self.skip(f'POST /users ({email})', 'bootstrap route is closed because users already exist and no valid admin token was supplied')
        return None

    def login(self, email: str, password: str, name: str) -> str | None:
        try:
            _, body, _ = self.request_json(
                'POST',
                '/auth/login',
                json_body={'email': email, 'password': password},
                expected_status=200,
            )
            if not isinstance(body, dict):
                self.fail(f'POST /auth/login ({name})', f'non-JSON response: {self.preview(body)}')
                return None

            token = body.get('access_token')
            if not token:
                self.fail(f'POST /auth/login ({name})', f'missing access_token in response: {self.preview(body)}')
                return None

            self.pass_(f'POST /auth/login ({name})', 'login succeeded')
            return token
        except RuntimeError as exc:
            self.fail(f'POST /auth/login ({name})', str(exc))
            return None

    def run(self) -> int:
        self.section('Health')
        self.safe_json('GET', '/health', 'GET /health', expected_status=200)
        self.safe_json('GET', '/db-health', 'GET /db-health', expected_status=200)

        self.section('Bootstrap And Auth')
        self.ensure_user(ADMIN_EMAIL, ADMIN_PASSWORD, 'Platform Admin', 'admin', None)
        self.admin_token = self.login(ADMIN_EMAIL, ADMIN_PASSWORD, 'admin')
        if not self.admin_token:
            print('\nAdmin login failed. If your DB is not empty, run again with matching ADMIN_EMAIL and ADMIN_PASSWORD.', flush=True)
            return 1

        me_body = self.safe_json('GET', '/auth/me', 'GET /auth/me', token=self.admin_token, expected_status=200)
        if isinstance(me_body, dict):
            self.admin_user_id = me_body.get('id')

        self.section('User Provisioning')
        self.ensure_user(INTERNAL_EMAIL, INTERNAL_PASSWORD, 'Internal User', 'internal_user', self.admin_token)
        self.ensure_user(STANDARD_EMAIL, STANDARD_PASSWORD, 'Standard User', 'user', self.admin_token)
        users_body = self.safe_json('GET', '/users', 'GET /users', token=self.admin_token, expected_status=200)
        if isinstance(users_body, dict):
            for item in users_body.get('items', []):
                if item.get('email') == INTERNAL_EMAIL:
                    self.internal_user_id = item.get('id')
                if item.get('email') == ADMIN_EMAIL:
                    self.admin_user_id = item.get('id')

        self.section('API Keys')
        self.safe_json('POST', '/auth/api-keys', 'POST /auth/api-keys', token=self.admin_token, json_body={'name': 'chatbot-key'}, expected_status=200)
        self.safe_json('GET', '/auth/api-keys', 'GET /auth/api-keys', token=self.admin_token, expected_status=200)

        self.section('Role Logins')
        self.internal_token = self.login(INTERNAL_EMAIL, INTERNAL_PASSWORD, 'internal_user')
        self.standard_token = self.login(STANDARD_EMAIL, STANDARD_PASSWORD, 'user')

        if not self.internal_token:
            return 1

        self.section('Collections')
        collection_name = f"api-test-{uuid.uuid4().hex[:8]}"
        collection_body = self.safe_json(
            'POST',
            '/collections',
            'POST /collections',
            token=self.internal_token,
            json_body={'name': collection_name, 'visibility': 'internal'},
            expected_status=200,
        )
        if isinstance(collection_body, dict):
            self.collection_id = collection_body.get('id')
        self.safe_json('GET', '/collections', 'GET /collections (internal)', token=self.internal_token, expected_status=200)
        if self.standard_token:
            self.safe_json('GET', '/collections', 'GET /collections (user)', token=self.standard_token, expected_status=200)
            self.safe_json(
                'POST',
                '/collections',
                'POST /collections (user should fail)',
                token=self.standard_token,
                json_body={'name': 'forbidden-collection', 'visibility': 'internal'},
                expected_status=403,
            )

        self.section('Uploads And Jobs')
        if not self.collection_id:
            self.fail('Collection prerequisite', 'collection_id was not created, upload tests skipped')
        else:
            sample_csv, sample_pdf = self.create_test_files()
            self.upload_and_track(sample_csv, 'text/csv')
            self.upload_and_track(sample_pdf, 'application/pdf')
            self.safe_json('GET', '/files', 'GET /files', token=self.internal_token, expected_status=200)
            if self.file_id:
                self.safe_json('GET', f'/files/{self.file_id}', 'GET /files/{id}', token=self.internal_token, expected_status=200)
            if self.standard_token:
                self.safe_json('GET', '/files', 'GET /files (user should fail)', token=self.standard_token, expected_status=403)
            for job_id in self.upload_job_ids:
                self.wait_for_job(job_id)

        self.section('Admin APIs')
        self.safe_json('GET', '/admin/dashboard/summary', 'GET /admin/dashboard/summary', token=self.admin_token, expected_status=200)
        self.safe_json('GET', '/admin/users', 'GET /admin/users', token=self.admin_token, expected_status=200)
        if self.admin_user_id:
            self.safe_json('GET', f'/admin/users/{self.admin_user_id}', 'GET /admin/users/{id}', token=self.admin_token, expected_status=200)
        self.safe_json('GET', '/admin/uploads', 'GET /admin/uploads', token=self.admin_token, expected_status=200)
        self.safe_json('GET', '/admin/uploads/summary', 'GET /admin/uploads/summary', token=self.admin_token, expected_status=200)
        chats_body = self.safe_json('GET', '/admin/chats', 'GET /admin/chats', token=self.admin_token, expected_status=200)
        if isinstance(chats_body, dict) and chats_body.get('items'):
            session_id = chats_body['items'][0].get('id')
            if session_id:
                self.safe_json('GET', f'/admin/chats/{session_id}', 'GET /admin/chats/{session_id}', token=self.admin_token, expected_status=200)
        else:
            self.skip('GET /admin/chats/{session_id}', 'no chat session exists; this stack has no chat-create API yet')
        self.safe_json('GET', '/admin/jobs', 'GET /admin/jobs', token=self.admin_token, expected_status=200)
        self.safe_json('GET', '/admin/jobs/summary', 'GET /admin/jobs/summary', token=self.admin_token, expected_status=200)
        if self.job_id:
            self.safe_json('GET', f'/admin/jobs/{self.job_id}', 'GET /admin/jobs/{id}', token=self.admin_token, expected_status=200)
            self.safe_json('GET', f'/jobs/{self.job_id}', 'GET /jobs/{id}', token=self.internal_token, expected_status=200)
        self.safe_json('GET', '/admin/processes', 'GET /admin/processes', token=self.admin_token, expected_status=200)
        self.safe_json('GET', '/admin/processes/summary', 'GET /admin/processes/summary', token=self.admin_token, expected_status=200)
        self.safe_json('GET', '/admin/activity/recent', 'GET /admin/activity/recent', token=self.admin_token, expected_status=200)

        self.section('Summary')
        pass_count = sum(1 for item in self.results if item.status == 'PASS')
        fail_count = sum(1 for item in self.results if item.status == 'FAIL')
        skip_count = sum(1 for item in self.results if item.status == 'SKIP')
        print(f'PASS={pass_count} FAIL={fail_count} SKIP={skip_count}', flush=True)
        return 1 if fail_count else 0

    def safe_json(
        self,
        method: str,
        path: str,
        label: str,
        *,
        token: str | None = None,
        json_body: dict[str, Any] | None = None,
        expected_status: int | tuple[int, ...] | None = None,
    ) -> Any:
        try:
            status_code, body, _ = self.request_json(method, path, token=token, json_body=json_body, expected_status=expected_status)
            self.pass_(label, f'status={status_code}')
            return body
        except RuntimeError as exc:
            self.fail(label, str(exc))
            return None

    def create_test_files(self) -> tuple[Path, Path]:
        temp_dir = Path(tempfile.mkdtemp(prefix='ai-stack-api-test-'))
        csv_path = temp_dir / 'sample.csv'
        pdf_path = temp_dir / 'sample.pdf'
        csv_path.write_text('id,name\n1,alpha\n2,beta\n', encoding='utf-8')
        pdf_path.write_bytes(MINIMAL_PDF_BYTES)
        self.pass_('Generated test files', str(temp_dir))
        return csv_path, pdf_path

    def upload_and_track(self, file_path: Path, content_type: str) -> None:
        try:
            status_code, body, _ = self.request_multipart(
                '/upload',
                token=self.internal_token,
                fields={'collection_id': self.collection_id},
                files={'file': (file_path.name, file_path.read_bytes(), content_type)},
                expected_status=200,
            )
            self.pass_(f'POST /upload ({file_path.name})', f'status={status_code}')
            if isinstance(body, dict):
                file_id = body.get('file', {}).get('id')
                job_id = body.get('job', {}).get('id')
                if file_id:
                    self.file_id = file_id
                if job_id:
                    self.job_id = job_id
                    self.upload_job_ids.append(job_id)
        except RuntimeError as exc:
            self.fail(f'POST /upload ({file_path.name})', str(exc))

    def wait_for_job(self, job_id: str) -> None:
        deadline = time.time() + JOB_TIMEOUT_SECONDS
        while time.time() < deadline:
            try:
                _, body, _ = self.request_json('GET', f'/jobs/{job_id}', token=self.internal_token, expected_status=200)
            except RuntimeError as exc:
                self.fail(f'Poll /jobs/{job_id}', str(exc))
                return

            job = body.get('job', {}) if isinstance(body, dict) else {}
            status_value = job.get('status')
            stage_value = job.get('current_stage')
            if status_value == 'completed':
                self.pass_(f'Job completion {job_id}', f'completed at stage={stage_value}')
                return
            if status_value == 'failed':
                self.fail(f'Job completion {job_id}', f"failed: {self.preview(body)}")
                return
            print(f"[INFO] waiting for job {job_id}: status={status_value} stage={stage_value}", flush=True)
            time.sleep(POLL_INTERVAL_SECONDS)

        self.fail(f'Job completion {job_id}', f'timed out after {JOB_TIMEOUT_SECONDS}s')


def main() -> int:
    runner = ApiTestRunner()
    return runner.run()


if __name__ == '__main__':
    raise SystemExit(main())

