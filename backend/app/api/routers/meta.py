from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import __version__
from app.config import api_docs_enabled, get_oidc_settings, get_registration_mode, password_login_enabled
from app.db.database import get_db
from app.schemas.invitation import MetaRead, OidcMeta
from app.services import setup_service

router = APIRouter()


@router.get("/meta", response_model=MetaRead)
def meta(db: Session = Depends(get_db)):
    """Public facts the login page needs (e.g. whether to offer "Register")."""
    return MetaRead(
        version=__version__,
        registration=get_registration_mode(),
        setup_needed=setup_service.needs_setup(db),
        password_login=password_login_enabled(),
        oidc=OidcMeta(label=oidc.label) if (oidc := get_oidc_settings()) is not None else None,
        api_docs=api_docs_enabled(),
    )
