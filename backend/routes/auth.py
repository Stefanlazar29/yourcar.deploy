from fastapi import APIRouter, HTTPException, status
from backend.models import UserRegister, UserLogin, TokenResponse
from backend.database import DatabaseConnection
from backend.auth import PasswordManager, TokenManager

router = APIRouter(prefix="/api", tags=["auth"])


@router.get("/stats")
async def get_stats():
    db = DatabaseConnection()
    db.init_db()
    return db.get_stats()


@router.post("/register", response_model=TokenResponse)
async def register(user: UserRegister):
    """Register a new user."""
    if not user.email and not user.phone:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either email or phone must be provided"
        )

    db = DatabaseConnection()
    db.init_db()

    if user.email:
        existing = db.get_user_by_email(user.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

    if user.phone:
        existing = db.get_user_by_phone(user.phone)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone already registered"
            )

    password_hash = PasswordManager.hash_password(user.password)
    new_user = db.create_user(user.email, user.phone, password_hash)

    token = TokenManager.create_access_token(new_user["id"], user.email)

    return TokenResponse(
        user_id=new_user["id"],
        email=new_user["email"],
        phone=new_user["phone"],
        token=token,
        expires_in=86400
    )


@router.post("/login", response_model=TokenResponse)
async def login(user: UserLogin):
    """Login a user with email/phone and password."""
    if not user.email and not user.phone:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either email or phone must be provided"
        )

    db = DatabaseConnection()
    db.init_db()

    existing_user = None
    if user.email:
        existing_user = db.get_user_by_email(user.email)
    elif user.phone:
        existing_user = db.get_user_by_phone(user.phone)

    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    if not PasswordManager.verify_password(user.password, existing_user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    token = TokenManager.create_access_token(existing_user["id"], existing_user["email"])

    return TokenResponse(
        user_id=existing_user["id"],
        email=existing_user["email"],
        phone=existing_user["phone"],
        token=token,
        expires_in=86400
    )
