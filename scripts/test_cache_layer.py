import os
import tempfile
from pathlib import Path
from typing import Any

from test_hybrid_retrieval import HybridRetrievalTestRunner, build_pdf_bytes


CACHE_SEARCH_QUERY = os.getenv('CACHE_SEARCH_QUERY', 'premium onboarding escalation steps')
CACHE_EXACT_QUERY = os.getenv('CACHE_EXACT_QUERY', 'SOP-1042 premium onboarding escalation')
CACHE_NUMERIC_QUERY = os.getenv('CACHE_NUMERIC_QUERY', 'invoice 2025-000184 customer 48192')
CACHE_CHAT_QUERY = os.getenv('CACHE_CHAT_QUERY', 'What does SOP-1042 say about premium onboarding escalation?')
CACHE_MISS_QUERY = os.getenv('CACHE_MISS_QUERY', 'What is the cafeteria menu on the Mars colony base?')
EXPECT_PROMPT_CACHE = os.getenv('EXPECT_PROMPT_CACHE', '0').strip().lower() in {'1', 'true', 'yes'}
EXPECT_ANSWER_CACHE = os.getenv('EXPECT_ANSWER_CACHE', '0').strip().lower() in {'1', 'true', 'yes'}


class CacheLayerTestRunner(HybridRetrievalTestRunner):
    def __init__(self) -> None:
        super().__init__()
        self.search_version_before_invalidation: int | None = None

    def create_test_files(self) -> tuple[Path, Path, Path]:
        temp_dir = Path(tempfile.mkdtemp(prefix='ai-stack-cache-test-'))
        csv_path = temp_dir / 'customer_report.csv'
        pdf_path = temp_dir / 'SOP-1042-onboarding.pdf'
        invalidation_path = temp_dir / 'SOP-1042-appendix.pdf'

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
        pdf_path.write_bytes(
            build_pdf_bytes(
                [
                    'SOP-1042 Premium Support Onboarding Escalation Procedure',
                    'Step 1 verify account ownership and confirm the premium plan.',
                    'Step 2 create the onboarding ticket within 2 business hours.',
                    'Step 3 escalate to the onboarding manager if the ticket breaches the SLA.',
                    'Step 4 cite customer_id and invoice_id when escalating operational risk.',
                ]
            )
        )
        invalidation_path.write_bytes(
            build_pdf_bytes(
                [
                    'SOP-1042 Appendix B Additional Escalation Notes',
                    'Premium onboarding escalations must include ticket age and breach reason.',
                    'Operational review should cite invoice 2025-000184 when replaying test scenarios.',
                ]
            )
        )
        self.pass_('Generated cache test files', str(temp_dir))
        return csv_path, pdf_path, invalidation_path

    @staticmethod
    def event_payload(event: dict[str, Any]) -> dict[str, Any]:
        data = event.get('data', {})
        if isinstance(data, dict):
            nested = data.get('data')
            if isinstance(nested, dict):
                return nested
            return data
        return {}

    @staticmethod
    def find_event(events: list[dict[str, Any]], event_name: str) -> dict[str, Any] | None:
        for event in events:
            if event.get('event') == event_name:
                return event
        return None

    def assert_keys_present(self, label: str, body: dict[str, Any], keys: set[str]) -> None:
        missing = [key for key in keys if key not in body]
        if missing:
            self.fail(label, f'missing keys={missing}')
        else:
            self.pass_(label, 'required keys present')

    def assert_cache_shape(self, body: dict[str, Any], label: str) -> None:
        self.assert_keys_present(label, body, {'cache', 'cache_version_scope', 'timings'})
        cache_block = body.get('cache', {})
        retrieval_cache = cache_block.get('retrieval') if isinstance(cache_block, dict) else None
        embedding_cache = cache_block.get('embedding') if isinstance(cache_block, dict) else None
        if isinstance(retrieval_cache, dict):
            self.assert_keys_present(f'{label} retrieval cache', retrieval_cache, {'hit', 'lookup_ms'})
        else:
            self.fail(f'{label} retrieval cache', self.pretty_value(cache_block))
        if isinstance(embedding_cache, dict):
            self.assert_keys_present(f'{label} embedding cache', embedding_cache, {'hit', 'lookup_ms'})
        else:
            self.fail(f'{label} embedding cache', self.pretty_value(cache_block))

        scope = body.get('cache_version_scope', {})
        if isinstance(scope, dict) and {'scope', 'version'}.issubset(scope.keys()):
            self.pass_(f'{label} version scope', f"scope={scope.get('scope')} version={scope.get('version')}")
        else:
            self.fail(f'{label} version scope', self.pretty_value(scope))

    def assert_sse_sequence(self, events: list[dict[str, Any]], label: str) -> None:
        event_names = [event['event'] for event in events]
        required = ['retrieval.started', 'retrieval.completed', 'generation.started', 'citations.completed', 'message.saved', 'generation.completed']
        missing = [name for name in required if name not in event_names]
        if missing:
            self.fail(f'{label} event sequence', f'missing events={missing}')
        else:
            self.pass_(f'{label} event sequence', 'required SSE events present')

        delta_count = event_names.count('content.delta')
        if delta_count >= 1:
            self.pass_(f'{label} content streaming', f'content.delta count={delta_count}')
        else:
            self.fail(f'{label} content streaming', 'no content.delta events received')

    def assert_search_cache_flow(self) -> None:
        search_payload = {
            'query': CACHE_SEARCH_QUERY,
            'collection_id': self.collection_id,
            'top_k': 5,
            'enable_vector': True,
            'enable_keyword': True,
            'enable_rerank': True,
            'debug': True,
        }
        first_body = self.safe_json('POST', '/search', 'POST /search first cache probe', token=self.internal_token, json_body=search_payload, expected_status=200)
        if not isinstance(first_body, dict):
            return
        self.assert_cache_shape(first_body, 'POST /search first cache probe')
        first_retrieval_cache = first_body.get('cache', {}).get('retrieval', {})
        if first_retrieval_cache.get('hit') is False:
            self.pass_('First search retrieval cache', 'cold request was a cache miss')
        else:
            self.fail('First search retrieval cache', self.pretty_value(first_retrieval_cache))
        first_scope = first_body.get('cache_version_scope', {})
        if isinstance(first_scope, dict):
            version = first_scope.get('version')
            if isinstance(version, int):
                self.search_version_before_invalidation = version

        second_body = self.safe_json('POST', '/search', 'POST /search second cache probe', token=self.internal_token, json_body=search_payload, expected_status=200)
        if isinstance(second_body, dict):
            self.assert_cache_shape(second_body, 'POST /search second cache probe')
            second_retrieval_cache = second_body.get('cache', {}).get('retrieval', {})
            if second_retrieval_cache.get('hit') is True:
                self.pass_('Second search retrieval cache', 'repeat request hit retrieval cache')
            else:
                self.fail('Second search retrieval cache', self.pretty_value(second_retrieval_cache))

        embedding_probe_payload = dict(search_payload)
        embedding_probe_payload['top_k'] = 6
        third_body = self.safe_json('POST', '/search', 'POST /search embedding cache probe', token=self.internal_token, json_body=embedding_probe_payload, expected_status=200)
        if isinstance(third_body, dict):
            self.assert_cache_shape(third_body, 'POST /search embedding cache probe')
            retrieval_cache = third_body.get('cache', {}).get('retrieval', {})
            embedding_cache = third_body.get('cache', {}).get('embedding', {})
            if retrieval_cache.get('hit') is False:
                self.pass_('Embedding probe retrieval cache', 'changed signature bypassed retrieval cache as expected')
            else:
                self.fail('Embedding probe retrieval cache', self.pretty_value(retrieval_cache))
            if embedding_cache.get('hit') is True:
                self.pass_('Embedding cache reuse', 'same normalized query reused cached embedding')
            else:
                self.fail('Embedding cache reuse', self.pretty_value(embedding_cache))

        retrieve_body = self.safe_json('POST', '/retrieve', 'POST /retrieve cross-endpoint cache probe', token=self.internal_token, json_body=embedding_probe_payload, expected_status=200)
        if isinstance(retrieve_body, dict):
            self.assert_cache_shape(retrieve_body, 'POST /retrieve cross-endpoint cache probe')
            retrieval_cache = retrieve_body.get('cache', {}).get('retrieval', {})
            if retrieval_cache.get('hit') is True:
                self.pass_('Cross-endpoint retrieval cache', '/retrieve reused retrieval cache warmed by /search')
            else:
                self.fail('Cross-endpoint retrieval cache', self.pretty_value(retrieval_cache))

        exact_body = self.safe_json(
            'POST',
            '/search',
            'POST /search exact keyword cache probe',
            token=self.internal_token,
            json_body={
                'query': CACHE_EXACT_QUERY,
                'collection_id': self.collection_id,
                'top_k': 5,
                'enable_vector': False,
                'enable_keyword': True,
                'enable_rerank': True,
                'debug': True,
            },
            expected_status=200,
        )
        if isinstance(exact_body, dict):
            joined = ' '.join((item.get('text', '') or '') for item in exact_body.get('items', [])).lower()
            if 'sop-1042' in joined:
                self.pass_('Exact keyword retrieval evidence', 'keyword path returned SOP evidence')
            else:
                self.fail('Exact keyword retrieval evidence', self.pretty_value(exact_body.get('items', [])))

        numeric_body = self.safe_json(
            'POST',
            '/search',
            'POST /search numeric cache probe',
            token=self.internal_token,
            json_body={
                'query': CACHE_NUMERIC_QUERY,
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
            joined = ' '.join((item.get('text', '') or '') for item in numeric_body.get('items', [])).lower()
            if '48192' in joined and '2025-000184' in joined:
                self.pass_('Numeric retrieval evidence', 'hybrid retrieval returned numeric identifiers')
            else:
                self.fail('Numeric retrieval evidence', self.pretty_value(numeric_body.get('items', [])))

    def assert_invalidation_flow(self, invalidation_path: Path) -> None:
        self.upload_and_wait(invalidation_path, 'application/pdf')
        if self.search_version_before_invalidation is None:
            self.skip('Retrieval cache invalidation', 'initial cache version was unavailable')
            return

        body = self.safe_json(
            'POST',
            '/search',
            'POST /search after invalidation',
            token=self.internal_token,
            json_body={
                'query': CACHE_SEARCH_QUERY,
                'collection_id': self.collection_id,
                'top_k': 5,
                'enable_vector': True,
                'enable_keyword': True,
                'enable_rerank': True,
                'debug': True,
            },
            expected_status=200,
        )
        if not isinstance(body, dict):
            return
        self.assert_cache_shape(body, 'POST /search after invalidation')
        scope = body.get('cache_version_scope', {})
        version_after = scope.get('version') if isinstance(scope, dict) else None
        retrieval_cache = body.get('cache', {}).get('retrieval', {})
        if version_after != self.search_version_before_invalidation:
            self.pass_('Retrieval cache version bump', f'version changed from {self.search_version_before_invalidation} to {version_after}')
        else:
            self.fail('Retrieval cache version bump', self.pretty_value(scope))
        if retrieval_cache.get('hit') is False:
            self.pass_('Retrieval cache invalidation', 'post-ingestion search did not reuse stale retrieval cache')
        else:
            self.fail('Retrieval cache invalidation', self.pretty_value(retrieval_cache))

    def assert_chat_cache_flow(self) -> None:
        first_events = self.request_sse(
            token=self.internal_token,
            json_body={
                'mode': 'knowledge_qa',
                'message': CACHE_CHAT_QUERY,
                'collection_id': self.collection_id,
            },
            label='POST /chat first cache probe',
        )
        if not first_events:
            return
        self.assert_sse_sequence(first_events, 'POST /chat first cache probe')
        first_retrieval_event = self.find_event(first_events, 'retrieval.completed')
        first_generation_started = self.find_event(first_events, 'generation.started')
        first_generation_completed = self.find_event(first_events, 'generation.completed')
        first_session_id = self.extract_session_id(first_events)

        if first_retrieval_event:
            retrieval_payload = self.event_payload(first_retrieval_event)
            cache_block = retrieval_payload.get('cache', {}) if isinstance(retrieval_payload, dict) else {}
            if isinstance(cache_block, dict) and 'retrieval' in cache_block:
                self.pass_('Chat retrieval cache metadata', 'retrieval.completed included cache block')
            else:
                self.fail('Chat retrieval cache metadata', self.pretty_value(retrieval_payload))
        else:
            self.fail('Chat retrieval cache metadata', 'retrieval.completed event missing')

        if first_generation_started:
            generation_payload = self.event_payload(first_generation_started)
            if 'cache' in generation_payload:
                self.pass_('Chat generation cache metadata', 'generation.started included cache block')
            else:
                self.fail('Chat generation cache metadata', self.pretty_value(generation_payload))

        if first_generation_completed:
            generation_payload = self.event_payload(first_generation_completed)
            if 'cache' in generation_payload:
                self.pass_('Chat generation completed cache metadata', 'generation.completed included cache block')
            else:
                self.fail('Chat generation completed cache metadata', self.pretty_value(generation_payload))

        second_events = self.request_sse(
            token=self.internal_token,
            json_body={
                'mode': 'knowledge_qa',
                'message': CACHE_CHAT_QUERY,
                'collection_id': self.collection_id,
            },
            label='POST /chat second cache probe',
        )
        if not second_events:
            return
        self.assert_sse_sequence(second_events, 'POST /chat second cache probe')
        second_retrieval_event = self.find_event(second_events, 'retrieval.completed')
        second_generation_started = self.find_event(second_events, 'generation.started')
        second_session_id = self.extract_session_id(second_events)

        if second_retrieval_event:
            retrieval_payload = self.event_payload(second_retrieval_event)
            retrieval_cache = retrieval_payload.get('cache', {}).get('retrieval', {}) if isinstance(retrieval_payload.get('cache'), dict) else {}
            if retrieval_cache.get('hit') is True:
                self.pass_('Chat retrieval cache reuse', 'second chat request reused retrieval cache')
            else:
                self.fail('Chat retrieval cache reuse', self.pretty_value(retrieval_payload))
        else:
            self.fail('Chat retrieval cache reuse', 'retrieval.completed event missing')

        if second_generation_started:
            generation_payload = self.event_payload(second_generation_started)
            cache_block = generation_payload.get('cache', {}) if isinstance(generation_payload, dict) else {}
            if EXPECT_PROMPT_CACHE:
                if generation_payload.get('generation_mode') != 'llm':
                    self.skip('Prompt cache reuse', f"generation_mode={generation_payload.get('generation_mode')} so prompt cache is not applicable")
                elif isinstance(cache_block, dict) and cache_block.get('hit') is True:
                    self.pass_('Prompt cache reuse', 'second chat request reused prompt cache')
                else:
                    self.fail('Prompt cache reuse', self.pretty_value(generation_payload))
            else:
                self.skip('Prompt cache reuse', 'EXPECT_PROMPT_CACHE is not enabled for this run')

        session_id_for_detail = second_session_id or first_session_id
        if session_id_for_detail:
            detail_body = self.safe_json('GET', f'/chat/sessions/{session_id_for_detail}', 'GET /chat/sessions/{id} cache probe', token=self.internal_token, expected_status=200)
            if isinstance(detail_body, dict):
                messages = detail_body.get('messages', [])
                assistant_messages = [message for message in messages if message.get('role') == 'assistant']
                sourced_messages = [message for message in assistant_messages if message.get('sources')]
                if sourced_messages:
                    self.pass_('Assistant citations persisted', f'assistant_messages_with_sources={len(sourced_messages)}')
                else:
                    insufficient_messages = [
                        message for message in assistant_messages
                        if 'not enough information in the uploaded knowledge base' in (message.get('content', '') or '').lower()
                        or 'i could not find enough information in the uploaded knowledge base' in (message.get('content', '') or '').lower()
                    ]
                    if insufficient_messages:
                        self.pass_('Assistant citations persisted', 'no citations expected for insufficient-evidence response')
                    else:
                        self.fail('Assistant citations persisted', 'assistant messages had no persisted sources')

        if EXPECT_ANSWER_CACHE:
            self.assert_answer_cache_flow()
        else:
            self.skip('Answer cache reuse', 'EXPECT_ANSWER_CACHE is not enabled for this run')

    def assert_answer_cache_flow(self) -> None:
        first_events = self.request_sse(
            token=self.internal_token,
            json_body={
                'mode': 'knowledge_qa',
                'message': CACHE_MISS_QUERY,
                'collection_id': self.collection_id,
            },
            label='POST /chat answer cache warmup',
        )
        if not first_events:
            return
        second_events = self.request_sse(
            token=self.internal_token,
            json_body={
                'mode': 'knowledge_qa',
                'message': CACHE_MISS_QUERY,
                'collection_id': self.collection_id,
            },
            label='POST /chat answer cache reuse',
        )
        if not second_events:
            return

        generation_started = self.find_event(second_events, 'generation.started')
        if not generation_started:
            self.fail('Answer cache reuse', 'generation.started event missing on second insufficient-evidence request')
            return

        payload = self.event_payload(generation_started)
        cache_block = payload.get('cache', {}) if isinstance(payload, dict) else {}
        if isinstance(cache_block, dict) and cache_block.get('eligible') is False:
            self.skip('Answer cache reuse', 'server-side answer cache is not enabled for this response path')
        elif payload.get('generation_mode') == 'answer_cache':
            self.pass_('Answer cache reuse', 'second insufficient-evidence request reused deterministic answer cache')
        else:
            self.fail('Answer cache reuse', self.pretty_value(payload))

    def run(self) -> int:
        self.section('Health')
        self.safe_json('GET', '/health', 'GET /health', expected_status=200)
        self.safe_json('GET', '/db-health', 'GET /db-health', expected_status=200)

        self.section('Bootstrap And Auth')
        self.ensure_user(os.getenv('ADMIN_EMAIL', 'admin@example.com'), os.getenv('ADMIN_PASSWORD', 'StrongPass123!'), 'Platform Admin', 'admin', None)
        self.admin_token = self.login(os.getenv('ADMIN_EMAIL', 'admin@example.com'), os.getenv('ADMIN_PASSWORD', 'StrongPass123!'), 'admin')
        if not self.admin_token:
            print('\nAdmin login failed. Re-run with valid ADMIN_EMAIL and ADMIN_PASSWORD if your DB is not empty.', flush=True)
            return 1
        self.ensure_user(os.getenv('INTERNAL_EMAIL', 'internal@example.com'), os.getenv('INTERNAL_PASSWORD', 'StrongPass123!'), 'Internal User', 'internal_user', self.admin_token)
        self.internal_token = self.login(os.getenv('INTERNAL_EMAIL', 'internal@example.com'), os.getenv('INTERNAL_PASSWORD', 'StrongPass123!'), 'internal_user')
        if not self.internal_token:
            return 1

        self.section('Collection And Uploads')
        self.create_collection()
        if not self.collection_id:
            self.fail('Collection prerequisite', 'collection_id missing; stopping')
            return 1
        csv_path, pdf_path, invalidation_path = self.create_test_files()
        self.upload_and_wait(csv_path, 'text/csv')
        self.upload_and_wait(pdf_path, 'application/pdf')

        self.section('Search And Retrieve Cache')
        self.assert_search_cache_flow()

        self.section('Cache Invalidation')
        self.assert_invalidation_flow(invalidation_path)

        self.section('Chat Cache And SSE')
        self.assert_chat_cache_flow()

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
    runner = CacheLayerTestRunner()
    return runner.run()


if __name__ == '__main__':
    raise SystemExit(main())
