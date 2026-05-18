import base64
import os
import re
from concurrent.futures import ThreadPoolExecutor

import requests
import urllib3

from .config import BASE_URL

VERIFY_SSL = True
DEFAULT_TIMEOUT = 20


def _apply_ssl(verify: bool):
    global VERIFY_SSL
    VERIFY_SSL = verify
    if not verify:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _req_get(url, **kwargs):
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
    return requests.get(url, verify=VERIFY_SSL, **kwargs)


def _req_post(url, **kwargs):
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
    return requests.post(url, verify=VERIFY_SSL, **kwargs)


def _req_put(url, **kwargs):
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
    return requests.put(url, verify=VERIFY_SSL, **kwargs)


def _friendly_request_error(e: Exception) -> str:
    """Возвращает понятное сообщение об ошибке вместо технического трейсбека."""
    s = str(e)
    if "SSLError" in s or "EOF occurred in violation of protocol" in s:
        return (
            "Ошибка SSL-соединения.\n\n"
            "Возможные причины:\n"
            "• Активен VPN — попробуйте отключить или настроить split-tunneling\n"
            "• Корпоративный прокси — укажите его адрес в Настройках\n\n"
            "Быстрый фикс: откройте ⚙ Настройки и отключите «Проверку SSL»."
        )
    if "ProxyError" in s or "Unable to connect to proxy" in s:
        return (
            "Не удалось подключиться через прокси.\n\n"
            "Проверьте адрес прокси в ⚙ Настройках или очистите поле прокси."
        )
    if "ConnectionError" in s or "Max retries exceeded" in s:
        return (
            "Нет соединения с сервером 1.shkolkovo.online.\n\n"
            "Проверьте интернет-подключение и настройки VPN/прокси."
        )
    if "401" in s or "Unauthorized" in s:
        return "JWT токен устарел или неверен. Скопируйте актуальный токен из браузера."
    if "403" in s or "Forbidden" in s:
        return "Доступ запрещён. Убедитесь, что у вашего аккаунта есть права администратора."
    return s


def set_proxy(proxy_url: str):
    """Устанавливает/удаляет переменные окружения для прокси."""
    if proxy_url and proxy_url.strip():
        os.environ["HTTP_PROXY"] = proxy_url.strip()
        os.environ["HTTPS_PROXY"] = proxy_url.strip()
    else:
        os.environ.pop("HTTP_PROXY", None)
        os.environ.pop("HTTPS_PROXY", None)


def get_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Cookie": f"jwt={token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Connection": "keep-alive",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
    }


def fetch_question(question_id: int, token: str) -> dict:
    url = f"{BASE_URL}/test/v1/question/admin/by-id/{question_id}"
    r = _req_get(url, headers=get_headers(token))
    r.raise_for_status()
    payload = r.json()
    result = payload.get("result")
    if not isinstance(result, dict):
        raise ValueError("Не удалось получить данные задачи: пустой ответ API")
    return result


def fetch_latex_session(session_id: int, token: str) -> dict:
    """Получает LaTeX-HTML/tex из сервиса LaTeX."""
    if not session_id:
        return {"tex": "", "html": ""}
    base = f"{BASE_URL}/latex-service/v1/GetSession/{session_id}"
    try:
        r = _req_get(base, headers=get_headers(token))
        if r.status_code != 200:
            return {"tex": "", "html": ""}
        res = r.json().get("Result", {})
        html_body = res.get("Html", "")
        css = res.get("Css", "")
        file_list = res.get("FileList", [])
    except Exception:
        return {"tex": "", "html": ""}

    tex = ""
    try:
        tr = _req_get(
            f"{base}/index.tex",
            params={"json": "1"},
            headers=get_headers(token),
        )
        if tr.status_code == 200:
            tex = tr.json().get("Result", "")
    except Exception:
        pass

    for svg in [f for f in file_list if f.endswith(".svg")]:
        try:
            sr = _req_get(f"{base}/{svg}", headers=get_headers(token))
            if sr.status_code == 200:
                b64 = base64.b64encode(sr.content).decode()
                html_body = html_body.replace(
                    f'src="{svg}"', f'src="data:image/svg+xml;base64,{b64}"'
                )
        except Exception:
            pass

    for img in [f for f in file_list if f.lower().endswith((".png", ".jpg", ".jpeg"))]:
        try:
            ir = _req_get(f"{base}/{img}", headers=get_headers(token))
            if ir.status_code == 200:
                ext = img.rsplit(".", 1)[1].lower()
                mime = "image/png" if ext == "png" else "image/jpeg"
                b64 = base64.b64encode(ir.content).decode()
                html_body = html_body.replace(
                    f'src="{img}"', f'src="data:{mime};base64,{b64}"'
                )
        except Exception:
            pass

    full_html = (
        '<!DOCTYPE html><html><head><meta charset="utf-8"><style>'
        'body{font-family:"CMU Serif","Times New Roman",serif;font-size:14px;'
        'margin:12px 16px;line-height:1.6;color:#1a1a1a;background:#fff}'
        'img.math{vertical-align:middle}img{max-width:100%}'
        f"p{{margin-top:0;margin-bottom:6px}}{css}"
        f"</style></head><body>{html_body}</body></html>"
    )
    return {"tex": tex, "html": full_html}


def extract_tex_body(tex: str) -> str:
    """Убирает preamble/ending LaTeX-документов."""
    if not tex:
        return ""
    m = re.search(r"\\begin\{document\}(.*?)\\end\{document\}", tex, re.DOTALL)
    return m.group(1).strip() if m else tex


def fetch_questions_without_hints(theme_id: int, token: str, page_size: int = 200) -> list[dict]:
    """Возвращает список задач темы, у которых нет подсказок (Faq пуст)."""
    url = f"{BASE_URL}/test/v1/question/admin/list"
    body = {
        "Condition": [
            {
                "Column": "QuestionTheme.ThemeId",
                "Operator": "=",
                "Value": [theme_id],
            }
        ],
        "Pagination": {"PerPage": page_size, "Page": 1},
        "Order": [{"Column": "Question.Id", "Desc": False}],
    }
    r = _req_post(url, headers=get_headers(token), json=body)
    r.raise_for_status()
    result = r.json().get("result", {})
    if isinstance(result, dict):
        items = result.get("questions", result.get("items", result.get("Items", [])))
    elif isinstance(result, list):
        items = result
    else:
        items = []
    if not isinstance(items, list):
        items = []
    return [q for q in items if not q.get("Faq") or len(q["Faq"]) == 0]


def save_hints_to_platform(question_id, hints, question_data, token):
    """Отправка подсказок обратно на платформу."""
    url = f"{BASE_URL}/test/v1/question/admin/edit/{question_id}"
    payload = {
        "Id": question_data["Id"],
        "Faq": hints,
        "Name": question_data.get("Name", ""),
        "AnswerTypeId": question_data.get("AnswerTypeId"),
        "InputType": question_data.get("InputType"),
        "IsDeactivated": question_data.get("IsDeactivated", False),
        "IsPrivate": question_data.get("IsPrivate", False),
        "IsSurvey": question_data.get("IsSurvey", False),
        "IsEGE": question_data.get("IsEGE", False),
        "Answer": question_data.get("Answer"),
        "Themes": question_data.get("Themes", []),
        "Tags": question_data.get("Tags", []),
        "DifficultyId": question_data.get("DifficultyId"),
        "ParentThemeId": question_data.get("ParentThemeId"),
        "SortOrder": question_data.get("SortOrder", 0),
        "LessonTimeCode": question_data.get("LessonTimeCode", 0),
    }
    r = _req_post(url, headers=get_headers(token), json=payload)
    r.raise_for_status()


def filter_question_ids_without_hints(question_ids: list[str], token: str, max_workers: int = 8) -> list[str]:
    """Оставляет только задачи, у которых ещё нет подсказок."""
    ordered_unique_ids = []
    seen = set()
    for qid in question_ids:
        if qid not in seen:
            ordered_unique_ids.append(qid)
            seen.add(qid)

    def inspect(qid: str):
        data = fetch_question(int(qid), token)
        faq = data.get("Faq") or []
        return qid, not faq

    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for qid, has_no_hints in executor.map(inspect, ordered_unique_ids):
            results[qid] = has_no_hints

    return [qid for qid in ordered_unique_ids if results.get(qid)]
