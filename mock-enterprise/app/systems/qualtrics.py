"""Mock Qualtrics Survey API.

Real API shape: GET /API/v3/surveys/{surveyId}/responses
Response: {"result": {"elements": [...], "nextPage": null}, "meta": {"httpStatus": "200"}}
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import QSurvey, QResponse

router = APIRouter(prefix="/api/qualtrics", tags=["Qualtrics"])


def _serialize(obj):
    d = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    for k, v in d.items():
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return d


def _qualtrics_response(elements: list) -> dict:
    """Mimic Qualtrics API response shape."""
    return {
        "result": {"elements": elements, "nextPage": None},
        "meta": {"httpStatus": "200 - OK", "requestId": "mock-request"},
    }


# --- Surveys ---

@router.get("/surveys")
def list_surveys(
    status: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(QSurvey)
    if status:
        query = query.filter(QSurvey.status == status)
    return _qualtrics_response([_serialize(s) for s in query.all()])


@router.get("/surveys/{survey_id}")
def get_survey(survey_id: str, db: Session = Depends(get_db)):
    survey = db.query(QSurvey).filter(QSurvey.id == survey_id).first()
    if not survey:
        return {"meta": {"httpStatus": "404 - Not Found"}}
    result = _serialize(survey)
    result["response_count"] = db.query(QResponse).filter(QResponse.survey_id == survey_id).count()
    return {"result": result, "meta": {"httpStatus": "200 - OK"}}


# --- Responses ---

@router.get("/surveys/{survey_id}/responses")
def list_responses(
    survey_id: str,
    period: str | None = None,
    relationship_name: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(QResponse).filter(QResponse.survey_id == survey_id)
    if period:
        query = query.filter(QResponse.period == period)
    if relationship_name:
        query = query.filter(QResponse.relationship_name.ilike(f"%{relationship_name}%"))
    return _qualtrics_response([_serialize(r) for r in query.order_by(QResponse.submitted_at.desc()).all()])


@router.get("/surveys/{survey_id}/responses/{response_id}")
def get_response(survey_id: str, response_id: str, db: Session = Depends(get_db)):
    resp = db.query(QResponse).filter(QResponse.id == response_id, QResponse.survey_id == survey_id).first()
    if not resp:
        return {"meta": {"httpStatus": "404 - Not Found"}}
    return {"result": _serialize(resp), "meta": {"httpStatus": "200 - OK"}}


@router.get("/surveys/{survey_id}/stats")
def survey_stats(survey_id: str, db: Session = Depends(get_db)):
    """Aggregate response statistics for a survey."""
    responses = db.query(QResponse).filter(QResponse.survey_id == survey_id).all()
    if not responses:
        return {"result": {"total_responses": 0}, "meta": {"httpStatus": "200 - OK"}}

    # Aggregate numeric answers
    all_answers = {}
    for r in responses:
        if r.answers:
            for key, value in r.answers.items():
                if isinstance(value, (int, float)):
                    all_answers.setdefault(key, []).append(value)

    averages = {k: round(sum(v) / len(v), 2) for k, v in all_answers.items()}

    return {
        "result": {
            "total_responses": len(responses),
            "companies_represented": len(set(r.respondent_company for r in responses if r.respondent_company)),
            "average_scores": averages,
            "by_period": _group_by_period(responses),
        },
        "meta": {"httpStatus": "200 - OK"},
    }


def _group_by_period(responses: list) -> dict:
    periods = {}
    for r in responses:
        if r.period:
            periods.setdefault(r.period, []).append(r)
    result = {}
    for period, resps in sorted(periods.items()):
        scores = []
        for r in resps:
            if r.answers:
                numeric = [v for v in r.answers.values() if isinstance(v, (int, float))]
                if numeric:
                    scores.extend(numeric)
        result[period] = {
            "response_count": len(resps),
            "avg_score": round(sum(scores) / len(scores), 2) if scores else None,
        }
    return result
