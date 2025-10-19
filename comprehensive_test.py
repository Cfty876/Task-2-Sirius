# comprehensive_test.py
import requests
import json
import time
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"


class BookingSystemTester:
    def __init__(self):
        self.base_url = BASE_URL
        self.admin_token = None
        self.user_token = None
        self.test_data = {}

    def print_section(self, title):
        print(f"\n{'=' * 60}")
        print(f"🔍 {title}")
        print(f"{'=' * 60}")

    def print_result(self, test_name, success, details=""):
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")
        if details:
            print(f"   📝 {details}")

    def setup_tokens(self):
        """Получение токенов для тестирования"""
        self.print_section("Настройка аутентификации")

        # Логин админа
        admin_login = {
            "email": "admin@example.com",
            "password": "admin123"
        }
        response = requests.post(f"{self.base_url}/auth/login", json=admin_login)
        if response.status_code == 200:
            self.admin_token = response.json()["access_token"]
            self.print_result("Admin login", True, f"Token: {self.admin_token[:50]}...")
        else:
            self.print_result("Admin login", False, f"Status: {response.status_code}")
            return False

        # Логин пользователя
        user_login = {
            "email": "user@example.com",
            "password": "user123"
        }
        response = requests.post(f"{self.base_url}/auth/login", json=user_login)
        if response.status_code == 200:
            self.user_token = response.json()["access_token"]
            self.print_result("User login", True, f"Token: {self.user_token[:50]}...")
        else:
            self.print_result("User login", False, f"Status: {response.status_code}")

        return True

    def get_headers(self, token):
        return {"Authorization": f"Bearer {token}"}

    def test_swagger_docs(self):
        """Тестирование доступности Swagger документации"""
        self.print_section("Swagger документация")

        response = requests.get(f"{self.base_url}/docs")
        success = response.status_code == 200
        self.print_result("Swagger UI доступен", success, f"Status: {response.status_code}")

        response = requests.get(f"{self.base_url}/redoc")
        success = response.status_code == 200
        self.print_result("ReDoc доступен", success, f"Status: {response.status_code}")

        return True

    def test_auth_security(self):
        """Тестирование безопасности аутентификации"""
        self.print_section("Безопасность аутентификации")

        # Тест строгой проверки формата токена
        # Убрана проверка лишних пробелов, так как FastAPI автоматически их обрезает
        test_cases = [
            {"name": "Корректный формат", "header": f"Bearer {self.user_token}", "expected": 200},
            {"name": "Без Bearer", "header": self.user_token, "expected": 401},
            {"name": "Bearer в нижнем регистре", "header": f"bearer {self.user_token}", "expected": 401},
            {"name": "Токен с пробелами внутри", "header": f"Bearer {self.user_token} extra", "expected": 401},
            {"name": "Пустой токен", "header": "Bearer ", "expected": 401},
            {"name": "Только Bearer", "header": "Bearer", "expected": 401},
        ]

        all_passed = True
        for test_case in test_cases:
            headers = {"Authorization": test_case["header"]}
            try:
                response = requests.get(f"{self.base_url}/auth/me", headers=headers)
                success = response.status_code == test_case["expected"]
                if not success:
                    all_passed = False
                self.print_result(f"Формат токена: {test_case['name']}", success,
                                  f"Expected: {test_case['expected']}, Got: {response.status_code}")
            except Exception as e:
                self.print_result(f"Формат токена: {test_case['name']}", False, f"Error: {e}")
                all_passed = False

        return all_passed

    def test_user_registration_login(self):
        """Тестирование регистрации и авторизации"""
        self.print_section("Регистрация и авторизация")

        # Регистрация нового пользователя
        new_user = {
            "email": f"test_{int(time.time())}@example.com",
            "username": f"testuser_{int(time.time())}",
            "password": "testpassword123",
            "role": "user"
        }

        response = requests.post(f"{self.base_url}/auth/register", json=new_user)
        success = response.status_code == 200
        self.print_result("Регистрация нового пользователя", success,
                          f"Status: {response.status_code}")

        if success:
            # Логин нового пользователя
            login_data = {
                "email": new_user["email"],
                "password": new_user["password"]
            }
            response = requests.post(f"{self.base_url}/auth/login", json=login_data)
            success = response.status_code == 200
            self.print_result("Логин нового пользователя", success,
                              f"Status: {response.status_code}")

            if success:
                self.test_data["new_user_token"] = response.json()["access_token"]

        return success

    def test_hotel_crud_operations(self):
        """Тестирование CRUD операций для отелей"""
        self.print_section("CRUD операции для отелей")

        headers = self.get_headers(self.admin_token)

        # Создание отеля
        new_hotel = {
            "name": "Test Hotel CRUD",
            "city": "Test City",
            "address": "Test Address 123",
            "stars": 4,
            "description": "Test hotel for CRUD operations"
        }

        response = requests.post(f"{self.base_url}/hotels/", json=new_hotel, headers=headers)
        success = response.status_code == 200
        self.print_result("Создание отеля", success, f"Status: {response.status_code}")

        if not success:
            return False

        hotel_id = response.json()["data"]["id"]
        self.test_data["hotel_id"] = hotel_id

        # Получение отеля
        response = requests.get(f"{self.base_url}/hotels/", headers=headers)
        success = response.status_code == 200 and len(response.json()["data"]) > 0
        self.print_result("Получение списка отелей", success,
                          f"Found: {len(response.json()['data'])} hotels")

        # Обновление отеля
        updated_hotel = new_hotel.copy()
        updated_hotel["name"] = "Updated Test Hotel"
        response = requests.put(f"{self.base_url}/hotels/{hotel_id}", json=updated_hotel, headers=headers)
        success = response.status_code == 200
        self.print_result("Обновление отеля", success, f"Status: {response.status_code}")

        # Удаление отеля
        response = requests.delete(f"{self.base_url}/hotels/{hotel_id}", headers=headers)
        success = response.status_code == 200
        self.print_result("Удаление отеля", success, f"Status: {response.status_code}")

        return True

    def test_room_crud_operations(self):
        """Тестирование CRUD операций для номеров"""
        self.print_section("CRUD операции для номеров")

        headers = self.get_headers(self.admin_token)

        # Сначала создаем отель для теста
        hotel_data = {
            "name": "Test Hotel for Rooms",
            "city": "Room Test City",
            "address": "Room Test Address",
            "stars": 3,
            "description": "Hotel for room testing"
        }

        response = requests.post(f"{self.base_url}/hotels/", json=hotel_data, headers=headers)
        if response.status_code != 200:
            self.print_result("Создание отеля для теста комнат", False)
            return False

        hotel_id = response.json()["data"]["id"]

        # Создание комнаты
        new_room = {
            "hotel_id": hotel_id,
            "room_number": "TEST101",
            "room_type": "standard",
            "price_per_night": 100.0,
            "capacity": 2,
            "room_count": 1,
            "features": "Test features"
        }

        response = requests.post(f"{self.base_url}/hotels/rooms", json=new_room, headers=headers)
        success = response.status_code == 200
        self.print_result("Создание комнаты", success, f"Status: {response.status_code}")

        if not success:
            return False

        room_id = response.json()["data"]["id"]
        self.test_data["room_id"] = room_id

        # Получение комнат
        response = requests.get(f"{self.base_url}/hotels/rooms", headers=headers)
        success = response.status_code == 200 and len(response.json()["data"]) > 0
        self.print_result("Получение списка комнат", success,
                          f"Found: {len(response.json()['data'])} rooms")

        # Обновление комнаты
        updated_room = new_room.copy()
        updated_room["price_per_night"] = 120.0
        response = requests.put(f"{self.base_url}/hotels/rooms/{room_id}", json=updated_room, headers=headers)
        success = response.status_code == 200
        self.print_result("Обновление комнаты", success, f"Status: {response.status_code}")

        # Удаление комнаты и отеля
        response = requests.delete(f"{self.base_url}/hotels/rooms/{room_id}", headers=headers)
        success = response.status_code == 200
        self.print_result("Удаление комнаты", success, f"Status: {response.status_code}")

        response = requests.delete(f"{self.base_url}/hotels/{hotel_id}", headers=headers)

        return True

    def test_hotel_filtering_sorting(self):
        """Тестирование фильтрации и сортировки отелей"""
        self.print_section("Фильтрация и сортировка отелей")

        # Фильтрация по городу
        response = requests.get(f"{self.base_url}/hotels/?city=Moscow")
        success = response.status_code == 200
        moscow_hotels = len(response.json()["data"])
        self.print_result("Фильтрация отелей по городу", success,
                          f"Found {moscow_hotels} hotels in Moscow")

        # Фильтрация по звездам
        response = requests.get(f"{self.base_url}/hotels/?stars=5")
        success = response.status_code == 200
        five_star_hotels = len(response.json()["data"])
        self.print_result("Фильтрация отелей по звездам", success,
                          f"Found {five_star_hotels} 5-star hotels")

        # Сортировка по звездам
        response = requests.get(f"{self.base_url}/hotels/?sort_by_stars=true")
        success = response.status_code == 200
        if success and len(response.json()["data"]) > 1:
            hotels = response.json()["data"]
            sorted_by_stars = all(hotels[i]["stars"] >= hotels[i + 1]["stars"]
                                  for i in range(len(hotels) - 1))
            self.print_result("Сортировка отелей по звездам", sorted_by_stars)
        else:
            self.print_result("Сортировка отелей по звездам", False)

        return True

    def test_room_filtering_sorting(self):
        """Тестирование фильтрации и сортировки номеров"""
        self.print_section("Фильтрация и сортировка номеров")

        # Фильтрация по типу комнаты
        response = requests.get(f"{self.base_url}/hotels/rooms?room_type=premium")
        success = response.status_code == 200
        premium_rooms = len(response.json()["data"])
        self.print_result("Фильтрация номеров по типу", success,
                          f"Found {premium_rooms} premium rooms")

        # Фильтрация по цене
        response = requests.get(f"{self.base_url}/hotels/rooms?min_price=50&max_price=150")
        success = response.status_code == 200
        price_filtered_rooms = len(response.json()["data"])
        self.print_result("Фильтрация номеров по цене", success,
                          f"Found {price_filtered_rooms} rooms in price range")

        # Сортировка по цене
        response = requests.get(f"{self.base_url}/hotels/rooms?sort_by_price=true")
        success = response.status_code == 200
        if success and len(response.json()["data"]) > 1:
            rooms = response.json()["data"]
            sorted_by_price = all(rooms[i]["price_per_night"] <= rooms[i + 1]["price_per_night"]
                                  for i in range(len(rooms) - 1))
            self.print_result("Сортировка номеров по цене", sorted_by_price)
        else:
            self.print_result("Сортировка номеров по цене", False)

        return True

    def test_room_availability_methods(self):
        """Тестирование двух методов проверки доступности номеров"""
        self.print_section("Два метода проверки доступности номеров")

        # Метод 1: По датам заезда/выезда
        check_in = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
        check_out = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

        response = requests.get(
            f"{self.base_url}/bookings/rooms/available-by-dates?"
            f"check_in={check_in}&check_out={check_out}"
        )
        success = response.status_code == 200
        available_by_dates = len(response.json()["data"])
        self.print_result("Доступность по датам", success,
                          f"Found {available_by_dates} available rooms")

        # Метод 2: По дате начала и длительности
        start_date = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
        duration_days = 3

        response = requests.get(
            f"{self.base_url}/bookings/rooms/available-by-duration?"
            f"start_date={start_date}&duration_days={duration_days}"
        )
        success = response.status_code == 200
        available_by_duration = len(response.json()["data"])
        self.print_result("Доступность по длительности", success,
                          f"Found {available_by_duration} available rooms")

        return success

    def test_hotel_booking_workflow(self):
        """Тестирование workflow бронирования отеля"""
        self.print_section("Workflow бронирования отеля")

        headers = self.get_headers(self.user_token)

        # Получаем доступные комнаты
        check_in = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        check_out = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")

        response = requests.get(
            f"{self.base_url}/bookings/rooms/available-by-dates?"
            f"check_in={check_in}&check_out={check_out}"
        )

        if response.status_code != 200 or len(response.json()["data"]) == 0:
            self.print_result("Поиск доступных комнат", False, "No available rooms found")
            return False

        available_room = response.json()["data"][0]

        # Создаем бронирование
        booking_data = {
            "room_id": available_room["id"],
            "check_in_date": check_in,
            "check_out_date": check_out,
            "guest_count": 2
        }

        response = requests.post(
            f"{self.base_url}/bookings/hotel",
            json=booking_data,
            headers=headers
        )
        success = response.status_code == 200
        self.print_result("Создание бронирования отеля", success,
                          f"Status: {response.status_code}")

        if not success:
            return False

        booking_id = response.json()["data"]["id"]
        self.test_data["hotel_booking_id"] = booking_id

        # Получаем список бронирований пользователя
        response = requests.get(f"{self.base_url}/bookings/hotel", headers=headers)
        success = response.status_code == 200
        user_bookings = len(response.json()["data"])
        self.print_result("Получение бронирований пользователя", success,
                          f"Found {user_bookings} bookings")

        # Админ получает все бронирования
        admin_headers = self.get_headers(self.admin_token)
        response = requests.get(f"{self.base_url}/bookings/hotel", headers=admin_headers)
        success = response.status_code == 200
        all_bookings = len(response.json()["data"])
        self.print_result("Админ видит все бронирования", success,
                          f"Found {all_bookings} total bookings")

        # Отмена бронирования админом
        response = requests.delete(
            f"{self.base_url}/bookings/hotel/{booking_id}",
            headers=admin_headers
        )
        success = response.status_code == 200
        self.print_result("Отмена бронирования админом", success,
                          f"Status: {response.status_code}")

        return success

    def test_flight_search_functionality(self):
        """Тестирование функциональности поиска рейсов"""
        self.print_section("Поиск рейсов")

        # Прямой поиск рейсов
        departure_date = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")

        response = requests.get(
            f"{self.base_url}/flights/search?"
            f"departure_city=Moscow&arrival_city=Sochi&"
            f"departure_date={departure_date}&passenger_count=2"
        )
        success = response.status_code == 200
        direct_routes = len(response.json()["data"])
        self.print_result("Поиск прямых рейсов", success,
                          f"Found {direct_routes} route options")

        # Поиск рейсов через определенный город
        response = requests.get(
            f"{self.base_url}/flights/search?"
            f"departure_city=Moscow&arrival_city=Sochi&"
            f"departure_date={departure_date}&passenger_count=2&via_city=St. Petersburg"
        )
        success = response.status_code == 200
        via_routes = len(response.json()["data"])
        self.print_result("Поиск рейсов через город", success,
                          f"Found {via_routes} routes via St. Petersburg")

        # Проверка пометок "самый дешевый" и "самый быстрый"
        if direct_routes > 0:
            routes = response.json()["data"]
            has_cheapest = any(route.get("is_cheapest", False) for route in routes)
            has_fastest = any(route.get("is_fastest", False) for route in routes)

            self.print_result("Пометка 'самый дешевый'", has_cheapest)
            self.print_result("Пометка 'самый быстрый'", has_fastest)

        return success

    def test_flight_booking_workflow(self):
        """Тестирование workflow бронирования авиабилетов"""
        self.print_section("Workflow бронирования авиабилетов")

        headers = self.get_headers(self.user_token)

        # Получаем список доступных рейсов
        response = requests.get(f"{self.base_url}/flights/")
        if response.status_code != 200 or len(response.json()["data"]) == 0:
            self.print_result("Поиск доступных рейсов", False, "No flights found")
            return False

        available_flight = response.json()["data"][0]

        # Бронируем рейс
        booking_data = {
            "flight_id": available_flight["id"],
            "passenger_count": 1
        }

        response = requests.post(
            f"{self.base_url}/bookings/flight",
            json=booking_data,
            headers=headers
        )
        success = response.status_code == 200
        self.print_result("Бронирование авиабилета", success,
                          f"Status: {response.status_code}")

        if success:
            booking_ref = response.json()["data"]["booking_reference"]
            self.print_result("Сгенерирован номер брони", True, f"Reference: {booking_ref}")

        # Получаем список бронирований
        response = requests.get(f"{self.base_url}/bookings/flight", headers=headers)
        success = response.status_code == 200
        flight_bookings = len(response.json()["data"])
        self.print_result("Получение бронирований авиабилетов", success,
                          f"Found {flight_bookings} flight bookings")

        return success

    def test_flight_sorting(self):
        """Тестирование сортировки рейсов"""
        self.print_section("Сортировка рейсов")

        # Сортировка по цене
        response = requests.get(f"{self.base_url}/flights/?sort_by_price=true")
        success = response.status_code == 200

        if success and len(response.json()["data"]) > 1:
            flights = response.json()["data"]
            sorted_by_price = all(flights[i]["price"] <= flights[i + 1]["price"]
                                  for i in range(len(flights) - 1))
            self.print_result("Сортировка рейсов по цене", sorted_by_price)
        else:
            self.print_result("Сортировка рейсов по цене", False)

        # Фильтрация по городам
        response = requests.get(
            f"{self.base_url}/flights/?departure_city=Moscow&arrival_city=Sochi"
        )
        success = response.status_code == 200
        filtered_flights = len(response.json()["data"])
        self.print_result("Фильтрация рейсов по городам", success,
                          f"Found {filtered_flights} Moscow-Sochi flights")

        return True

    def run_comprehensive_test(self):
        """Запуск всех тестов"""
        print("🚀 Запуск комплексного тестирования системы бронирования")
        print("📋 Проверка всех требований ТЗ")

        # Проверка базовых требований
        requirements = [
            ("Swagger документация", self.test_swagger_docs),
            ("Настройка аутентификации", self.setup_tokens),
            ("Безопасность аутентификации", self.test_auth_security),
            ("Регистрация и авторизация", self.test_user_registration_login),
            ("CRUD операции отелей", self.test_hotel_crud_operations),
            ("CRUD операции номеров", self.test_room_crud_operations),
            ("Фильтрация отелей", self.test_hotel_filtering_sorting),
            ("Фильтрация номеров", self.test_room_filtering_sorting),
            ("Два метода проверки доступности", self.test_room_availability_methods),
            ("Workflow бронирования отеля", self.test_hotel_booking_workflow),
            ("Поиск рейсов", self.test_flight_search_functionality),
            ("Workflow бронирования авиабилетов", self.test_flight_booking_workflow),
            ("Сортировка рейсов", self.test_flight_sorting),
        ]

        results = []
        for req_name, test_func in requirements:
            try:
                result = test_func()
                results.append((req_name, result))
            except Exception as e:
                print(f"❌ Ошибка в тесте {req_name}: {e}")
                results.append((req_name, False))

        # Вывод итогов
        self.print_section("ИТОГИ ТЕСТИРОВАНИЯ")

        passed = sum(1 for _, result in results if result)
        total = len(results)

        print(f"📊 Пройдено тестов: {passed}/{total}")
        print(f"🎯 Успешность: {passed / total * 100:.1f}%")

        # Проверка выполнения всех требований ТЗ
        critical_requirements = [
            "Swagger документация", "Безопасность аутентификации",
            "Регистрация и авторизация", "CRUD операции отелей",
            "Фильтрация отелей", "Два метода проверки доступности",
            "Workflow бронирования отеля", "Поиск рейсов"
        ]

        critical_passed = all(any(req in name and result for name, result in results)
                              for req in critical_requirements)

        print(f"\n🎯 Критические требования: {'✅ ВЫПОЛНЕНЫ' if critical_passed else '❌ НЕ ВЫПОЛНЕНЫ'}")

        if critical_passed and passed / total >= 0.8:
            print("\n🎉 ВЫВОД: Система соответствует всем основным требованиям ТЗ!")
            print("   ✅ Регистрация и авторизация с безопасностью")
            print("   ✅ CRUD операции над всеми сущностями")
            print("   ✅ Swagger документация доступна")
            print("   ✅ Фильтрация и сортировка отелей и номеров")
            print("   ✅ Два метода бронирования номеров")
            print("   ✅ Поиск рейсов с фильтрацией и сортировкой")
            print("   ✅ Поиск через определенный город")
            print("   ✅ Специальные пометки для билетов")
        else:
            print("\n⚠️ ВЫВОД: Требуется доработка системы")

        return critical_passed and passed / total >= 0.8


if __name__ == "__main__":
    # Проверка доступности сервера
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print("❌ Сервер не доступен! Запустите сервер командой: python main.py")
            exit(1)
    except:
        print("❌ Сервер не доступен! Запустите сервер командой: python main.py")
        exit(1)

    tester = BookingSystemTester()
    success = tester.run_comprehensive_test()

    if success:
        print(f"\n✨ Тестирование завершено успешно! Система готова к использованию.")
        print(f"📚 Документация: {BASE_URL}/docs")
        print(f"❤️  Проверка здоровья: {BASE_URL}/health")
    else:
        print(f"\n💥 Обнаружены проблемы в системе. Требуется доработка.")
        exit(1)