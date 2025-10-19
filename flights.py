from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from datetime import datetime, timedelta
from database import get_db_connection
from models import FlightBase, FlightResponse, FlightRouteResponse, SearchResponse
from auth import get_current_admin, get_current_user

router = APIRouter()


@router.get("/search", response_model=SearchResponse)
async def search_flights(
        departure_city: str = Query(..., description="Departure city"),
        arrival_city: str = Query(..., description="Arrival city"),
        departure_date: str = Query(..., description="Departure date (YYYY-MM-DD)"),
        passenger_count: int = Query(1, ge=1, description="Number of passengers"),
        via_city: Optional[str] = Query(None, description="Search routes via specific city")
):
    conn = get_db_connection()

    routes = []

    # Direct flights
    direct_flights = conn.execute(
        """SELECT * FROM flights 
        WHERE LOWER(departure_city) = LOWER(?) AND LOWER(arrival_city) = LOWER(?)
        AND date(departure_time) = date(?)
        AND available_seats >= ?
        AND is_active = 1
        ORDER BY price ASC, departure_time ASC""",
        (departure_city, arrival_city, departure_date, passenger_count)
    ).fetchall()

    # Process direct flights
    for flight in direct_flights:
        flight_dict = dict(flight)
        departure_dt = datetime.fromisoformat(flight["departure_time"].replace('Z', '+00:00'))
        arrival_dt = datetime.fromisoformat(flight["arrival_time"].replace('Z', '+00:00'))
        duration = (arrival_dt - departure_dt).total_seconds() / 60

        routes.append(FlightRouteResponse(
            segments=[FlightResponse(**flight_dict)],
            total_price=flight["price"] * passenger_count,
            total_duration_minutes=int(duration),
            connection_cities=[]
        ))

    # Find connecting flights
    if via_city:
        # Search for routes via specific city
        connecting_flights = find_connecting_flights_via_city(
            conn, departure_city, arrival_city, departure_date, passenger_count, via_city
        )
    else:
        # Find all connecting flights
        connecting_flights = find_connecting_flights(
            conn, departure_city, arrival_city, departure_date, passenger_count
        )

    routes.extend(connecting_flights)

    # Mark fastest and cheapest
    if routes:
        cheapest_route = min(routes, key=lambda x: x.total_price)
        fastest_route = min(routes, key=lambda x: x.total_duration_minutes)

        for route in routes:
            if route.total_price == cheapest_route.total_price:
                route.is_cheapest = True
            if route.total_duration_minutes == fastest_route.total_duration_minutes:
                route.is_fastest = True

    # Sort routes by price
    routes.sort(key=lambda x: x.total_price)

    conn.close()

    return SearchResponse(
        success=True,
        message=f"Found {len(routes)} flight options",
        data=[route.dict() for route in routes],
        total=len(routes)
    )


def find_connecting_flights(conn, departure_city, arrival_city, departure_date, passenger_count):
    routes = []

    # Find possible connection points
    first_legs = conn.execute(
        """SELECT * FROM flights 
        WHERE LOWER(departure_city) = LOWER(?)
        AND date(departure_time) = date(?)
        AND available_seats >= ?
        AND is_active = 1
        ORDER BY departure_time ASC""",
        (departure_city, departure_date, passenger_count)
    ).fetchall()

    for first_flight in first_legs:
        connection_city = first_flight["arrival_city"]
        if connection_city.lower() == arrival_city.lower():
            continue  # Skip if first flight already arrives at destination

        # Find second leg with reasonable layover (1-24 hours)
        second_legs = conn.execute(
            """SELECT * FROM flights 
            WHERE LOWER(departure_city) = LOWER(?) AND LOWER(arrival_city) = LOWER(?)
            AND departure_time > ? 
            AND datetime(departure_time) <= datetime(?, '+24 hours')
            AND available_seats >= ?
            AND is_active = 1
            ORDER BY departure_time ASC""",
            (connection_city, arrival_city, first_flight["arrival_time"], first_flight["arrival_time"], passenger_count)
        ).fetchall()

        for second_flight in second_legs:
            first_departure = datetime.fromisoformat(first_flight["departure_time"].replace('Z', '+00:00'))
            first_arrival = datetime.fromisoformat(first_flight["arrival_time"].replace('Z', '+00:00'))
            second_departure = datetime.fromisoformat(second_flight["departure_time"].replace('Z', '+00:00'))
            second_arrival = datetime.fromisoformat(second_flight["arrival_time"].replace('Z', '+00:00'))

            layover = (second_departure - first_arrival).total_seconds() / 60
            total_duration = (second_arrival - first_departure).total_seconds() / 60
            total_price = (first_flight["price"] + second_flight["price"]) * passenger_count

            # Only include routes with reasonable layover (1-24 hours)
            if 60 <= layover <= 1440:  # 1 hour to 24 hours
                routes.append(FlightRouteResponse(
                    segments=[
                        FlightResponse(**dict(first_flight)),
                        FlightResponse(**dict(second_flight))
                    ],
                    total_price=total_price,
                    total_duration_minutes=int(total_duration),
                    connection_cities=[connection_city],
                    layover_minutes=int(layover)
                ))

    return routes


def find_connecting_flights_via_city(conn, departure_city, arrival_city, departure_date, passenger_count, via_city):
    routes = []

    # First leg to via city
    first_legs = conn.execute(
        """SELECT * FROM flights 
        WHERE LOWER(departure_city) = LOWER(?) AND LOWER(arrival_city) = LOWER(?)
        AND date(departure_time) = date(?)
        AND available_seats >= ?
        AND is_active = 1
        ORDER BY departure_time ASC""",
        (departure_city, via_city, departure_date, passenger_count)
    ).fetchall()

    for first_flight in first_legs:
        # Second leg from via city to destination
        second_legs = conn.execute(
            """SELECT * FROM flights 
            WHERE LOWER(departure_city) = LOWER(?) AND LOWER(arrival_city) = LOWER(?)
            AND departure_time > ? 
            AND datetime(departure_time) <= datetime(?, '+24 hours')
            AND available_seats >= ?
            AND is_active = 1
            ORDER BY departure_time ASC""",
            (via_city, arrival_city, first_flight["arrival_time"], first_flight["arrival_time"], passenger_count)
        ).fetchall()

        for second_flight in second_legs:
            first_departure = datetime.fromisoformat(first_flight["departure_time"].replace('Z', '+00:00'))
            first_arrival = datetime.fromisoformat(first_flight["arrival_time"].replace('Z', '+00:00'))
            second_departure = datetime.fromisoformat(second_flight["departure_time"].replace('Z', '+00:00'))
            second_arrival = datetime.fromisoformat(second_flight["arrival_time"].replace('Z', '+00:00'))

            layover = (second_departure - first_arrival).total_seconds() / 60
            total_duration = (second_arrival - first_departure).total_seconds() / 60
            total_price = (first_flight["price"] + second_flight["price"]) * passenger_count

            # Only include routes with reasonable layover (1-24 hours)
            if 60 <= layover <= 1440:
                routes.append(FlightRouteResponse(
                    segments=[
                        FlightResponse(**dict(first_flight)),
                        FlightResponse(**dict(second_flight))
                    ],
                    total_price=total_price,
                    total_duration_minutes=int(total_duration),
                    connection_cities=[via_city],
                    layover_minutes=int(layover)
                ))

    return routes


@router.get("/", response_model=SearchResponse)
async def get_flights(
        departure_city: Optional[str] = Query(None, description="Filter by departure city"),
        arrival_city: Optional[str] = Query(None, description="Filter by arrival city"),
        sort_by_price: bool = Query(False, description="Sort by price")
):
    conn = get_db_connection()
    query = "SELECT * FROM flights WHERE is_active = 1"
    params = []

    if departure_city:
        query += " AND LOWER(departure_city) LIKE LOWER(?)"
        params.append(f"%{departure_city}%")
    if arrival_city:
        query += " AND LOWER(arrival_city) LIKE LOWER(?)"
        params.append(f"%{arrival_city}%")

    if sort_by_price:
        query += " ORDER BY price ASC"
    else:
        query += " ORDER BY departure_time ASC"

    flights = conn.execute(query, params).fetchall()
    conn.close()

    return SearchResponse(
        success=True,
        message=f"Found {len(flights)} flights",
        data=[dict(flight) for flight in flights],
        total=len(flights)
    )


@router.post("/", response_model=SearchResponse)
async def create_flight(
        flight: FlightBase,
        user: dict = Depends(get_current_admin)
):
    # Validate flight times
    departure_dt = datetime.fromisoformat(flight.departure_time.replace('Z', '+00:00'))
    arrival_dt = datetime.fromisoformat(flight.arrival_time.replace('Z', '+00:00'))

    if arrival_dt <= departure_dt:
        raise HTTPException(status_code=400, detail="Arrival time must be after departure time")

    if flight.available_seats > flight.total_seats:
        raise HTTPException(status_code=400, detail="Available seats cannot exceed total seats")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO flights 
        (flight_number, airline, departure_city, arrival_city, departure_time, arrival_time, price, total_seats, available_seats)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (flight.flight_number, flight.airline, flight.departure_city, flight.arrival_city,
         flight.departure_time, flight.arrival_time, flight.price, flight.total_seats, flight.available_seats)
    )
    flight_id = cursor.lastrowid
    conn.commit()

    new_flight = conn.execute(
        "SELECT * FROM flights WHERE id = ?", (flight_id,)
    ).fetchone()
    conn.close()

    return SearchResponse(
        success=True,
        message="Flight created successfully",
        data=dict(new_flight)
    )


@router.put("/{flight_id}", response_model=SearchResponse)
async def update_flight(
        flight_id: int,
        flight: FlightBase,
        user: dict = Depends(get_current_admin)
):
    conn = get_db_connection()

    # Check if flight exists
    existing_flight = conn.execute("SELECT * FROM flights WHERE id = ?", (flight_id,)).fetchone()
    if not existing_flight:
        conn.close()
        raise HTTPException(status_code=404, detail="Flight not found")

    conn.execute(
        """UPDATE flights SET 
        flight_number = ?, airline = ?, departure_city = ?, arrival_city = ?, 
        departure_time = ?, arrival_time = ?, price = ?, total_seats = ?, available_seats = ?
        WHERE id = ?""",
        (flight.flight_number, flight.airline, flight.departure_city, flight.arrival_city,
         flight.departure_time, flight.arrival_time, flight.price, flight.total_seats, flight.available_seats,
         flight_id)
    )
    conn.commit()

    updated_flight = conn.execute("SELECT * FROM flights WHERE id = ?", (flight_id,)).fetchone()
    conn.close()

    return SearchResponse(
        success=True,
        message="Flight updated successfully",
        data=dict(updated_flight)
    )


@router.delete("/{flight_id}", response_model=SearchResponse)
async def delete_flight(
        flight_id: int,
        user: dict = Depends(get_current_admin)
):
    conn = get_db_connection()

    # Check if flight exists
    existing_flight = conn.execute("SELECT * FROM flights WHERE id = ?", (flight_id,)).fetchone()
    if not existing_flight:
        conn.close()
        raise HTTPException(status_code=404, detail="Flight not found")

    conn.execute("DELETE FROM flights WHERE id = ?", (flight_id,))
    conn.commit()
    conn.close()

    return SearchResponse(
        success=True,
        message="Flight deleted successfully"
    )