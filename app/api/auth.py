"""DEV-ONLY token issuance. Replace with real user management in Phase 5."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.auth.security import authenticate_dev_user, create_access_token
from app.models.schemas import TokenOut

router = APIRouter(prefix="/api/v1", tags=["auth"])


@router.post("/token", response_model=TokenOut)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    scopes = authenticate_dev_user(form_data.username, form_data.password)
    if scopes is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    token = create_access_token(subject=form_data.username, scopes=scopes)
    return TokenOut(access_token=token)
