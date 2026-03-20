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
    if mode == 'analysis':
        return (
            'Answer style:\n'
            '- Choose the structure dynamically based on what the evidence supports.\n'
            '- Use plain paragraphs, bullets, numbered steps, short headings, or compact comparisons only when they genuinely improve clarity.\n'
            '- Do not force fixed labels, repeated section patterns, or canned answer templates.\n'
            '- Prefer clean synthesis over dumping notes or fragments.\n'
            '- Keep the tone smart, natural, and business-friendly.\n'
        )

    return (
        'Answer style:\n'
        '- Choose the structure dynamically based on the actual answer, not on a fixed template.\n'
        '- Use plain paragraphs for simple answers.\n'
        '- Use bullets only when listing items helps.\n'
        '- Use numbered steps only when the answer is truly sequential or procedural.\n'
        '- Use short headings only when the answer naturally has distinct parts.\n'
        '- Do not force labels like "More specifically" or "In simple terms" unless they naturally fit the response.\n'
        '- Keep the answer natural, polished, and easy to read.\n'
        '\n'
        'Additional style guidance:\n'
        '- Write in a clear, human, conversational way.\n'
        '- Prefer simple words over complicated wording.\n'
        '- Make the response feel helpful and natural, not robotic or overly formal.\n'
        '- Prioritize clarity, readability, and usefulness over sounding smart.\n'
        '- Avoid unnecessary jargon; when technical terms are needed, explain them simply.\n'
        '- Keep sentences reasonably short unless longer explanation genuinely helps.\n'
        '- Avoid repetitive phrasing and avoid repeating the user’s question back unless useful.\n'
        '- Do not over-explain when a concise answer is enough.\n'
        '- When the topic is complex, break it into clean, digestible parts.\n'
        '- Use examples only when they make the answer easier to understand.\n'
        '- Make formatting feel intentional and clean, never cluttered.\n'
        '- Keep transitions smooth so the response flows naturally.\n'
        '- Sound confident but not arrogant.\n'
        '- Be direct, but not blunt.\n'
        '- Be friendly, but not overly casual.\n'
        '- Do not use filler phrases that add no value.\n'
        '- Do not use generic AI-sounding phrases like "As an AI language model".\n'
        '- Do not sound like a textbook unless the user asks for a formal explanation.\n'
        '- Match the depth of the answer to the user’s question: simple for simple questions, detailed for complex ones.\n'
        '- If the user asks for practical help, give actionable guidance.\n'
        '- If multiple good answers exist, present the most useful one first.\n'
        '- When giving instructions, make them easy to follow.\n'
        '- When rewriting or generating text, make it sound natural and fluent.\n'
        '- Favor readability over perfect symmetry in formatting.\n'
        '- End cleanly without unnecessary wrap-up lines.\n'
    )


def build_language_guidance(question: str) -> str:
    has_indic_script = bool(
        re.search(
            r'[\u0900-\u097F\u0980-\u09FF\u0A00-\u0A7F\u0A80-\u0AFF\u0B00-\u0B7F\u0B80-\u0BFF\u0C00-\u0C7F\u0C80-\u0CFF\u0D00-\u0D7F]',
            question or '',
        )
    )
    normalized = ' '.join((question or '').strip().lower().split())
    hinglish_markers = {
        'kya', 'kaise', 'kyu', 'kyun', 'hai', 'hain', 'kar', 'karte', 'karna', 'karne', 'nahi', 'nahin',
        'sahi', 'tarike', 'tarika', 'samjhao', 'samjha', 'bolo', 'batao', 'iska', 'iske', 'isme', 'agar',
        'matlab', 'kr', 'karo', 'hoga', 'hogi', 'he', 'ho', 'acha', 'accha'
    }
    tokens = set(re.findall(r"[a-z']+", normalized))
    looks_hinglish = bool(tokens & hinglish_markers)

    if has_indic_script:
        return (
            'Language style:\n'
            '- Reply in the same Indian language and script used by the user.\n'
            '- If the user mixes that language with English technical terms, keep useful technical terms in English where natural.\n'
            '- Do not switch everything into Hindi or English unless the user does that first.\n'
        )

    if looks_hinglish:
        return (
            'Language style:\n'
            '- Reply in the same Hinglish style as the user.\n'
            '- Keep the wording natural, simple, and conversational.\n'
            '- Use English technical terms where they feel natural, but do not switch into fully formal English.\n'
        )

    return (
        'Language style:\n'
        '- Reply in the same language and tone as the user\'s question.\n'
        '- If the user asks in English, answer in English. If the user mixes languages, mirror that mix naturally.\n'
        '- Support Indian languages naturally when the user writes in them.\n'
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
