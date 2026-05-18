import copy
from typing import Any

from .api import _req_get, _req_post, _req_put, get_headers
from .config import BASE_URL


def _extract_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result = payload.get("result", [])
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        for key in ("questions", "items", "Items", "result"):
            value = result.get(key)
            if isinstance(value, list):
                return value
    return []


def list_questions(
    token: str,
    *,
    page: int = 1,
    per_page: int = 50,
    question_id: int | None = None,
    parent_theme_id: int | None = None,
    difficulty_id: int | None = None,
    is_private: bool | None = None,
    is_deactivated: bool | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    conditions: list[dict[str, Any]] = []
    if question_id is not None:
        conditions.append({"Column": "Question.Id", "Operator": "=", "Value": [question_id]})
    if parent_theme_id is not None:
        conditions.append(
            {"Column": "QuestionTheme.ThemeId", "Operator": "=", "Value": [parent_theme_id]}
        )
    if difficulty_id is not None:
        conditions.append(
            {"Column": "Question.DifficultyId", "Operator": "=", "Value": [difficulty_id]}
        )
    if is_private is not None:
        conditions.append({"Column": "Question.IsPrivate", "Operator": "=", "Value": [is_private]})
    if is_deactivated is not None:
        conditions.append(
            {"Column": "Question.IsDeactivated", "Operator": "=", "Value": [is_deactivated]}
        )

    body = {
        "Condition": conditions,
        "Pagination": {"Page": page, "PerPage": per_page},
        "Order": [
            {"Column": "Question.SortOrder", "Desc": False},
            {"Column": "Question.Id", "Desc": False},
        ],
    }
    response = _req_post(
        f"{BASE_URL}/test/v1/question/admin/list",
        headers=get_headers(token),
        json=body,
    )
    response.raise_for_status()
    payload = response.json()
    items = _extract_items(payload)
    return items, payload


def get_question_by_id(question_id: int, token: str) -> dict[str, Any]:
    response = _req_get(
        f"{BASE_URL}/test/v1/question/admin/by-id/{question_id}",
        headers=get_headers(token),
    )
    response.raise_for_status()
    payload = response.json()
    result = payload.get("result")
    if not isinstance(result, dict):
        raise ValueError("API returned invalid question object")
    return result


def update_question(question: dict[str, Any], token: str) -> dict[str, Any]:
    qid = question.get("Id")
    if not isinstance(qid, int):
        raise ValueError("Question Id is missing")
    response = _req_post(
        f"{BASE_URL}/test/v1/question/admin/edit/{qid}",
        headers=get_headers(token),
        json=question,
    )
    response.raise_for_status()
    return response.json()


def update_related_questions(question_id: int, related_ids: list[int], token: str) -> None:
    payload = {"QuestionId": question_id, "RelatedQuestionIds": related_ids}
    response = _req_put(
        f"{BASE_URL}/test/v1/related-questions/admin/edit",
        headers=get_headers(token),
        json=payload,
    )
    response.raise_for_status()


def create_question_draft(
    token: str,
    *,
    name: str,
    theme_id: int,
    difficulty_id: int,
    source_id: int | None = None,
    answer_text: str = "",
    answer_type_id: int = 1,
    input_type: int = 1,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "Id": 0,
        "Name": name,
        "IsDeactivated": False,
        "AnswerTypeId": answer_type_id,
        "InputType": input_type,
        "QuestionTexSessionId": 0,
        "SolutionTexSessionId": 0,
        "GradeCriteriaTexSessionId": 0,
        "SolutionPlanTexSessionId": 0,
        "QuestionFiles": [],
        "SolutionFiles": [],
        "AnswerCheckoutFile": None,
        "AnswerNeedsAttachment": False,
        "RelatesToQuestionContentId": 0,
        "Themes": [theme_id],
        "SortOrder": 0,
        "Tags": [],
        "DifficultyId": difficulty_id,
        "Faq": [],
        "LessonTimeCode": 0,
        "QuestionTaskReviews": [],
        "Sources": [source_id] if source_id is not None else [],
        "Answer": {"TexSessionId": 0, "text": answer_text},
    }
    # HAR confirms this endpoint is used for creation flow.
    response = _req_put(
        f"{BASE_URL}/test/v1/question/admin/new",
        headers=get_headers(token),
        json=payload,
    )
    response.raise_for_status()
    payload = response.json()
    result = payload.get("result")
    if not isinstance(result, dict):
        raise ValueError("API returned invalid created question object")
    return result


def list_themes(token: str) -> list[dict[str, Any]]:
    response = _req_post(
        f"{BASE_URL}/test/v1/theme/admin/list",
        headers=get_headers(token),
        json={"Pagination": {"PerPage": 100000}},
    )
    response.raise_for_status()
    payload = response.json()
    result = payload.get("result", [])
    return result if isinstance(result, list) else []


def list_tags(token: str) -> list[dict[str, Any]]:
    response = _req_post(
        f"{BASE_URL}/test/v1/tags/list",
        headers=get_headers(token),
        json={"Pagination": {"PerPage": 10000}},
    )
    response.raise_for_status()
    payload = response.json()
    result = payload.get("result", [])
    return result if isinstance(result, list) else []


def list_difficulties(token: str, subject_id: int = 30) -> list[dict[str, Any]]:
    response = _req_post(
        f"{BASE_URL}/test/v1/subject-difficulty/admin/list",
        headers=get_headers(token),
        json={
            "Condition": [
                {"Column": "SubjectDifficulty.SubjectId", "Operator": "=", "Value": [str(subject_id)]}
            ]
        },
    )
    response.raise_for_status()
    payload = response.json()
    result = payload.get("result", [])
    return result if isinstance(result, list) else []


def patch_question_from_form(
    source_question: dict[str, Any],
    *,
    name: str,
    parent_theme_id: int | None,
    difficulty_id: int | None,
    source_id: int | None,
    sort_order: int,
    lesson_time_code: int,
    answer_text: str,
    is_private: bool,
    is_deactivated: bool,
    themes: list[int],
    tags: list[int],
    faq: list[list[str]],
) -> dict[str, Any]:
    question = copy.deepcopy(source_question)
    question["Name"] = name
    question["IsPrivate"] = is_private
    question["IsDeactivated"] = is_deactivated
    question["SortOrder"] = sort_order
    question["LessonTimeCode"] = lesson_time_code
    question["Themes"] = themes
    question["Tags"] = tags
    question["Faq"] = faq

    if parent_theme_id is not None:
        question["ParentThemeId"] = parent_theme_id
    if difficulty_id is not None:
        question["DifficultyId"] = difficulty_id
    if source_id is not None:
        question["SourceId"] = source_id

    answer = question.get("Answer")
    if not isinstance(answer, dict):
        answer = {"text": ""}
    answer["text"] = answer_text
    question["Answer"] = answer
    return question
