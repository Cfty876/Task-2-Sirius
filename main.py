from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import sys
from datetime import datetime

from database import init_db, get_db_connection
from auth import router as auth_router
from hotels import router as hotels_router
from flights import router as flights_router
from bookings import router as bookings_router
from models import ErrorResponse

# Настройка логирования с поддержкой Unicode
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Hotel & Flight Booking API...")
    try:
        init_db()
        logger.info("Database initialized successfully!")
        logger.info("Admin credentials: admin@example.com / admin123")
        logger.info("User credentials: user@example.com / user123")
        logger.info("API Documentation: http://localhost:8000/docs")
        logger.info("Health check: http://localhost:8000/health")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

    yield

    # Shutdown
    logger.info("Application shutting down...")


app = FastAPI(
    title="Hotel & Flight Booking API",
    description="""
    ## Полнофункциональное API для бронирования отелей и авиабилетов

    ### Основные возможности:
    - Безопасная аутентификация JWT
    - Управление отелями и номерами
    - Поиск и бронирование авиабилетов
    - Гибкая система бронирования
    - Ролевая модель (user/admin)

    ### Быстрый старт:
    1. Используйте тестовых пользователей для входа
    2. Изучите endpoints через Swagger UI
    3. Начните с поиска отелей или авиабилетов

    ### Тестовые пользователи:
    - **Admin**: admin@example.com / admin123
    - **User**: user@example.com / user123
    """,
    version="2.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутеров
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(hotels_router, prefix="/hotels", tags=["Hotels & Rooms"])
app.include_router(flights_router, prefix="/flights", tags=["Flights"])
app.include_router(bookings_router, prefix="/bookings", tags=["Bookings"])


@app.get("/", summary="Главная страница", description="Информация о API и доступных endpoints")
async def root():
    return {
        "message": "Hotel & Flight Booking API",
        "version": "2.1.0",
        "description": "Полнофункциональное API для бронирования отелей и авиабилетов",
        "endpoints": {
            "documentation": "/docs",
            "authentication": "/auth",
            "hotels": "/hotels",
            "flights": "/flights",
            "bookings": "/bookings"
        },
        "quick_start": "Используйте /docs для интерактивной документации и тестирования API"
    }


@app.get("/health", summary="Проверка здоровья", description="Проверка статуса приложения и базы данных")
async def health_check():
    try:
        conn = get_db_connection()
        conn.execute("SELECT 1")
        conn.close()
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "database": "connected",
            "version": "2.1.0"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")


@app.get("/status", summary="Статус системы", description="Подробная информация о состоянии системы")
async def system_status():
    conn = get_db_connection()

    # Получаем статистику
    stats = {}
    try:
        tables = ['users', 'hotels', 'rooms', 'flights', 'hotel_bookings', 'flight_bookings']
        for table in tables:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            stats[table] = count
    except Exception as e:
        logger.error(f"Error getting stats: {e}")

    conn.close()

    return {
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "database_stats": stats,
        "endpoints_available": 6,
        "memory_usage": "normal"
    }


# Глобальный обработчик ошибок
@app.exception_handler(500)
async def internal_server_error_handler(request, exc):
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal Server Error",
            details="An unexpected error occurred. Please try again later."
        ).model_dump()  # Исправлено: .dict() -> .model_dump()
    )


@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content=ErrorResponse(
            error="Not Found",
            details="The requested resource was not found."
        ).model_dump()  # Исправлено: .dict() -> .model_dump()
    )


if __name__ == "__main__":
    import uvicorn

    print("\n" + "=" * 60)
    print("Hotel & Flight Booking API Starting...")
    print("=" * 60)
    print("Documentation: http://localhost:8000/docs")
    print("Health Check: http://localhost:8000/health")
    print("System Status: http://localhost:8000/status")
    print("=" * 60 + "\n")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )