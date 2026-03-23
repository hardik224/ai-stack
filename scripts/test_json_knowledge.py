import os
import subprocess
import sys
import tempfile
from pathlib import Path

from test_hybrid_retrieval import HybridRetrievalTestRunner


JSON_SEARCH_QUERY = os.getenv('JSON_SEARCH_QUERY', 'How should expiry returns be processed in ProCure?')
JSON_CHAT_QUERY = os.getenv('JSON_CHAT_QUERY', 'How should expiry returns be processed in ProCure?')
GENERIC_JSON_QUERY = os.getenv('GENERIC_JSON_QUERY', 'What does cash management include?')


class JsonKnowledgeTestRunner(HybridRetrievalTestRunner):
    def __init__(self) -> None:
        super().__init__()
        self.fixture_dir = Path(__file__).resolve().parent / 'fixtures'

    def run_python_check(self, label: str, code: str, *, pythonpath: str) -> None:
        env = os.environ.copy()
        env['PYTHONPATH'] = pythonpath
        completed = subprocess.run(
            [sys.executable, '-c', code],
            env=env,
            capture_output=True,
            text=True,
            timeout=90,
        )
        if completed.returncode == 0:
            detail = completed.stdout.strip() or 'ok'
            self.pass_(label, detail)
        else:
            detail = (completed.stderr or completed.stdout or 'python check failed').strip()
            self.fail(label, detail)

    def run_unit_checks(self) -> None:
        self.section('Local Parser Checks')
        worker_code = r'''
from pathlib import Path
from app.services.json_processor import parse_json_bytes

fixture_dir = Path(r'D:\\ews\\ai-stack') / 'scripts' / 'fixtures'
youtube = parse_json_bytes((fixture_dir / 'youtube_transcript_sample.json').read_bytes())
generic = parse_json_bytes((fixture_dir / 'generic_nested_sample.json').read_bytes())
assert youtube['source_type'] == 'json'
assert youtube['file_metadata']['knowledge_type'] == 'youtube_transcript'
assert any(unit.source_metadata.get('chunk_type') == 'youtube_segment' for unit in youtube['units'])
assert any(unit.source_metadata.get('chunk_type') == 'youtube_window' for unit in youtube['units'])
assert any(unit.source_metadata.get('chunk_type') == 'youtube_video' for unit in youtube['units'])
segment = next(unit for unit in youtube['units'] if unit.source_metadata.get('chunk_type') == 'youtube_segment')
assert 'youtube.com/watch' in segment.source_metadata.get('deep_link_url', '')
assert segment.source_metadata.get('thumbnail_url')
assert generic['file_metadata']['knowledge_type'] == 'generic_json'
assert generic['units']
print(f"youtube_units={len(youtube['units'])} generic_units={len(generic['units'])}")
'''
        self.run_python_check('Worker JSON parser', worker_code, pythonpath=str(Path(__file__).resolve().parents[1] / 'apps' / 'worker'))

        api_code = r'''
from app.services.media_card_service import choose_media_suggestions
from app.services.prompt_service import build_chat_prompt

items = [
    {
        'citation_label': 'S1',
        'source_type': 'json',
        'filename': 'youtube_transcript_sample.json',
        'text': 'Transcript excerpt: open the expiry returns section and submit the return request.',
        'source_metadata': {
            'knowledge_type': 'youtube_transcript',
            'chunk_type': 'youtube_segment',
            'video_id': 'Mu-NckS2CfU',
            'title': 'Expiry Returns for ProCure - Hindi',
            'url': 'https://www.youtube.com/watch?v=Mu-NckS2CfU',
            'start': 42.0,
            'end': 77.0,
            'segment_label': '00:42 - 01:17',
            'thumbnail_url': 'https://i.ytimg.com/vi/Mu-NckS2CfU/hqdefault.jpg',
            'snippet': 'Open the expiry returns section, select the distributor, add expired items, confirm quantity and batch details, and submit the return request.',
            'clean_text': 'Open the expiry returns section, select the distributor, add expired items, confirm quantity and batch details, and submit the return request.',
        },
        'rerank_score': 0.91,
        'vector_score': 0.88,
    },
    {
        'citation_label': 'S2',
        'source_type': 'json',
        'filename': 'youtube_transcript_sample.json',
        'text': 'Transcript excerpt: keep the acknowledgement and track the credit note status.',
        'source_metadata': {
            'knowledge_type': 'youtube_transcript',
            'chunk_type': 'youtube_window',
            'video_id': 'Mu-NckS2CfU',
            'title': 'Expiry Returns for ProCure - Hindi',
            'url': 'https://www.youtube.com/watch?v=Mu-NckS2CfU',
            'start': 42.0,
            'end': 104.0,
            'segment_label': '00:42 - 01:44',
            'thumbnail_url': 'https://i.ytimg.com/vi/Mu-NckS2CfU/hqdefault.jpg',
            'snippet': 'Keep the acknowledgement and track the credit note or replacement status.',
            'clean_text': 'Keep the acknowledgement and track the credit note or replacement status.',
        },
        'rerank_score': 0.84,
        'vector_score': 0.8,
    },
]

cards = choose_media_suggestions(items, question='How should expiry returns be processed in ProCure?')
assert cards
assert cards[0]['type'] in {'youtube_segment', 'youtube_video'}
prompt = build_chat_prompt(question='How should expiry returns be processed in ProCure?', context_items=items, history_messages=[], mode='knowledge_qa')
serialized = '\n'.join(message['content'] for message in prompt)
assert 'Relevant segment' in serialized or 'relevant segment' in serialized.lower()
assert 'Transcript excerpt' in serialized
assert '$.paragraphs' not in serialized
print(f"card_type={cards[0]['type']}")
'''
        self.run_python_check('API media-card and prompt formatting', api_code, pythonpath=str(Path(__file__).resolve().parents[1] / 'apps' / 'api'))

    def upload_fixture(self, fixture_name: str) -> None:
        fixture_path = self.fixture_dir / fixture_name
        self.upload_and_wait(fixture_path, 'application/json')

    def run_live_checks(self) -> None:
        self.section('Health')
        try:
            status_code, _, _ = self.request_json('GET', '/health', expected_status=200)
            self.pass_('GET /health', f'status={status_code}')
            status_code, _, _ = self.request_json('GET', '/db-health', expected_status=200)
            self.pass_('GET /db-health', f'status={status_code}')
        except RuntimeError as exc:
            detail = str(exc)
            self.skip('Live API checks', f'API unavailable at configured BASE_URL: {detail}')
            return

        self.section('Bootstrap And Auth')
        admin_email = os.getenv('ADMIN_EMAIL', 'admin@example.com')
        admin_password = os.getenv('ADMIN_PASSWORD', 'StrongPass123!')
        internal_email = os.getenv('INTERNAL_EMAIL', 'internal@example.com')
        internal_password = os.getenv('INTERNAL_PASSWORD', 'StrongPass123!')
        self.ensure_user(admin_email, admin_password, 'Platform Admin', 'admin', None)
        self.admin_token = self.login(admin_email, admin_password, 'admin')
        if not self.admin_token:
            return
        self.ensure_user(internal_email, internal_password, 'Internal User', 'internal_user', self.admin_token)
        self.internal_token = self.login(internal_email, internal_password, 'internal_user')
        if not self.internal_token:
            return

        self.section('Upload Validation')
        invalid_json = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        invalid_json.write(b'{"broken": true')
        invalid_json.close()
        try:
            with open(invalid_json.name, 'rb') as handle:
                try:
                    self.request_multipart(
                        '/upload',
                        token=self.internal_token,
                        fields={},
                        files={'file': ('invalid.json', handle.read(), 'application/json')},
                        expected_status=400,
                    )
                    self.pass_('POST /upload invalid json', 'invalid JSON rejected with 400')
                except RuntimeError as exc:
                    self.fail('POST /upload invalid json', str(exc))
        finally:
            Path(invalid_json.name).unlink(missing_ok=True)

        self.section('Collection And JSON Uploads')
        self.create_collection()
        if not self.collection_id:
            self.fail('Collection prerequisite', 'collection_id missing; stopping')
            return
        self.upload_fixture('generic_nested_sample.json')
        self.upload_fixture('youtube_transcript_sample.json')

        self.section('JSON Search')
        generic_body = self.safe_json(
            'POST',
            '/search',
            'POST /search generic json',
            token=self.internal_token,
            json_body={
                'query': GENERIC_JSON_QUERY,
                'collection_id': self.collection_id,
                'top_k': 5,
                'enable_vector': True,
                'enable_keyword': True,
                'enable_rerank': True,
                'debug': True,
            },
            expected_status=200,
        )
        if isinstance(generic_body, dict):
            self.assert_retrieval_shape(generic_body, 'POST /search generic json')
            self.assert_result_contains(generic_body, 'Generic JSON evidence', 'cash management')
            items = generic_body.get('items', [])
            if any((item.get('source_type') == 'json') for item in items):
                self.pass_('Generic JSON source type', 'json retrieval items returned')
            else:
                self.fail('Generic JSON source type', self.pretty_value(items[:2]))

        youtube_body = self.safe_json(
            'POST',
            '/search',
            'POST /search youtube transcript json',
            token=self.internal_token,
            json_body={
                'query': JSON_SEARCH_QUERY,
                'collection_id': self.collection_id,
                'top_k': 6,
                'enable_vector': True,
                'enable_keyword': True,
                'enable_rerank': True,
                'debug': True,
            },
            expected_status=200,
        )
        if isinstance(youtube_body, dict):
            self.assert_retrieval_shape(youtube_body, 'POST /search youtube transcript json')
            self.assert_result_contains(youtube_body, 'YouTube transcript evidence', 'expiry returns')
            media_cards = youtube_body.get('media_suggestions', [])
            if media_cards:
                self.pass_('YouTube media suggestions', f"count={len(media_cards)} type={media_cards[0].get('type')}")
            else:
                self.fail('YouTube media suggestions', self.pretty_value(youtube_body))

        self.section('Grounded Chat With Media Cards')
        chat_events = self.request_sse(
            token=self.internal_token,
            json_body={
                'mode': 'knowledge_qa',
                'message': JSON_CHAT_QUERY,
                'collection_id': self.collection_id,
            },
            label='POST /chat json transcript grounding',
        )
        if chat_events:
            retrieval_event = next((event for event in chat_events if event['event'] == 'retrieval.completed'), None)
            if retrieval_event and isinstance(retrieval_event.get('data'), dict):
                data = retrieval_event['data'].get('data', {}) if isinstance(retrieval_event['data'].get('data'), dict) else {}
                media_cards = data.get('media_suggestions', [])
                if media_cards:
                    self.pass_('Chat retrieval media suggestions', f"count={len(media_cards)} type={media_cards[0].get('type')}")
                else:
                    self.fail('Chat retrieval media suggestions', self.pretty_value(data))
            else:
                self.fail('Chat retrieval media suggestions', 'retrieval.completed event missing or malformed')

    def run(self) -> int:
        self.run_unit_checks()
        self.run_live_checks()
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


if __name__ == '__main__':
    raise SystemExit(JsonKnowledgeTestRunner().run())


