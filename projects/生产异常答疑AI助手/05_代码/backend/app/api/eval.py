"""评估路由：黄金测试用例查询（实际批量评估见 eval/run_eval.py）。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_roles
from app.models import QATestCase, User
from app.schemas.common import PageResult

router = APIRouter(prefix="/eval", tags=["评估"])


@router.get("/cases", response_model=PageResult[dict])
def list_cases(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    q = db.query(QATestCase)
    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    return PageResult(
        list=[
            {
                "id": c.id,
                "scenario": c.scenario,
                "question": c.question,
                "standard_answer": c.standard_answer,
                "expected_route": c.expected_route,
                "severity": c.severity,
            }
            for c in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
