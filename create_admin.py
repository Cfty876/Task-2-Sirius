# create_admin.py
import requests
import json

BASE_URL = "http://localhost:8000"


def create_admin_account():
    print("🔧 Creating admin account...")

    # Логинимся как существующий админ
    login_data = {
        "email": "admin@example.com",
        "password": "admin123"
    }

    login_response = requests.post(f"{BASE_URL}/auth/login", json=login_data)

    if login_response.status_code != 200:
        print("❌ Cannot login as admin")
        return

    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Создаем нового админа
    admin_data = {
        "email": "superadmin@example.com",
        "username": "superadmin",
        "password": "superadmin123",
        "role": "admin"
    }

    response = requests.post(f"{BASE_URL}/auth/register-admin", json=admin_data, headers=headers)
    print(f"Create admin status: {response.status_code}")
    print(f"Response: {response.text}")

    if response.status_code == 200:
        print("✅ Admin account created successfully!")
    else:
        print("❌ Failed to create admin account")


def promote_user_to_admin(user_id: int):
    print(f"🔧 Promoting user {user_id} to admin...")

    # Логинимся как существующий админ
    login_data = {
        "email": "admin@example.com",
        "password": "admin123"
    }

    login_response = requests.post(f"{BASE_URL}/auth/login", json=login_data)

    if login_response.status_code != 200:
        print("❌ Cannot login as admin")
        return

    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Повышаем пользователя до админа
    response = requests.put(f"{BASE_URL}/auth/promote-to-admin?target_user_id={user_id}", headers=headers)
    print(f"Promotion status: {response.status_code}")
    print(f"Response: {response.text}")

    if response.status_code == 200:
        print(f"✅ User {user_id} promoted to admin successfully!")
    else:
        print(f"❌ Failed to promote user {user_id}")


if __name__ == "__main__":
    # Создаем нового админа
    create_admin_account()

    # Повышаем существующего пользователя до админа (например, testuser1 с ID 3)
    promote_user_to_admin(3)