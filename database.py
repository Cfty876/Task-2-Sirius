import sqlite3
import hashlib
import logging

logger = logging.getLogger(__name__)


def get_password_hash(password: str) -> str:
    """Хеширование пароля с солью для безопасности"""
    salt = "booking_system_salt_2024"
    return hashlib.sha256((password + salt).encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверка пароля"""
    return get_password_hash(plain_password) == hashed_password


def get_db_connection():
    """Создание подключения к базе данных с обработкой ошибок"""
    try:
        conn = sqlite3.connect('booking.db')
        conn.row_factory = sqlite3.Row
        # Включение foreign keys
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    except sqlite3.Error as e:
        logger.error(f"Database connection error: {e}")
        raise


def init_db():
    """Инициализация базы данных с тестовыми данными"""
    conn = sqlite3.connect('booking.db')
    cursor = conn.cursor()

    # Включение foreign keys
    cursor.execute("PRAGMA foreign_keys = ON")

    logger.info("Creating database tables...")

    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Hotels table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hotels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            city TEXT NOT NULL,
            address TEXT,
            stars INTEGER CHECK(stars >= 1 AND stars <= 5),
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Rooms table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hotel_id INTEGER NOT NULL,
            room_number TEXT NOT NULL,
            room_type TEXT DEFAULT 'standard',
            price_per_night REAL NOT NULL CHECK(price_per_night > 0),
            capacity INTEGER NOT NULL CHECK(capacity >= 1),
            room_count INTEGER DEFAULT 1 CHECK(room_count >= 1),
            is_available BOOLEAN DEFAULT TRUE,
            features TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (hotel_id) REFERENCES hotels (id) ON DELETE CASCADE
        )
    ''')

    # Hotel bookings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hotel_bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            room_id INTEGER NOT NULL,
            check_in_date TEXT NOT NULL,
            check_out_date TEXT NOT NULL,
            total_price REAL NOT NULL CHECK(total_price >= 0),
            status TEXT DEFAULT 'pending',
            guest_count INTEGER DEFAULT 1 CHECK(guest_count >= 1),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (room_id) REFERENCES rooms (id) ON DELETE CASCADE
        )
    ''')

    # Flights table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS flights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            flight_number TEXT NOT NULL,
            airline TEXT NOT NULL,
            departure_city TEXT NOT NULL,
            arrival_city TEXT NOT NULL,
            departure_time TEXT NOT NULL,
            arrival_time TEXT NOT NULL,
            price REAL NOT NULL CHECK(price > 0),
            total_seats INTEGER NOT NULL CHECK(total_seats > 0),
            available_seats INTEGER NOT NULL CHECK(available_seats >= 0),
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Flight bookings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS flight_bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            flight_id INTEGER NOT NULL,
            passenger_count INTEGER NOT NULL CHECK(passenger_count >= 1),
            total_price REAL NOT NULL CHECK(total_price >= 0),
            status TEXT DEFAULT 'pending',
            booking_reference TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (flight_id) REFERENCES flights (id) ON DELETE CASCADE
        )
    ''')

    # Проверяем, нужно ли добавлять тестовые данные
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]

    if user_count == 0:
        logger.info("Adding sample data...")

        # Создаем тестовых пользователей
        admin_password = get_password_hash("admin123")
        user_password = get_password_hash("user123")

        cursor.execute(
            "INSERT INTO users (email, username, hashed_password, role) VALUES (?, ?, ?, ?)",
            ("admin@example.com", "admin", admin_password, "admin")
        )
        cursor.execute(
            "INSERT INTO users (email, username, hashed_password, role) VALUES (?, ?, ?, ?)",
            ("user@example.com", "user", user_password, "user")
        )

        # Создаем тестовые отели
        hotels_data = [
            ('Grand Hotel Moscow', 'Moscow', 'Tverskaya st. 1', 5, 'Luxury hotel in city center'),
            ('Comfort Inn', 'Moscow', 'Arbat st. 25', 3, 'Comfortable budget hotel'),
            ('Seaside Resort', 'Sochi', 'Beach blvd. 10', 4, 'Beautiful resort by the sea'),
            ('Business Hotel SPB', 'St. Petersburg', 'Nevsky Prospect 50', 4, 'Hotel for business travelers')
        ]
        cursor.executemany(
            "INSERT INTO hotels (name, city, address, stars, description) VALUES (?, ?, ?, ?, ?)",
            hotels_data
        )

        # Создаем тестовые номера
        rooms_data = [
            (1, '101', 'premium', 200.0, 2, 1, 'Sea view, King bed'),
            (1, '102', 'standard', 120.0, 2, 1, 'City view, Queen bed'),
            (2, '201', 'standard', 80.0, 2, 1, 'Basic room with TV'),
            (2, '202', 'large', 120.0, 4, 2, 'Family room'),
            (3, '301', 'premium', 180.0, 2, 1, 'Beach front, Balcony'),
            (4, '401', 'premium', 150.0, 2, 1, 'Executive room')
        ]
        cursor.executemany(
            "INSERT INTO rooms (hotel_id, room_number, room_type, price_per_night, capacity, room_count, features) VALUES (?, ?, ?, ?, ?, ?, ?)",
            rooms_data
        )

        # Создаем тестовые рейсы
        flights_data = [
            ('SU100', 'Aeroflot', 'Moscow', 'Sochi', '2024-01-15 08:00:00', '2024-01-15 10:30:00', 120.0, 180, 150),
            ('SU200', 'Aeroflot', 'Moscow', 'Sochi', '2024-01-15 14:00:00', '2024-01-15 16:30:00', 150.0, 180, 120),
            ('SU150', 'Aeroflot', 'Moscow', 'St. Petersburg', '2024-01-15 09:00:00', '2024-01-15 10:00:00', 80.0, 180, 100),
            ('SU250', 'Aeroflot', 'St. Petersburg', 'Sochi', '2024-01-15 12:00:00', '2024-01-15 15:00:00', 100.0, 180, 80)
        ]
        cursor.executemany(
            "INSERT INTO flights (flight_number, airline, departure_city, arrival_city, departure_time, arrival_time, price, total_seats, available_seats) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            flights_data
        )

        logger.info("Sample data added successfully")

    conn.commit()
    conn.close()
    logger.info("Database initialization completed")