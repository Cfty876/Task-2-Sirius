# bookings.py
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from datetime import datetime, timedelta
from database import get_db_connection
from models import HotelBookingCreate, HotelBookingResponse, FlightBookingCreate, FlightBookingResponse, SearchResponse
from auth import get_current_user, get_current_admin

router = APIRouter()


def parse_iso_date(date_str: str) -> datetime:
    """Безопасный парсинг ISO дат"""
    try:
        # Убираем timezone для упрощения
        clean_date = date_str.rstrip('Z').replace('+00:00', '')
        return datetime.fromisoformat(clean_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {date_str}")


# Utility functions
def calculate_booking_days(check_in: str, check_out: str) -> int:
    """Calculate number of days between check-in and check-out"""
    try:
        check_in_dt = parse_iso_date(check_in)
        check_out_dt = parse_iso_date(check_out)
        return (check_out_dt - check_in_dt).days
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")


def validate_dates(check_in: str, check_out: str):
    """Validate that check-in is before check-out and not in the past"""
    try:
        check_in_dt = parse_iso_date(check_in)
        check_out_dt = parse_iso_date(check_out)
        now = datetime.now()

        if check_in_dt.date() < now.date():
            raise HTTPException(status_code=400, detail="Check-in date cannot be in the past")
        if check_out_dt <= check_in_dt:
            raise HTTPException(status_code=400, detail="Check-out date must be after check-in date")
        if (check_out_dt - check_in_dt).days > 30:
            raise HTTPException(status_code=400, detail="Maximum booking duration is 30 days")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")


@router.get("/rooms/available-by-dates", response_model=SearchResponse)
async def get_available_rooms_by_dates(
        check_in: str = Query(..., description="Check-in date (YYYY-MM-DD)"),
        check_out: str = Query(..., description="Check-out date (YYYY-MM-DD)"),
        hotel_id: Optional[int] = Query(None, description="Filter by hotel ID"),
        city: Optional[str] = Query(None, description="Filter by city")
):
    # Validate dates
    validate_dates(check_in, check_out)

    conn = get_db_connection()

    query = """
    SELECT r.*, h.name as hotel_name, h.city as hotel_city 
    FROM rooms r 
    JOIN hotels h ON r.hotel_id = h.id 
    WHERE r.is_available = 1
    AND r.id NOT IN (
        SELECT room_id FROM hotel_bookings 
        WHERE status IN ('pending', 'confirmed')
        AND check_in_date < ? AND check_out_date > ?
    )
    """
    params = [check_out, check_in]

    if hotel_id:
        query += " AND r.hotel_id = ?"
        params.append(hotel_id)
    if city:
        query += " AND LOWER(h.city) LIKE LOWER(?)"
        params.append(f"%{city}%")

    query += " ORDER BY r.price_per_night ASC"

    available_rooms = conn.execute(query, params).fetchall()
    conn.close()

    return SearchResponse(
        success=True,
        message=f"Found {len(available_rooms)} available rooms for the selected dates",
        data=[dict(room) for room in available_rooms],
        total=len(available_rooms)
    )


@router.get("/rooms/available-by-duration", response_model=SearchResponse)
async def get_available_rooms_by_duration(
        start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
        duration_days: int = Query(..., ge=1, le=30, description="Duration in days (1-30)"),
        hotel_id: Optional[int] = Query(None, description="Filter by hotel ID")
):
    # Calculate check_out date
    try:
        start_dt = parse_iso_date(start_date)
        check_out = (start_dt + timedelta(days=duration_days)).strftime("%Y-%m-%d")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")

    validate_dates(start_date, check_out)

    conn = get_db_connection()

    query = """
    SELECT r.*, h.name as hotel_name, h.city as hotel_city 
    FROM rooms r 
    JOIN hotels h ON r.hotel_id = h.id 
    WHERE r.is_available = 1
    AND r.id NOT IN (
        SELECT room_id FROM hotel_bookings 
        WHERE status IN ('pending', 'confirmed')
        AND check_in_date < ? AND check_out_date > ?
    )
    """
    params = [check_out, start_date]

    if hotel_id:
        query += " AND r.hotel_id = ?"
        params.append(hotel_id)

    query += " ORDER BY r.price_per_night ASC"

    available_rooms = conn.execute(query, params).fetchall()
    conn.close()

    return SearchResponse(
        success=True,
        message=f"Found {len(available_rooms)} available rooms for {duration_days} days",
        data=[dict(room) for room in available_rooms],
        total=len(available_rooms)
    )


@router.post("/hotel", response_model=SearchResponse)
async def create_hotel_booking(
        booking: HotelBookingCreate,
        user: dict = Depends(get_current_user)
):
    # Validate dates
    validate_dates(booking.check_in_date, booking.check_out_date)

    conn = get_db_connection()

    # Check room availability and get room details
    room = conn.execute(
        "SELECT r.*, h.name as hotel_name FROM rooms r JOIN hotels h ON r.hotel_id = h.id WHERE r.id = ? AND r.is_available = 1",
        (booking.room_id,)
    ).fetchone()

    if not room:
        conn.close()
        raise HTTPException(status_code=404, detail="Room not found or not available")

    # Check guest count doesn't exceed room capacity
    if booking.guest_count > room["capacity"]:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail=f"Room capacity is {room['capacity']} guests, but {booking.guest_count} requested"
        )

    # Check if room is available for dates
    existing_booking = conn.execute(
        """SELECT * FROM hotel_bookings 
        WHERE room_id = ? AND status IN ('pending', 'confirmed')
        AND check_in_date < ? AND check_out_date > ?""",
        (booking.room_id, booking.check_out_date, booking.check_in_date)
    ).fetchone()

    if existing_booking:
        conn.close()
        raise HTTPException(status_code=400, detail="Room not available for selected dates")

    # Calculate total price
    nights = calculate_booking_days(booking.check_in_date, booking.check_out_date)
    total_price = room["price_per_night"] * nights

    # Create booking
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO hotel_bookings 
        (user_id, room_id, check_in_date, check_out_date, total_price, guest_count, status) 
        VALUES (?, ?, ?, ?, ?, ?, 'confirmed')""",
        (user["id"], booking.room_id, booking.check_in_date, booking.check_out_date, total_price, booking.guest_count)
    )
    booking_id = cursor.lastrowid
    conn.commit()

    # Get booking with details
    new_booking = conn.execute("""
        SELECT hb.*, r.room_number, h.name as hotel_name 
        FROM hotel_bookings hb
        JOIN rooms r ON hb.room_id = r.id
        JOIN hotels h ON r.hotel_id = h.id
        WHERE hb.id = ?
    """, (booking_id,)).fetchone()
    conn.close()

    return SearchResponse(
        success=True,
        message=f"Booking created successfully for {nights} nights. Total: ${total_price}",
        data=dict(new_booking)
    )


@router.get("/hotel", response_model=SearchResponse)
async def get_my_bookings(user: dict = Depends(get_current_user)):
    conn = get_db_connection()

    if user["role"] == "admin":
        bookings = conn.execute("""
            SELECT hb.*, r.room_number, h.name as hotel_name 
            FROM hotel_bookings hb
            JOIN rooms r ON hb.room_id = r.id
            JOIN hotels h ON r.hotel_id = h.id
            ORDER BY hb.created_at DESC
        """).fetchall()
    else:
        bookings = conn.execute(
            """
            SELECT hb.*, r.room_number, h.name as hotel_name 
            FROM hotel_bookings hb
            JOIN rooms r ON hb.room_id = r.id
            JOIN hotels h ON r.hotel_id = h.id
            WHERE hb.user_id = ?
            ORDER BY hb.created_at DESC
            """, (user["id"],)
        ).fetchall()

    conn.close()

    return SearchResponse(
        success=True,
        message=f"Found {len(bookings)} bookings",
        data=[dict(booking) for booking in bookings],
        total=len(bookings)
    )


@router.delete("/hotel/{booking_id}", response_model=SearchResponse)
async def cancel_booking(
        booking_id: int,
        user: dict = Depends(get_current_user)
):
    conn = get_db_connection()

    booking = conn.execute(
        "SELECT * FROM hotel_bookings WHERE id = ?", (booking_id,)
    ).fetchone()

    if not booking:
        conn.close()
        raise HTTPException(status_code=404, detail="Booking not found")

    # Check permissions - only admin can cancel any booking, users can only cancel their own
    if user["role"] != "admin" and booking["user_id"] != user["id"]:
        conn.close()
        raise HTTPException(status_code=403, detail="Not enough permissions")

    # Check if booking can be cancelled (not in the past)
    try:
        check_in_dt = parse_iso_date(booking["check_in_date"])
        if check_in_dt <= datetime.now():
            conn.close()
            raise HTTPException(status_code=400, detail="Cannot cancel past or ongoing booking")
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=f"Invalid check-in date format: {str(e)}")

    conn.execute(
        "UPDATE hotel_bookings SET status = 'cancelled' WHERE id = ?",
        (booking_id,)
    )
    conn.commit()
    conn.close()

    return SearchResponse(
        success=True,
        message="Booking cancelled successfully"
    )


@router.post("/flight", response_model=SearchResponse)
async def book_flight(
        booking: FlightBookingCreate,
        user: dict = Depends(get_current_user)
):
    conn = get_db_connection()

    # Check flight availability
    flight = conn.execute(
        "SELECT * FROM flights WHERE id = ? AND is_active = 1", (booking.flight_id,)
    ).fetchone()

    if not flight:
        conn.close()
        raise HTTPException(status_code=404, detail="Flight not found")

    if flight["available_seats"] < booking.passenger_count:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail=f"Only {flight['available_seats']} seats available, but {booking.passenger_count} requested"
        )

    total_price = flight["price"] * booking.passenger_count
    booking_reference = f"FL{flight['id']:04d}{user['id']:04d}{datetime.now().strftime('%H%M%S')}"

    # Create booking
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO flight_bookings 
        (user_id, flight_id, passenger_count, total_price, booking_reference, status)
        VALUES (?, ?, ?, ?, ?, 'confirmed')""",
        (user["id"], booking.flight_id, booking.passenger_count, total_price, booking_reference)
    )

    # Update available seats
    conn.execute(
        "UPDATE flights SET available_seats = available_seats - ? WHERE id = ?",
        (booking.passenger_count, booking.flight_id)
    )

    conn.commit()

    # Get booking with flight details
    new_booking = conn.execute("""
        SELECT fb.*, f.flight_number, f.departure_city, f.arrival_city 
        FROM flight_bookings fb
        JOIN flights f ON fb.flight_id = f.id
        WHERE fb.booking_reference = ?
    """, (booking_reference,)).fetchone()
    conn.close()

    return SearchResponse(
        success=True,
        message=f"Flight booked successfully! Reference: {booking_reference}",
        data=dict(new_booking)
    )


@router.get("/flight", response_model=SearchResponse)
async def get_my_flight_bookings(user: dict = Depends(get_current_user)):
    conn = get_db_connection()

    if user["role"] == "admin":
        bookings = conn.execute("""
            SELECT fb.*, f.flight_number, f.departure_city, f.arrival_city 
            FROM flight_bookings fb
            JOIN flights f ON fb.flight_id = f.id
            ORDER BY fb.created_at DESC
        """).fetchall()
    else:
        bookings = conn.execute(
            """
            SELECT fb.*, f.flight_number, f.departure_city, f.arrival_city 
            FROM flight_bookings fb
            JOIN flights f ON fb.flight_id = f.id
            WHERE fb.user_id = ?
            ORDER BY fb.created_at DESC
            """, (user["id"],)
        ).fetchall()

    conn.close()

    return SearchResponse(
        success=True,
        message=f"Found {len(bookings)} flight bookings",
        data=[dict(booking) for booking in bookings],
        total=len(bookings)
    )