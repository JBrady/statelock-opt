from pathlib import Path

from .constants import PROMPTS_DIR


def _read_fragment(group, name):
    if group == "citation_instruction":
        filename = {
            "required_inline_ids": "required_inline.txt",
            "required_footnotes": "required_footnote.txt",
            "concise_inline_ids": "concise_inline.txt",
        }[name]
    else:
        filename = f"{name}.txt"
    subdir = {
        "answer_style": "answer_style",
        "citation_instruction": "citation_mode",
        "refusal_behavior": "refusal_mode",
    }[group]
    path = PROMPTS_DIR / subdir / filename
    return path.read_text().strip()


def render_prompt(query, assembled, prompt_config):
    template = (PROMPTS_DIR / "base_system.txt").read_text()
    rendered = template.format(
        answer_style=_read_fragment("answer_style", prompt_config["answer_style"]),
        citation_instruction=_read_fragment("citation_instruction", prompt_config["citation_instruction"]),
        refusal_behavior=_read_fragment("refusal_behavior", prompt_config["refusal_behavior"]),
        query=query,
        context=assembled["context_text"],
    )
    return {
        "text": rendered,
        "settings": {
            "answer_style": prompt_config["answer_style"],
            "citation_instruction": prompt_config["citation_instruction"],
            "refusal_behavior": prompt_config["refusal_behavior"],
            "max_context_tokens": prompt_config["max_context_tokens"],
            "quote_budget_tokens": prompt_config["quote_budget_tokens"],
        },
    }
