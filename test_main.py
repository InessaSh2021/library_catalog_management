import pytest
from fastapi.testclient import TestClient
from main import app, Book, Reader

client = TestClient(app)

# Подготовка тестовых данных
@pytest.fixture(autouse=True)
def setup_db():
    # Очистка баз данных перед каждым тестом
    app.users_db.clear()
    app.readers_db.clear()
    app.books_db.clear()
    app.borrowed_books_db.clear()

    # Добавляем тестовые книги
    book1 = Book(id=1, title="Book One", author="Author One", copies=2)
    book2 = Book(id=2, title="Book Two", author="Author Two", copies=0)
    app.books_db.append(book1)
    app.books_db.append(book2)

    # Добавляем тестового читателя
    reader = Reader(id=1, name="Reader One", email="reader@example.com")
    app.readers_db.append(reader)

    # Регистрация пользователя для тестов
    client.post("/register/", json={"username": "testuser", "email": "test@example.com"})

# Тест на успешное заимствование книги
def test_borrow_book_success():
    token_response = client.post("/token", data={"username": "testuser", "password": "default_password"})
    token = token_response.json()["access_token"]

    response = client.post("/borrow/", headers={"Authorization": f"Bearer {token}"}, json={"book_id": 1, "reader_id": 1})
    assert response.status_code == 200
    assert response.json() == {"detail": "Book borrowed successfully."}
    assert app.books_db[0].copies == 1  # Проверка, что количество копий уменьшилось

# Тест на попытку заимствования книги, которой нет в наличии
def test_borrow_book_not_available():
    token_response = client.post("/token", data={"username": "testuser", "password": "default_password"})
    token = token_response.json()["access_token"]

    response = client.post("/borrow/", headers={"Authorization": f"Bearer {token}"}, json={"book_id": 2, "reader_id": 1})
    assert response.status_code == 400
    assert response.json() == {"detail": "Book not available."}

# Тест на попытку заимствования более трех книг
def test_borrow_more_than_three_books():
    # Добавляем три книги и заимствуем их
    for i in range(3):
        app.borrowed_books_db.append({
            "id": i + 1,
            "book_id": 1,
            "reader_id": 1,
            "borrow_date": "2023-01-01T00:00:00",
            "return_date": None
        })

    token_response = client.post("/token", data={"username": "testuser", "password": "default_password"})
    token = token_response.json()["access_token"]

    response = client.post("/borrow/", headers={"Authorization": f"Bearer {token}"}, json={"book_id": 1, "reader_id": 1})
    assert response.status_code == 400
    assert response.json() == {"detail": "Reader cannot borrow more than 3 books."}

# Тест на доступ к защищенному эндпоинту без токена
def test_secure_endpoint_without_token():
    response = client.get("/readers/")
    assert response.status_code == 401  # Должен вернуть 401 Unauthorized

# Тест на доступ к защищенному эндпоинту с токеном
def test_secure_endpoint_with_token():
    token_response = client.post("/token", data={"username": "testuser", "password": "default_password"})
    token = token_response.json()["access_token"]

    response = client.get("/readers/", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == [{"id": 1, "name": "Reader One", "email": "reader@example.com"}]  # Проверка списка читателей
