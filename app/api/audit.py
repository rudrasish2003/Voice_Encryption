from fastapi import APIRouter, Depends

from app.auth.security import require_scopes
from app.repos.audit_repo import AuditRepo

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])

audit_repo = AuditRepo()


@router.get("")
def list_audit(limit: int = 100, payload: dict = Depends(require_scopes("audit:read"))):
    return audit_repo.query(limit=limit)
