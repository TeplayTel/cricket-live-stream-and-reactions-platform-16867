from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field, EmailStr
from typing import Dict, Optional
from datetime import datetime, timedelta
from jose import JWTError, jwt

# == Temporary in-memory user store ==
# In production, use a database.
_fake_user_db: Dict[str, dict] = {}

SECRET_KEY = "devsecret-please-change"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# --- Models ---

class UserRegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="User email (used for login)")
    password: str = Field(..., min_length=6, description="Raw password (will be hashed)")
    display_name: Optional[str] = Field(None, description="Public display name for the user")

class UserLoginRequest(BaseModel):
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., min_length=6, description="User password")

class Token(BaseModel):
    access_token: str
    token_type: str

class UserProfile(BaseModel):
    email: EmailStr
    display_name: Optional[str]
    created_at: datetime
    # For future: avatar_url, reactions_history, chat_history

# --- Util functions ---

def _get_user(email: str) -> Optional[dict]:
    return _fake_user_db.get(email.lower())

def _hash_password(raw: str) -> str:
    # Use real password hashing in production (bcrypt/argon2)!
    return "psw$" + raw[::-1]

def _verify_password(raw: str, hashed: str) -> bool:
    return _hash_password(raw) == hashed

def _create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# --- Auth dependency ---

# PUBLIC_INTERFACE
def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Get current authenticated user from JWT token.
    Raises HTTP_401 if invalid/expired.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = _get_user(email)
    if user is None:
        raise credentials_exception
    return user

# --- API Router ---

router = APIRouter(prefix="/auth", tags=["auth"])

# PUBLIC_INTERFACE
@router.post("/register", summary="Register new user", response_model=UserProfile, responses={201: {"description": "User registered"}})
async def register_user(req: UserRegisterRequest):
    """
    Register a new user and return profile.
    """
    email_l = req.email.lower()
    if _get_user(email_l):
        raise HTTPException(status_code=400, detail="Email already registered")
    user_obj = {
        "email": email_l,
        "password_hash": _hash_password(req.password),
        "display_name": req.display_name or email_l.split('@')[0],
        "created_at": datetime.utcnow()
    }
    _fake_user_db[email_l] = user_obj
    return UserProfile(
        email=user_obj["email"],
        display_name=user_obj["display_name"],
        created_at=user_obj["created_at"],
    )

# PUBLIC_INTERFACE
@router.post("/login", summary="Authenticate user and return JWT", response_model=Token, responses={200: {"description": "Access token"}, 401: {"description": "Invalid credentials"}})
async def login_user(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Authenticate user credentials and return JWT token (Bearer).
    """
    user = _get_user(form_data.username.lower())
    if not user or not _verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = _create_access_token(data={"sub": user["email"]})
    return Token(access_token=token, token_type="bearer")

# PUBLIC_INTERFACE
@router.post("/logout", summary="Logout current user (stateless for JWT)", responses={200: {"description": "Logged out"}})
async def logout(request: Request, token: str = Depends(oauth2_scheme)):
    """
    "Logout" user by suggesting the client to drop their JWT (no effect server-side with stateless JWT).
    """
    return {"detail": "Token revoked client-side. Please remove JWT from your storage."}

# PUBLIC_INTERFACE
@router.get("/me", summary="Get current user profile", response_model=UserProfile)
async def get_my_profile(user: dict = Depends(get_current_user)):
    """
    Returns the profile of the authenticated user.
    """
    return UserProfile(
        email=user["email"],
        display_name=user.get("display_name"),
        created_at=user.get("created_at")
    )
