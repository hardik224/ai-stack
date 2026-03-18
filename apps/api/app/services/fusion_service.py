from collections import defaultdict



def fuse_candidates(
    *,
    vector_items: list[dict],
    keyword_items: list[dict],
    rrf_k: int,
    vector_weight: float,
    keyword_weight: float,
) -> list[dict]:
    combined: dict[str, dict] = {}
    contributions: defaultdict[str, list[dict]] = defaultdict(list)

    for source_name, items, weight in (
        ('vector', vector_items, vector_weight),
        ('keyword', keyword_items, keyword_weight),
    ):
        for rank, item in enumerate(items, start=1):
            chunk_id = item['chunk_id']
            fused_increment = weight / (rrf_k + rank)
            if chunk_id not in combined:
                combined[chunk_id] = dict(item)
                combined[chunk_id]['fused_score'] = 0.0
                combined[chunk_id]['retrieval_sources'] = list(item.get('retrieval_sources', [source_name]))
                combined[chunk_id]['match_reasons'] = list(item.get('match_reasons', []))
            else:
                existing = combined[chunk_id]
                existing['vector_score'] = max(float(existing.get('vector_score', 0.0)), float(item.get('vector_score', 0.0)))
                existing['keyword_score'] = max(float(existing.get('keyword_score', 0.0)), float(item.get('keyword_score', 0.0)))
                existing['score'] = max(float(existing.get('score', 0.0)), float(item.get('score', 0.0)))
                existing['lexical_overlap'] = max(float(existing.get('lexical_overlap', 0.0)), float(item.get('lexical_overlap', 0.0)))
                for source in item.get('retrieval_sources', [source_name]):
                    if source not in existing['retrieval_sources']:
                        existing['retrieval_sources'].append(source)
                for reason in item.get('match_reasons', []):
                    if reason not in existing['match_reasons']:
                        existing['match_reasons'].append(reason)
                if existing.get('vector_rank') is None and item.get('vector_rank') is not None:
                    existing['vector_rank'] = item['vector_rank']
                if existing.get('keyword_rank') is None and item.get('keyword_rank') is not None:
                    existing['keyword_rank'] = item['keyword_rank']

            combined[chunk_id]['fused_score'] += fused_increment
            contributions[chunk_id].append(
                {
                    'source': source_name,
                    'rank': rank,
                    'weight': weight,
                    'increment': round(fused_increment, 8),
                }
            )

    items = list(combined.values())
    for item in items:
        item['fused_score'] = round(float(item.get('fused_score', 0.0)), 8)
        item['fusion_details'] = contributions[item['chunk_id']]
    items.sort(
        key=lambda item: (
            item.get('fused_score', 0.0),
            item.get('keyword_score', 0.0),
            item.get('vector_score', 0.0),
            item.get('lexical_overlap', 0.0),
        ),
        reverse=True,
    )
    return items
