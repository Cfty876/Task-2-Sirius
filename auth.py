# auth.py (исправленная версия со строгой проверкой токенов)
from fastapi import APIRouter, HTTPException, status, Header, Depends, Query
from typing import Optional
from datetime import datetime, timedelta
from jose import JWTError, jwt
from database import get_db_connection, get_password_hash, verify_password
from models import UserCreate, UserLogin, Token, SearchResponse, UserResponse, UserRole

router = APIRouter()

# Настройки
SECRET_KEY = "booking-api-secret-key-2024"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str):
    try:
        # Убираем все пробелы и проверяем что токен не пустой
        token = token.strip()
        if not token:
            return None

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


# Dependency for authentication - СТРОГАЯ ВЕРСИЯ
async def get_current_user(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing"
        )

    # СТРОГАЯ проверка формата
    auth_parts = authorization.split()

    # Должно быть ровно 2 части: "Bearer" и токен
    if len(auth_parts) != 2:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format. Use 'Bearer <token>'"
        )

    # Проверяем что первая часть ТОЧНО "Bearer" (регистрозависимо)
    if auth_parts[0] != "Bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format. Use 'Bearer <token>' (case sensitive)"
        )

    token = auth_parts[1].strip()

    # Проверяем что токен не пустой
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing after 'Bearer'"
        )

    # Проверяем что в токене нет пробелов
    if ' ' in token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token contains spaces"
        )

    payload = verify_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )

    conn = get_db_connection()
    user = conn.execute(
        "SELECT id, email, username, role, is_active, created_at FROM users WHERE username = ? AND is_active = 1",
        (username,)
    ).fetchone()
    conn.close()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    return dict(user)


async def get_current_admin(user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return user


@router.post("/register", response_model=SearchResponse)
async def register(user_data: UserCreate):
    conn = get_db_connection()

    try:
        # Check if user exists
        existing_user = conn.execute(
            "SELECT * FROM users WHERE email = ? OR username = ?",
            (user_data.email, user_data.username)
        ).fetchone()

        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="Email or username already registered"
            )

        hashed_password = get_password_hash(user_data.password)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (email, username, hashed_password, role) VALUES (?, ?, ?, ?)",
            (user_data.email, user_data.username, hashed_password, user_data.role.value)
        )
        user_id = cursor.lastrowid
        conn.commit()

        new_user = conn.execute(
            "SELECT id, email, username, role, is_active, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()

        return SearchResponse(
            success=True,
            message="User registered successfully",
            data=dict(new_user)
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")
    finally:
        conn.close()


@router.post("/login", response_model=Token)
async def login(credentials: UserLogin):
    conn = get_db_connection()
    try:
        user = conn.execute(
            "SELECT * FROM users WHERE email = ? AND is_active = 1", (credentials.email,)
        ).fetchone()

        if not user or not verify_password(credentials.password, user["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )

        access_token = create_access_token(
            data={"sub": user["username"], "role": user["role"], "user_id": user["id"]}
        )

        user_response = {
            "id": user["id"],
            "email": user["email"],
            "username": user["username"],
            "role": user["role"],
            "is_active": bool(user["is_active"]),
            "created_at": user["created_at"]
        }

        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user_response
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")
    finally:
        conn.close()


@router.put("/profile", response_model=SearchResponse)
async def update_profile(
        new_username: str = Query(..., description="New username"),
        current_user: dict = Depends(get_current_user)
):
    if len(new_username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters long")

    conn = get_db_connection()
    try:
        # Check if username is taken
        existing_user = conn.execute(
            "SELECT * FROM users WHERE username = ? AND id != ?",
            (new_username, current_user["id"])
        ).fetchone()

        if existing_user:
            raise HTTPException(status_code=400, detail="Username already taken")

        # Update username
        conn.execute(
            "UPDATE users SET username = ? WHERE id = ?",
            (new_username, current_user["id"])
        )
        conn.commit()

        # Get updated user
        updated_user = conn.execute(
            "SELECT id, email, username, role, is_active, created_at FROM users WHERE id = ?",
            (current_user["id"],)
        ).fetchone()

        return SearchResponse(
            success=True,
            message="Username updated successfully",
            data=dict(updated_user)
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Profile update failed: {str(e)}")
    finally:
        conn.close()


@router.get("/me", response_model=SearchResponse)
async def get_current_user_profile(current_user: dict = Depends(get_current_user)):
    return SearchResponse(
        success=True,
        message="User profile retrieved successfully",
        data=current_user
    )


# ENDPOINT ДЛЯ ПОВЫШЕНИЯ ДО АДМИНА
@router.put("/promote-to-admin", response_model=SearchResponse)
async def promote_to_admin(
        target_user_id: int = Query(..., description="ID пользователя для повышения"),
        current_user: dict = Depends(get_current_admin)  # Только админы могут повышать
):
    conn = get_db_connection()
    try:
        # Проверяем существование пользователя
        target_user = conn.execute(
            "SELECT * FROM users WHERE id = ?", (target_user_id,)
        ).fetchone()

        if not target_user:
            raise HTTPException(status_code=404, detail="User not found")

        # Повышаем до админа
        conn.execute(
            "UPDATE users SET role = ? WHERE id = ?",
            (UserRole.ADMIN.value, target_user_id)
        )
        conn.commit()

        # Получаем обновленного пользователя
        updated_user = conn.execute(
            "SELECT id, email, username, role, is_active, created_at FROM users WHERE id = ?",
            (target_user_id,)
        ).fetchone()

        return SearchResponse(
            success=True,
            message=f"User {updated_user['username']} promoted to admin successfully",
            data=dict(updated_user)
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Promotion failed: {str(e)}")
    finally:
        conn.close()


# ENDPOINT ДЛЯ РЕГИСТРАЦИИ АДМИНА (только для существующих админов)
@router.post("/register-admin", response_model=SearchResponse)
async def register_admin(
        user_data: UserCreate,
        current_user: dict = Depends(get_current_admin)
):
    conn = get_db_connection()

    try:
        # Check if user exists
        existing_user = conn.execute(
            "SELECT * FROM users WHERE email = ? OR username = ?",
            (user_data.email, user_data.username)
        ).fetchone()

        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="Email or username already registered"
            )

        hashed_password = get_password_hash(user_data.password)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (email, username, hashed_password, role) VALUES (?, ?, ?, ?)",
            (user_data.email, user_data.username, hashed_password, UserRole.ADMIN.value)  # Принудительно ставим админа
        )
        user_id = cursor.lastrowid
        conn.commit()

        new_user = conn.execute(
            "SELECT id, email, username, role, is_active, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()

        return SearchResponse(
            success=True,
            message="Admin user registered successfully",
            data=dict(new_user)
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Admin registration failed: {str(e)}")
    finally:
        conn.close()