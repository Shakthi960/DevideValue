from fastapi import (
    APIRouter,
    Header,
    HTTPException
)

from pydantic import BaseModel, EmailStr

from app.core.supabase import supabase


router = APIRouter(
    prefix="/api/auth",
    tags=["Auth"]
)


# ============================================================
# SCHEMAS
# ============================================================

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str = ""


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


def _serialize_user(user) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name":
            user.user_metadata.get("full_name", ""),
        "created_at": (
            user.created_at.isoformat()
            if user.created_at
            else None
        ),
    }


# ============================================================
# REGISTER
# ============================================================

@router.post("/register", response_model=AuthResponse)
def register(data: RegisterRequest):
    email = data.email

    if len(data.password) < 6:
        raise HTTPException(
            status_code=422,
            detail="Password must be at least 6 characters"
        )

    try:
        result = supabase.auth.sign_up({
            "email": email,
            "password": data.password,
            "options": {
                "data": {
                    "full_name": data.full_name
                }
            }
        })
    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    user = result.user

    if user is None:
        raise HTTPException(
            status_code=400,
            detail="Unable to create user"
        )

    session = result.session

    if session is None:
        raise HTTPException(
            status_code=200,
            detail=(
                "Account created. "
                "Please verify your email."
            )
        )

    return AuthResponse(
        access_token=session.access_token,
        user=_serialize_user(user)
    )


# ============================================================
# LOGIN
# ============================================================

@router.post("/login", response_model=AuthResponse)
def login(data: LoginRequest):
    email = data.email

    try:
        result = supabase.auth.sign_in_with_password({
            "email": email,
            "password": data.password
        })
    except Exception as error:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    user = result.user

    if user is None or result.session is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    return AuthResponse(
        access_token=result.session.access_token,
        user=_serialize_user(user)
    )


# ============================================================
# GET CURRENT USER
# ============================================================

@router.get("/me")
def get_me(
    authorization: str = Header(None)
):
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated"
        )

    token = authorization.replace(
        "Bearer ",
        "",
        1
    )

    try:
        user = supabase.auth.get_user(token).user
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )

    return _serialize_user(user)
