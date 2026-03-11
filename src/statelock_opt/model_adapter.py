from .assemble import estimate_tokens
from .retrieve_lexical import tokenize


def _format_citations(cited_ids, citation_instruction):
    if not cited_ids:
        return ""
    if citation_instruction == "required_footnotes":
        refs = " ".join(f"[^{record_id}]" for record_id in cited_ids)
        notes = "\n".join(f"[^{record_id}]: {record_id}" for record_id in cited_ids)
        return f" {refs}\n{notes}"
    return " " + " ".join(f"[{record_id}]" for record_id in cited_ids)


def generate_response(case, assembled, prompt):
    selected = assembled["selected_records"]
    refusal_mode = prompt["settings"]["refusal_behavior"]
    answer_style = prompt["settings"]["answer_style"]
    citation_instruction = prompt["settings"]["citation_instruction"]
    query_tokens = set(tokenize(case["query"]))
    query_text = case["query"].lower()
    synthesis_cues = {"path", "process", "steps", "workflow", "route", "escalation", "handoff"}
    uncertainty_markers = (
        "pending",
        "did not choose",
        "no final",
        "still open",
        "not complete",
        "not enough information",
    )

    ranked_selected = sorted(selected, key=lambda item: (-item.get("retrieval_score", 0.0), item["id"]))
    primary = ranked_selected[0] if ranked_selected else None
    has_conflict = False
    if primary:
        for other in ranked_selected[1:]:
            if other["id"] in primary.get("contradicts_ids", []):
                close_in_confidence = abs(primary.get("confidence", 0.0) - other.get("confidence", 0.0)) <= 0.15
                close_in_score = other.get("retrieval_score", 0.0) >= primary.get("retrieval_score", 0.0) * 0.8
                if close_in_confidence or close_in_score:
                    has_conflict = True
                    break

    decisive = [record for record in ranked_selected if record.get("kind") in {"decision", "fact", "preference"}]
    cautionary = [
        record
        for record in ranked_selected
        if any(marker in record["text"].lower() for marker in ("likely", "tentative", "tentatively"))
    ]
    has_uncertain_evidence = any(
        marker in record["text"].lower()
        for record in ranked_selected
        for marker in uncertainty_markers
    )

    if not selected:
        text = "I do not have enough information to answer confidently."
        return {
            "text": text,
            "cited_ids": [],
            "used_record_ids": [],
            "refused": True,
            "warning": False,
            "prompt_tokens": estimate_tokens(prompt["text"]),
            "output_tokens": estimate_tokens(text),
        }

    if has_conflict and refusal_mode != "answer_if_partial_with_warning":
        text = "I do not have enough information to answer confidently because the retrieved records conflict."
        return {
            "text": text,
            "cited_ids": [],
            "used_record_ids": [],
            "refused": True,
            "warning": False,
            "prompt_tokens": estimate_tokens(prompt["text"]),
            "output_tokens": estimate_tokens(text),
        }

    if has_uncertain_evidence and not cautionary and refusal_mode != "answer_if_partial_with_warning":
        text = "I do not have enough information to answer confidently from the retrieved records."
        return {
            "text": text,
            "cited_ids": [],
            "used_record_ids": [],
            "refused": True,
            "warning": False,
            "prompt_tokens": estimate_tokens(prompt["text"]),
            "output_tokens": estimate_tokens(text),
        }

    if decisive:
        used = decisive[:1]
        if cautionary and refusal_mode != "strict_missing_evidence":
            used = [cautionary[0]]
            for record in decisive:
                if record["id"] != cautionary[0]["id"]:
                    used.append(record)
                    break
            warning = True
        elif answer_style != "concise":
            for extra in decisive[1:]:
                extra_tokens = set(tokenize(extra["text"]))
                if extra["id"] in used[0].get("contradicts_ids", []):
                    continue
                if extra.get("retrieval_score", 0.0) < used[0].get("retrieval_score", 0.0) * 0.65:
                    continue
                if len(extra_tokens & query_tokens) < 2:
                    continue
                if extra_tokens.issubset(set(tokenize(used[0]["text"]))):
                    continue
                if not any(cue in query_text for cue in synthesis_cues):
                    continue
                used.append(extra)
                break
            warning = False
        else:
            warning = False
    elif cautionary and refusal_mode != "strict_missing_evidence":
        used = cautionary[: 1 if answer_style == "concise" else 2]
        warning = True
    elif refusal_mode == "answer_if_partial_with_warning":
        used = selected[: 1 if answer_style == "concise" else 2]
        warning = True
    else:
        text = "I do not have enough information to answer confidently from the retrieved records."
        return {
            "text": text,
            "cited_ids": [],
            "used_record_ids": [],
            "refused": True,
            "warning": False,
            "prompt_tokens": estimate_tokens(prompt["text"]),
            "output_tokens": estimate_tokens(text),
        }

    body = " ".join(record["text"] for record in used)
    if warning:
        body = f"Based on available evidence, {body[0].lower() + body[1:]}"
    elif answer_style == "evidence_first":
        body = f"Supported by the retrieved memory, {body[0].lower() + body[1:]}"
    citations = _format_citations([record["id"] for record in used], citation_instruction)
    text = f"{body}{citations}".strip()
    return {
        "text": text,
        "cited_ids": [record["id"] for record in used],
        "used_record_ids": [record["id"] for record in used],
        "refused": False,
        "warning": warning,
        "prompt_tokens": estimate_tokens(prompt["text"]),
        "output_tokens": estimate_tokens(text),
    }
