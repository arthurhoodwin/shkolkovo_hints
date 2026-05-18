import json
import re

from .api import _req_get, _req_post


def _compose_user_message(
    question_text,
    solution_text,
    existing_hints,
    system_prompt,
    reference_question,
    reference_hints,
) -> str:
    """Формирует сообщение-запрос для LLM."""
    existing_str = ""
    if existing_hints:
        existing_str = "\n\nУже существующие подсказки:\n"
        for i, h in enumerate(existing_hints, 1):
            parts = h if isinstance(h, list) else [h]
            existing_str += f"Подсказка {i}: {' | '.join(parts)}\n"

    reference_str = ""
    if reference_question and reference_hints:
        reference_str = "\n\n---\nПРИМЕР ЭТАЛОННЫХ ПОДСКАЗОК:\n"
        reference_str += f"Условие:\n{reference_question}\n\nПодсказки:\n"
        for i, h in enumerate(reference_hints, 1):
            parts = h if isinstance(h, list) else [h]
            reference_str += f"Подсказка {i}: {' | '.join(parts)}\n"
        reference_str += "---\n"

    user_msg = (
        f"УСЛОВИЕ ЗАДАЧИ:\n{question_text or '(не загружено)'}\n\n"
        f"РЕШЕНИЕ (контекст, не раскрывай):\n{solution_text or '(не загружено)'}"
        f"{existing_str}"
        f"{reference_str}"
        "\n\nВерни ТОЛЬКО JSON-массив массивов строк, без текста и markdown."
    )
    return user_msg


def _extract_json(raw: str) -> list:
    """Надёжно извлекает JSON из ответа LLM, обрабатывая все форматы обёртки."""
    text = raw.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if m:
        text = m.group(1).strip()
    bracket = text.find("[")
    if bracket != -1:
        depth = 0
        for i, ch in enumerate(text[bracket:], bracket):
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    text = text[bracket : i + 1]
                    break
    data = json.loads(text)
    if isinstance(data, dict):
        data = next(iter(data.values()))
    if not isinstance(data, list):
        raise ValueError(f"LLM вернул не массив: {type(data)}")
    return data


def generate_hints_groq(
    question_text,
    solution_text,
    existing_hints,
    system_prompt,
    api_key,
    model,
    temperature=0.7,
    reference_question=None,
    reference_hints=None,
) -> list:
    """Вызов Groq API (совместим с OpenAI-форматом)."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": _compose_user_message(
                    question_text,
                    solution_text,
                    existing_hints,
                    system_prompt,
                    reference_question,
                    reference_hints,
                ),
            },
        ],
        "temperature": temperature,
        "max_tokens": 4096,
    }
    r = _req_post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )
    r.raise_for_status()
    raw = r.json()["choices"][0]["message"]["content"].strip()
    data = _extract_json(raw)
    return data


MODELS_FALLBACK_GROQ = [
    "llama3-8b-8192",
    "mixtral-8x7b-32768",
    "gemma-7b-it",
]

MODELS = list(MODELS_FALLBACK_GROQ)


def fetch_free_models_from_groq(api_key: str) -> list[str]:
    """Список моделей Groq (только текстовые; без ключа - fallback)."""
    exclude_keywords = ("whisper", "vision", "guard", "tts", "embed")
    if not api_key:
        return MODELS_FALLBACK_GROQ
    try:
        r = _req_get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json().get("data", [])
        models = [
            model["id"]
            for model in data
            if "id" in model and not any(keyword in model["id"].lower() for keyword in exclude_keywords)
        ]
        models.sort()
        return models if models else MODELS_FALLBACK_GROQ
    except Exception:
        return MODELS_FALLBACK_GROQ
