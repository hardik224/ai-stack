import re
from typing import Any


WORD_RE = re.compile(r"[a-z0-9]+")


MODE_GUIDANCE = {
    'knowledge_qa': {
        'label': 'Knowledge Q&A',
        'system': (
            'You are AI Stack Assistant in knowledge-base question answering mode. '
            'Answer strictly and only from the provided evidence. Never answer from general world knowledge, prior training, or assumptions. '
            'If the evidence is partial, clearly state what is known and what remains uncertain. '
            'If the evidence is insufficient, explicitly say that the uploaded knowledge base does not contain enough information. '
            'Always produce structured markdown with these sections when evidence exists: '
            '# Answer, ## Key Points, ## Evidence, ## Sources. '
            'Add ## Uncertainty only when needed. Use inline citations like [S1], [S2] that exactly match the provided source labels. '
            'Do not cite any source that is not in the provided evidence. Keep the answer concise, operational, and precise.'
        ),
        'instructions': [
            'Answer only from the evidence above.',
            'Never use general knowledge if the evidence does not support the answer.',
            'If the answer is not present in the evidence, say the knowledge base does not contain enough information.',
            'Use markdown headings and bullets.',
            'Cite supported claims inline with [S#].',
            'Include a ## Sources section listing the cited sources.',
            'If evidence is incomplete, add a short ## Uncertainty section.',
            'Prefer direct operational guidance for SOPs, product docs, and internal manuals.',
        ],
    },
    'analysis': {
        'label': 'Analysis',
        'system': (
            'You are AI Stack Assistant in analysis mode. '
            'Reason carefully over the provided evidence from PDFs, CSV rows, and documentation. '
            'You may synthesize across multiple sources, but every factual claim, trend, comparison, or calculation must be grounded in the retrieved evidence. '
            'Do not invent missing numbers, missing business logic, or fill gaps with general knowledge. '
            'If the evidence is partial, explain what can be concluded and what cannot be concluded yet. '
            'If the evidence is insufficient, say that the uploaded knowledge base does not contain enough information for a reliable analysis. '
            'Always produce structured markdown with these sections when evidence exists: '
            '# Answer, ## Key Findings, ## Analysis, ## Evidence, ## Sources. '
            'Add ## Uncertainty when assumptions, gaps, or incomplete coverage exist. '
            'Use inline citations like [S1], [S2] that exactly match the provided source labels. '
            'Keep the analysis business-friendly, explicit, and careful.'
        ),
        'instructions': [
            'Analyze only from the evidence above.',
            'Never use general knowledge or unsupported assumptions to complete the analysis.',
            'If the evidence is too weak for a reliable conclusion, explicitly say so.',
            'Combine evidence across multiple files when useful.',
            'Use markdown headings and bullets or numbered lists where helpful.',
            'Cite supported findings inline with [S#].',
            'Show comparisons, trends, exceptions, or risk points only when grounded in the evidence.',
            'If data is incomplete for a full conclusion, explicitly state the gap in ## Uncertainty.',
        ],
    },
}



def build_chat_prompt(*, question: str, context_items: list[dict], history_messages: list[dict], mode: str) -> list[dict[str, str]]:
    guidance = MODE_GUIDANCE.get(mode, MODE_GUIDANCE['knowledge_qa'])
    context_block = format_context_block(context_items)
    messages: list[dict[str, str]] = [{'role': 'system', 'content': guidance['system']}]

    for message in history_messages:
        role = message.get('role')
        if role not in {'user', 'assistant'}:
            continue
        messages.append({'role': role, 'content': message.get('content', '')})

    instruction_lines = '\n'.join(f'- {line}' for line in guidance['instructions'])
    user_prompt = (
        f"Mode: {guidance['label']}\n\n"
        'Question:\n'
        f'{question.strip()}\n\n'
        'Evidence:\n'
        f'{context_block}\n\n'
        'Instructions:\n'
        f'{instruction_lines}\n'
    )
    messages.append({'role': 'user', 'content': user_prompt})
    return messages



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
            f"[{item['citation_label']}] file={item['filename']} file_id={item['file_id']} chunk_id={item['chunk_id']} ({location_text})\n{item['text']}"
        )
    return '\n\n'.join(blocks)



def build_insufficient_evidence_markdown(*, question: str, mode: str) -> str:
    if mode == 'analysis':
        return (
            '# Answer\n\n'
            'I could not find enough grounded evidence in the uploaded knowledge base to produce a reliable analysis.\n\n'
            '## Key Findings\n\n'
            '- I searched the indexed documents and report data related to your request.\n'
            '- The available evidence is not strong enough to support a trustworthy multi-file analysis.\n'
            '- I will not fill the gaps with general knowledge or unsupported assumptions.\n'
            '- Please upload more relevant reports or narrow the question to a specific metric, time range, or process area.\n\n'
            '## Analysis\n\n'
            f'- Original request: **{question.strip()}**\n'
            '- A grounded analytical conclusion is not possible from the currently retrieved evidence.\n\n'
            '## Sources\n\n'
            '- No reliable source citations were available for this analysis.\n'
        )
    return (
        '# Answer\n\n'
        'I could not find enough information in the uploaded knowledge base to answer this confidently.\n\n'
        '## Key Points\n\n'
        '- I searched the indexed documents for evidence related to your question.\n'
        '- The available evidence is not strong enough to support a reliable grounded answer.\n'
        '- I will not answer from general knowledge or assumptions when the knowledge base does not support it.\n'
        '- Please upload more relevant documents or refine the question with more specific terms.\n\n'
        '## Evidence\n\n'
        f'- Original question: **{question.strip()}**\n'
        '- Retrieved evidence was insufficient for a grounded answer.\n\n'
        '## Sources\n\n'
        '- No reliable source citations were available for this answer.\n'
    )



def suggest_session_title(message: str) -> str:
    words = WORD_RE.findall(message.lower())[:8]
    if not words:
        return 'New Chat'
    title = ' '.join(words)
    return title[:80].title()
