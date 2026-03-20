import re
from typing import Any


WORD_RE = re.compile(r"[a-z0-9]+")


MODE_GUIDANCE = {
    'knowledge_qa': {
        'label': 'Knowledge Q&A',
        'system': (
            'You are AI Stack Assistant. Respond like a capable, helpful assistant, not like a search engine. '
            'Use the provided evidence as your ground truth and answer naturally in a direct, useful way. '
            'Start with the answer, then explain only what is needed. '
            'Synthesize across multiple files or chunks when they complement each other. '
            'Do not mention retrieval, embeddings, vector search, or internal system behavior unless the user explicitly asks. '
            'Never invent facts or fill gaps with general knowledge when the evidence does not support them. '
            'If the evidence is partial, explain what is known and what remains uncertain. '
            'Use inline citations like [S1], [S2] only for supported claims. '
            'Do not add a separate Sources heading inside the answer because the UI renders sources separately. '
            'Keep the answer concise, human, and operational.'
        ),
        'instructions': [
            'Answer only from the evidence and conversation context provided below.',
            'Give the direct answer first instead of narrating the search process.',
            'When the answer spans multiple chunks or files, combine them into one coherent answer instead of replying chunk by chunk.',
            'Reconcile related evidence from multiple files when they answer different parts of the question.',
            'Use markdown naturally when it helps clarity, but do not force the same section headings every time.',
            'Cite supported claims inline with [S#].',
            'Do not add a Sources heading in the body.',
            'If evidence is incomplete, add a short ## Uncertainty section.',
            'Prefer practical language for SOPs, product docs, internal manuals, and API references.',
            'Use source filenames as helpful context when they clarify which document a fact came from.',
        ],
    },
    'analysis': {
        'label': 'Analysis',
        'system': (
            'You are AI Stack Assistant in analysis mode. '
            'Think like a strong analytical assistant: combine, compare, summarize, and explain patterns across the provided evidence. '
            'Every factual claim, calculation, trend, comparison, or recommendation must stay grounded in the retrieved evidence. '
            'Do not invent missing numbers, missing business logic, or fill gaps with general knowledge. '
            'If the evidence is partial, explain what can be concluded and what cannot be concluded yet. '
            'Use a clear executive style: answer first, then supporting detail. '
            'Use inline citations like [S1], [S2] only for supported claims. '
            'Do not add a separate Sources heading inside the answer because the UI renders sources separately. '
            'Keep the analysis business-friendly, explicit, and careful.'
        ),
        'instructions': [
            'Analyze only from the evidence and conversation context provided below.',
            'Synthesize evidence from different files into one answer when they complement each other.',
            'Show comparisons, trends, exceptions, risks, or implications only when grounded in the evidence.',
            'Use markdown structure naturally; do not force the same section layout for every answer.',
            'Cite supported findings inline with [S#].',
            'Do not add a Sources heading in the body.',
            'Use source filenames and sheet/page/row hints when they help distinguish evidence from different uploaded files.',
            'If data is incomplete for a full conclusion, explicitly state the gap in ## Uncertainty.',
        ],
    },
}


def build_answer_style_guidance(question: str, mode: str) -> str:
    normalized = ' '.join((question or '').strip().lower().split())

    if mode == 'analysis':
        return (
            'Answer style:\n'
            '- Start with a short executive answer.\n'
            '- Then use compact sections or bullets for findings, implications, and risks when helpful.\n'
            '- Prefer synthesis over quotation.\n'
            '- Keep the tone smart, natural, and business-friendly.\n'
        )

    if normalized.startswith(('what is ', 'what are ', 'define ', 'who is ', 'what does ')):
        return (
            'Answer style:\n'
            '- Start with a short direct definition in 1 to 2 sentences.\n'
            '- Then add "More specifically:" with concise bullet points if useful.\n'
            '- If it helps clarity, end with "In simple terms:" and one plain-language sentence.\n'
            '- Avoid sounding like search results or raw notes.\n'
        )

    if normalized.startswith(('how ', 'how do ', 'how does ', 'steps', 'process', 'workflow')):
        return (
            'Answer style:\n'
            '- Start with the direct answer.\n'
            '- Then present the flow as short numbered steps.\n'
            '- Keep each step compact and easy to follow.\n'
        )

    if normalized.startswith(('compare ', 'difference ', 'differences ', 'vs ', 'versus ')):
        return (
            'Answer style:\n'
            '- Start with the main difference or conclusion.\n'
            '- Then use short comparison bullets.\n'
            '- Keep the structure crisp and decision-friendly.\n'
        )

    return (
        'Answer style:\n'
        '- Start with the direct answer.\n'
        '- Then add only the supporting detail that improves clarity.\n'
        '- Use bullets or short sections only when they genuinely help readability.\n'
        '- Keep the tone natural, polished, and helpful.\n'
    )


def build_chat_prompt(*, question: str, context_items: list[dict], history_messages: list[dict], mode: str) -> list[dict[str, str]]:
    guidance = MODE_GUIDANCE.get(mode, MODE_GUIDANCE['knowledge_qa'])
    context_block = format_context_block(context_items)
    evidence_overview = build_evidence_overview(context_items)
    conversation_context = build_conversation_context(history_messages)
    messages: list[dict[str, str]] = [{'role': 'system', 'content': guidance['system']}]

    instruction_lines = '\n'.join(f'- {line}' for line in guidance['instructions'])
    style_guidance = build_answer_style_guidance(question=question, mode=mode)
    user_prompt = (
        f"Mode: {guidance['label']}\n\n"
        'Current question:\n'
        f'{question.strip()}\n\n'
        'Conversation context:\n'
        f'{conversation_context}\n\n'
        'Evidence overview:\n'
        f'{evidence_overview}\n\n'
        'Evidence:\n'
        f'{context_block}\n\n'
        f'{style_guidance}\n'
        'Instructions:\n'
        f'{instruction_lines}\n'
    )
    messages.append({'role': 'user', 'content': user_prompt})
    return messages



def build_conversation_context(history_messages: list[dict[str, Any]]) -> str:
    if not history_messages:
        return '- No prior conversation context.'

    lines = []
    for message in history_messages[-6:]:
        role = message.get('role')
        if role not in {'user', 'assistant'}:
            continue
        content = ' '.join((message.get('content') or '').split())
        if not content:
            continue
        content = content[:280]
        prefix = 'User' if role == 'user' else 'Assistant'
        lines.append(f'- {prefix}: {content}')
    return '\n'.join(lines) if lines else '- No prior conversation context.'



def format_context_block(context_items: list[dict[str, Any]]) -> str:
    blocks = []
    for item in context_items:
        location = []
        if item.get('page_number'):
            location.append(f"page {item['page_number']}")
        if item.get('row_number'):
            location.append(f"row {item['row_number']}")
        location_text = ', '.join(location) if location else 'location unavailable'
        blocks.append(
            f"[{item['citation_label']}] source file: {item['filename']} | source type: {item.get('source_type') or 'document'} | {location_text}\n{item['text']}"
        )
    return '\n\n'.join(blocks)



def build_evidence_overview(context_items: list[dict[str, Any]]) -> str:
    if not context_items:
        return '- No grounded evidence retrieved.'

    file_map: dict[str, dict[str, Any]] = {}
    for item in context_items:
        key = str(item.get('file_id') or item.get('filename'))
        source_entry = file_map.setdefault(
            key,
            {
                'filename': item.get('filename') or 'Unknown file',
                'source_type': item.get('source_type') or 'document',
                'labels': [],
            },
        )
        source_entry['labels'].append(item['citation_label'])

    lines = []
    for source in file_map.values():
        labels = ', '.join(dict.fromkeys(source['labels']))
        lines.append(f"- {source['filename']} ({source['source_type']}): evidence labels {labels}")
    return '\n'.join(lines)



def build_insufficient_evidence_markdown(*, question: str, mode: str) -> str:
    if mode == 'analysis':
        return (
            "I couldn't find enough information in your uploaded files to give a reliable analysis. "
            'Please upload a more relevant file or ask a more specific question.'
        )
    return (
        "I couldn't find that in your uploaded files. "
        'Please upload a more relevant document or ask in a more specific way.'
    )



def suggest_session_title(message: str) -> str:
    words = WORD_RE.findall(message.lower())[:8]
    if not words:
        return 'New Chat'
    title = ' '.join(words)
    return title[:80].title()
