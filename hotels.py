from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from database import get_db_connection
from models import HotelBase, HotelResponse, RoomCreate, RoomResponse, SearchResponse, RoomType
from auth import get_current_admin, get_current_user

router = APIRouter()


@router.get("/", response_model=SearchResponse)
async def get_hotels(
        city: Optional[str] = Query(None, description="Filter by city"),
        stars: Optional[int] = Query(None, ge=1, le=5, description="Filter by star rating"),
        sort_by_stars: bool = Query(False, description="Sort by stars descending")
):
    conn = get_db_connection()
    query = """
    SELECT h.*, COUNT(r.id) as room_count 
    FROM hotels h 
    LEFT JOIN rooms r ON h.id = r.hotel_id AND r.is_available = 1
    WHERE 1=1
    """
    params = []

    if city:
        query += " AND LOWER(h.city) LIKE LOWER(?)"
        params.append(f"%{city}%")
    if stars:
        query += " AND h.stars = ?"
        params.append(stars)

    query += " GROUP BY h.id"

    if sort_by_stars:
        query += " ORDER BY h.stars DESC, h.name ASC"
    else:
        query += " ORDER BY h.name ASC"

    hotels = conn.execute(query, params).fetchall()
    conn.close()

    return SearchResponse(
        success=True,
        message=f"Found {len(hotels)} hotels",
        data=[dict(hotel) for hotel in hotels],
        total=len(hotels)
    )


@router.post("/", response_model=SearchResponse)
async def create_hotel(
        hotel: HotelBase,
        user: dict = Depends(get_current_admin)
):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO hotels (name, city, address, stars, description) VALUES (?, ?, ?, ?, ?)",
        (hotel.name, hotel.city, hotel.address, hotel.stars, hotel.description)
    )
    hotel_id = cursor.lastrowid
    conn.commit()

    new_hotel = conn.execute(
        "SELECT * FROM hotels WHERE id = ?", (hotel_id,)
    ).fetchone()
    conn.close()

    return SearchResponse(
        success=True,
        message="Hotel created successfully",
        data=dict(new_hotel)
    )


@router.put("/{hotel_id}", response_model=SearchResponse)
async def update_hotel(
        hotel_id: int,
        hotel: HotelBase,
        user: dict = Depends(get_current_admin)
):
    conn = get_db_connection()

    # Check if hotel exists
    existing_hotel = conn.execute("SELECT * FROM hotels WHERE id = ?", (hotel_id,)).fetchone()
    if not existing_hotel:
        conn.close()
        raise HTTPException(status_code=404, detail="Hotel not found")

    conn.execute(
        "UPDATE hotels SET name = ?, city = ?, address = ?, stars = ?, description = ? WHERE id = ?",
        (hotel.name, hotel.city, hotel.address, hotel.stars, hotel.description, hotel_id)
    )
    conn.commit()

    updated_hotel = conn.execute("SELECT * FROM hotels WHERE id = ?", (hotel_id,)).fetchone()
    conn.close()

    return SearchResponse(
        success=True,
        message="Hotel updated successfully",
        data=dict(updated_hotel)
    )


@router.delete("/{hotel_id}", response_model=SearchResponse)
async def delete_hotel(
        hotel_id: int,
        user: dict = Depends(get_current_admin)
):
    conn = get_db_connection()

    # Check if hotel exists
    existing_hotel = conn.execute("SELECT * FROM hotels WHERE id = ?", (hotel_id,)).fetchone()
    if not existing_hotel:
        conn.close()
        raise HTTPException(status_code=404, detail="Hotel not found")

    conn.execute("DELETE FROM hotels WHERE id = ?", (hotel_id,))
    conn.commit()
    conn.close()

    return SearchResponse(
        success=True,
        message="Hotel deleted successfully"
    )


@router.get("/rooms", response_model=SearchResponse)
async def get_rooms(
        hotel_id: Optional[int] = Query(None, description="Filter by hotel ID"),
        room_type: Optional[RoomType] = Query(None, description="Filter by room type"),
        min_price: Optional[float] = Query(None, ge=0, description="Minimum price per night"),
        max_price: Optional[float] = Query(None, ge=0, description="Maximum price per night"),
        min_capacity: Optional[int] = Query(None, ge=1, description="Minimum capacity"),
        sort_by_price: bool = Query(False, description="Sort by price ascending")
):
    conn = get_db_connection()
    query = """
    SELECT r.*, h.name as hotel_name, h.city as hotel_city 
    FROM rooms r 
    JOIN hotels h ON r.hotel_id = h.id 
    WHERE r.is_available = 1
    """
    params = []

    if hotel_id:
        query += " AND r.hotel_id = ?"
        params.append(hotel_id)
    if room_type:
        query += " AND r.room_type = ?"
        params.append(room_type.value)
    if min_price:
        query += " AND r.price_per_night >= ?"
        params.append(min_price)
    if max_price:
        query += " AND r.price_per_night <= ?"
        params.append(max_price)
    if min_capacity:
        query += " AND r.capacity >= ?"
        params.append(min_capacity)

    if sort_by_price:
        query += " ORDER BY r.price_per_night ASC"
    else:
        query += " ORDER BY r.hotel_id, r.room_number ASC"

    rooms = conn.execute(query, params).fetchall()
    conn.close()

    return SearchResponse(
        success=True,
        message=f"Found {len(rooms)} available rooms",
        data=[dict(room) for room in rooms],
        total=len(rooms)
    )


@router.post("/rooms", response_model=SearchResponse)
async def create_room(
        room: RoomCreate,
        user: dict = Depends(get_current_admin)
):
    # Check if hotel exists
    conn = get_db_connection()
    hotel = conn.execute("SELECT * FROM hotels WHERE id = ?", (room.hotel_id,)).fetchone()
    if not hotel:
        conn.close()
        raise HTTPException(status_code=404, detail="Hotel not found")

    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO rooms (hotel_id, room_number, room_type, price_per_night, capacity, room_count, features) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (room.hotel_id, room.room_number, room.room_type.value, room.price_per_night, room.capacity, room.room_count,
         room.features)
    )
    room_id = cursor.lastrowid
    conn.commit()

    new_room = conn.execute(
        "SELECT r.*, h.name as hotel_name, h.city as hotel_city FROM rooms r JOIN hotels h ON r.hotel_id = h.id WHERE r.id = ?",
        (room_id,)
    ).fetchone()
    conn.close()

    return SearchResponse(
        success=True,
        message="Room created successfully",
        data=dict(new_room)
    )


@router.put("/rooms/{room_id}", response_model=SearchResponse)
async def update_room(
        room_id: int,
        room: RoomCreate,
        user: dict = Depends(get_current_admin)
):
    conn = get_db_connection()

    # Check if room exists
    existing_room = conn.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
    if not existing_room:
        conn.close()
        raise HTTPException(status_code=404, detail="Room not found")

    conn.execute(
        "UPDATE rooms SET hotel_id = ?, room_number = ?, room_type = ?, price_per_night = ?, capacity = ?, room_count = ?, features = ? WHERE id = ?",
        (room.hotel_id, room.room_number, room.room_type.value, room.price_per_night, room.capacity, room.room_count,
         room.features, room_id)
    )
    conn.commit()

    updated_room = conn.execute(
        "SELECT r.*, h.name as hotel_name, h.city as hotel_city FROM rooms r JOIN hotels h ON r.hotel_id = h.id WHERE r.id = ?",
        (room_id,)
    ).fetchone()
    conn.close()

    return SearchResponse(
        success=True,
        message="Room updated successfully",
        data=dict(updated_room)
    )


@router.delete("/rooms/{room_id}", response_model=SearchResponse)
async def delete_room(
        room_id: int,
        user: dict = Depends(get_current_admin)
):
    conn = get_db_connection()

    # Check if room exists
    existing_room = conn.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
    if not existing_room:
        conn.close()
        raise HTTPException(status_code=404, detail="Room not found")

    conn.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
    conn.commit()
    conn.close()

    return SearchResponse(
        success=True,
        message="Room deleted successfully"
    )