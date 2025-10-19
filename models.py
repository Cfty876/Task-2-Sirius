# models.py
from enum import Enum
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List, Any
from datetime import datetime
import re


class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"


class RoomType(str, Enum):
    STANDARD = "standard"
    LARGE = "large"
    PREMIUM = "premium"


class BookingStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


# Базовые схемы
class UserBase(BaseModel):
    email: str = Field(
        examples=["user@example.com"],
        description="Email пользователя"
    )
    username: str = Field(
        min_length=3,
        max_length=50,
        examples=["john_doe"],
        description="Имя пользователя от 3 до 50 символов"
    )
    role: UserRole = Field(
        default=UserRole.USER,
        examples=["user"],
        description="Роль пользователя в системе"
    )

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
            raise ValueError('Invalid email format')
        return v

    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('Username can only contain letters, numbers and underscores')
        return v


class UserCreate(UserBase):
    password: str = Field(
        min_length=6,
        max_length=100,
        examples=["securepassword123"],
        description="Пароль должен содержать минимум 6 символов"
    )

    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters long')
        return v


class UserLogin(BaseModel):
    email: str = Field(
        examples=["admin@example.com"],
        description="Email для входа в систему"
    )
    password: str = Field(
        examples=["admin123"],
        description="Пароль для аутентификации"
    )

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
            raise ValueError('Invalid email format')
        return v


class UserResponse(BaseModel):
    id: int = Field(examples=[1], description="Уникальный идентификатор пользователя")
    email: str = Field(examples=["user@example.com"], description="Email пользователя")
    username: str = Field(examples=["john_doe"], description="Имя пользователя")
    role: str = Field(examples=["user"], description="Роль пользователя")
    is_active: bool = Field(examples=[True], description="Статус активности аккаунта")
    created_at: str = Field(examples=["2024-01-01T00:00:00"], description="Дата регистрации")

    model_config = ConfigDict(from_attributes=True)


class SafeUserResponse(BaseModel):
    id: int = Field(examples=[1], description="Уникальный идентификатор пользователя")
    email: str = Field(examples=["user@example.com"], description="Email пользователя")
    username: str = Field(examples=["john_doe"], description="Имя пользователя")
    role: str = Field(examples=["user"], description="Роль пользователя")
    is_active: bool = Field(examples=[True], description="Статус активности аккаунта")
    created_at: str = Field(examples=["2024-01-01T00:00:00"], description="Дата регистрации")

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str = Field(description="JWT токен для авторизации запросов")
    token_type: str = Field(default="bearer", examples=["bearer"], description="Тип токена")
    expires_in: int = Field(default=7200, examples=[7200], description="Время жизни токена в секундах")
    user: SafeUserResponse = Field(description="Информация о аутентифицированном пользователе")


class HotelBase(BaseModel):
    name: str = Field(
        min_length=2,
        max_length=100,
        examples=["Grand Hotel"],
        description="Название отеля от 2 до 100 символов"
    )
    city: str = Field(
        min_length=2,
        max_length=50,
        examples=["Moscow"],
        description="Город расположения отеля"
    )
    address: Optional[str] = Field(
        default=None,
        examples=["Tverskaya st. 1"],
        description="Полный адрес отеля"
    )
    stars: int = Field(
        ge=1,
        le=5,
        examples=[5],
        description="Количество звезд от 1 до 5"
    )
    description: Optional[str] = Field(
        default=None,
        examples=["Luxury hotel in city center with premium amenities"],
        description="Подробное описание отеля и услуг"
    )

    @field_validator('stars')
    @classmethod
    def validate_stars(cls, v):
        if v not in [1, 2, 3, 4, 5]:
            raise ValueError('Stars must be between 1 and 5')
        return v


class HotelResponse(HotelBase):
    id: int = Field(examples=[1], description="Уникальный идентификатор отеля")
    created_at: str = Field(description="Дата и время создания записи")
    room_count: Optional[int] = Field(default=0, examples=[10], description="Количество доступных номеров")

    model_config = ConfigDict(from_attributes=True)


class RoomBase(BaseModel):
    room_number: str = Field(
        examples=["101"],
        description="Уникальный номер комнаты в отеле"
    )
    room_type: RoomType = Field(
        default=RoomType.STANDARD,
        examples=["standard"],
        description="Категория номера"
    )
    price_per_night: float = Field(
        gt=0,
        examples=[100.0],
        description="Стоимость за одну ночь"
    )
    capacity: int = Field(
        ge=1,
        le=10,
        examples=[2],
        description="Максимальное количество гостей"
    )
    room_count: int = Field(
        default=1,
        ge=1,
        le=5,
        examples=[1],
        description="Количество комнат в номере"
    )
    features: Optional[str] = Field(
        default=None,
        examples=["Sea view, King bed, WiFi, Mini-bar"],
        description="Список удобств и особенностей номера"
    )

    @field_validator('price_per_night')
    @classmethod
    def validate_price(cls, v):
        if v <= 0:
            raise ValueError('Price must be greater than 0')
        return round(v, 2)


class RoomCreate(RoomBase):
    hotel_id: int = Field(examples=[1], description="ID отеля, к которому относится номер")


class RoomResponse(RoomBase):
    id: int = Field(examples=[1], description="Уникальный идентификатор номера")
    hotel_id: int = Field(examples=[1], description="ID родительского отеля")
    is_available: bool = Field(examples=[True], description="Доступен ли номер для бронирования")
    hotel_name: Optional[str] = Field(default=None, examples=["Grand Hotel"], description="Название отеля")
    hotel_city: Optional[str] = Field(default=None, examples=["Moscow"], description="Город отеля")

    model_config = ConfigDict(from_attributes=True)


class HotelBookingBase(BaseModel):
    room_id: int = Field(examples=[1], description="ID бронируемого номера")
    check_in_date: str = Field(
        examples=["2024-01-15"],
        description="Дата заезда в формате YYYY-MM-DD"
    )
    check_out_date: str = Field(
        examples=["2024-01-20"],
        description="Дата выезда в формате YYYY-MM-DD"
    )
    guest_count: int = Field(
        default=1,
        ge=1,
        le=10,
        examples=[2],
        description="Количество гостей"
    )

    @field_validator('check_in_date', 'check_out_date')
    @classmethod
    def validate_date_format(cls, v):
        try:
            datetime.strptime(v, '%Y-%m-%d')
        except ValueError:
            raise ValueError('Date must be in YYYY-MM-DD format')
        return v


class HotelBookingCreate(HotelBookingBase):
    pass


class HotelBookingResponse(HotelBookingBase):
    id: int = Field(examples=[1], description="Уникальный идентификатор бронирования")
    user_id: int = Field(examples=[1], description="ID пользователя, создавшего бронь")
    total_price: float = Field(examples=[500.0], description="Общая стоимость бронирования")
    status: BookingStatus = Field(examples=["confirmed"], description="Текущий статус брони")
    created_at: str = Field(description="Дата и время создания брони")
    room_number: Optional[str] = Field(default=None, examples=["101"], description="Номер комнаты")
    hotel_name: Optional[str] = Field(default=None, examples=["Grand Hotel"], description="Название отеля")
    nights_count: Optional[int] = Field(default=None, examples=[5], description="Количество ночей")

    model_config = ConfigDict(from_attributes=True)


class FlightBase(BaseModel):
    flight_number: str = Field(
        examples=["SU100"],
        description="Уникальный номер рейса авиакомпании"
    )
    airline: str = Field(
        examples=["Aeroflot"],
        description="Название авиакомпании"
    )
    departure_city: str = Field(
        examples=["Moscow"],
        description="Город вылета"
    )
    arrival_city: str = Field(
        examples=["Sochi"],
        description="Город прилета"
    )
    departure_time: str = Field(
        examples=["2024-01-15 08:00:00"],
        description="Время вылета в формате YYYY-MM-DD HH:MM:SS"
    )
    arrival_time: str = Field(
        examples=["2024-01-15 10:30:00"],
        description="Время прилета в формате YYYY-MM-DD HH:MM:SS"
    )
    price: float = Field(
        gt=0,
        examples=[120.0],
        description="Базовая стоимость билета"
    )
    total_seats: int = Field(
        ge=1,
        examples=[180],
        description="Общее количество мест в самолете"
    )
    available_seats: int = Field(
        ge=0,
        examples=[150],
        description="Количество доступных для бронирования мест"
    )

    @field_validator('departure_time', 'arrival_time')
    @classmethod
    def validate_datetime_format(cls, v):
        try:
            datetime.strptime(v, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            raise ValueError('DateTime must be in YYYY-MM-DD HH:MM:SS format')
        return v

    @field_validator('available_seats')
    @classmethod
    def validate_available_seats(cls, v, info):
        if 'total_seats' in info.data and v > info.data['total_seats']:
            raise ValueError('Available seats cannot exceed total seats')
        return v


class FlightResponse(FlightBase):
    id: int = Field(examples=[1], description="Уникальный идентификатор рейса")
    is_active: bool = Field(examples=[True], description="Активен ли рейс для бронирования")
    created_at: str = Field(description="Дата и время создания записи")
    duration_minutes: Optional[int] = Field(default=None, examples=[150],
                                            description="Продолжительность полета в минутах")

    model_config = ConfigDict(from_attributes=True)


class FlightRouteResponse(BaseModel):
    segments: List[FlightResponse] = Field(description="Список сегментов маршрута")
    total_price: float = Field(examples=[240.0], description="Общая стоимость маршрута")
    total_duration_minutes: int = Field(examples=[150], description="Общая продолжительность в минутах")
    is_cheapest: bool = Field(default=False, description="Является ли самым дешевым вариантом")
    is_fastest: bool = Field(default=False, description="Является ли самым быстрым вариантом")
    connection_cities: List[str] = Field(default_factory=list, description="Города пересадок")
    layover_minutes: Optional[int] = Field(default=None, examples=[120], description="Общее время пересадок в минутах")
    stops_count: int = Field(default=0, description="Количество пересадок")


class FlightBookingCreate(BaseModel):
    flight_id: int = Field(examples=[1], description="ID рейса для бронирования")
    passenger_count: int = Field(
        default=1,
        ge=1,
        le=10,
        examples=[2],
        description="Количество пассажиров"
    )


class FlightBookingResponse(BaseModel):
    id: int = Field(examples=[1], description="Уникальный идентификатор бронирования")
    user_id: int = Field(examples=[1], description="ID пользователя")
    flight_id: int = Field(examples=[1], description="ID забронированного рейса")
    passenger_count: int = Field(examples=[2], description="Количество пассажиров")
    total_price: float = Field(examples=[240.0], description="Общая стоимость")
    status: BookingStatus = Field(examples=["confirmed"], description="Статус бронирования")
    booking_reference: str = Field(examples=["FL00010001094530"], description="Уникальный номер брони")
    created_at: str = Field(description="Дата и время создания брони")
    flight_number: Optional[str] = Field(default=None, examples=["SU100"], description="Номер рейса")
    departure_city: Optional[str] = Field(default=None, examples=["Moscow"], description="Город вылета")
    arrival_city: Optional[str] = Field(default=None, examples=["Sochi"], description="Город прилета")

    model_config = ConfigDict(from_attributes=True)


# Утилитарные схемы
class SearchResponse(BaseModel):
    success: bool = Field(examples=[True], description="Флаг успешности выполнения запроса")
    message: str = Field(examples=["Found 5 hotels"], description="Пояснительное сообщение")
    data: Optional[Any] = Field(default=None, description="Основные данные ответа")
    total: Optional[int] = Field(default=0, examples=[5], description="Общее количество найденных элементов")
    page: Optional[int] = Field(default=1, examples=[1], description="Текущая страница (для пагинации)")
    pages: Optional[int] = Field(default=1, examples=[1], description="Общее количество страниц")


class ErrorResponse(BaseModel):
    success: bool = Field(default=False, description="Флаг неуспешности операции")
    error: str = Field(examples=["Not Found"], description="Тип ошибки")
    details: Optional[str] = Field(default=None, examples=["The requested resource was not found"],
                                   description="Детальное описание ошибки")
    error_code: Optional[str] = Field(default=None, examples=["RESOURCE_NOT_FOUND"],
                                      description="Код ошибки для обработки")


class HealthCheckResponse(BaseModel):
    status: str = Field(examples=["healthy"], description="Общий статус системы")
    timestamp: str = Field(description="Время проверки")
    database: str = Field(examples=["connected"], description="Статус подключения к БД")
    version: str = Field(examples=["2.1.0"], description="Версия приложения")


class SystemStatusResponse(BaseModel):
    status: str = Field(examples=["running"], description="Статус работы системы")
    timestamp: str = Field(description="Время формирования отчета")
    database_stats: dict = Field(default_factory=dict, description="Статистика по таблицам БД")
    endpoints_available: int = Field(examples=[6], description="Количество доступных endpoints")
    memory_usage: str = Field(examples=["normal"], description="Использование памяти")


# Схемы для фильтрации
class HotelFilter(BaseModel):
    city: Optional[str] = Field(default=None, description="Фильтр по городу")
    stars: Optional[int] = Field(default=None, ge=1, le=5, description="Фильтр по количеству звезд")
    sort_by_stars: bool = Field(default=False, description="Сортировка по рейтингу")


class RoomFilter(BaseModel):
    hotel_id: Optional[int] = Field(default=None, description="Фильтр по ID отеля")
    room_type: Optional[RoomType] = Field(default=None, description="Фильтр по типу номера")
    min_price: Optional[float] = Field(default=None, ge=0, description="Минимальная цена")
    max_price: Optional[float] = Field(default=None, ge=0, description="Максимальная цена")
    min_capacity: Optional[int] = Field(default=None, ge=1, description="Минимальная вместимость")
    sort_by_price: bool = Field(default=False, description="Сортировка по цене")


class FlightSearch(BaseModel):
    departure_city: str = Field(description="Город вылета")
    arrival_city: str = Field(description="Город прилета")
    departure_date: str = Field(description="Дата вылета (YYYY-MM-DD)")
    passenger_count: int = Field(default=1, ge=1, description="Количество пассажиров")
    via_city: Optional[str] = Field(default=None, description="Поиск через определенный город")