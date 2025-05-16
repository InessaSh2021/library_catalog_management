from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from mail import MailSender

# Конфигурация JWT
SECRET_KEY = "secret_key"  # секретный ключ
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Инициализация FastAPI
app = FastAPI(title="Library Catalog Management")

# Инициализация MailSender
mail_sender = MailSender(
    smtp_server="smtp.example.com",
    smtp_port=587,
    username="your_email@example.com",
    password="your_password"
)

# Модели
class User(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserInDB(User):
    hashed_password: str

class Reader(BaseModel):
    id: int
    name: str
    email: EmailStr

class Book(BaseModel):
    id: int
    title: str
    author: str
    year: Optional[int] = None
    isbn: Optional[str] = None
    copies: int = 1

class BorrowedBook(BaseModel):
    id: int
    book_id: int
    reader_id: int
    borrow_date: datetime
    return_date: Optional[datetime] = None

# Временные "базы данных"
users_db = {}
readers_db = []
books_db = []
borrowed_books_db = []

# Парольный контекст для хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 для защиты эндпоинтов
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Функции для работы с паролями
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

# Функции для работы с JWT
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return username

# Эндпоинты для управления пользователями
@app.post("/register/", response_model=User)
def register(user: User):
    if user.email in users_db:
        raise HTTPException(status_code=400, detail="Email already registered.")

    # Хеширование пароля из запроса
    hashed_password = get_password_hash(user.password)
    users_db[user.email] = UserInDB(**user.dict(), hashed_password=hashed_password)

    # Удаляем пароль перед возвратом
    del user.password

    # Отправка уведомления по электронной почте
    mail_sender.send_email(
        recipient=user.email,
        subject="Welcome to the Library",
        body="Thank you for registering!"
    )

    return user

@app.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = users_db.get(form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# Эндпоинты для управления читателями
@app.post("/readers/", response_model=Reader, dependencies=[Depends(get_current_user)])
def add_reader(reader: Reader):
    if any(r.email == reader.email for r in readers_db):
        raise HTTPException(status_code=400, detail="Email already registered.")
    reader.id = len(readers_db) + 1
    readers_db.append(reader)
    return reader

@app.get("/readers/", response_model=List[Reader], dependencies=[Depends(get_current_user)])
def get_readers():
    return readers_db

# Эндпоинты для управления книгами
@app.post("/books/", response_model=Book, dependencies=[Depends(get_current_user)])
def add_book(book: Book):
    if any(b.id == book.id for b in books_db):
        raise HTTPException(status_code=400, detail="Book with this ID already exists.")
    books_db.append(book)
    return book

@app.get("/books/", response_model=List[Book], dependencies=[Depends(get_current_user)])
def get_books():
    return books_db

# Эндпоинты для выдачи и возврата книг
@app.post("/borrow/", dependencies=[Depends(get_current_user)])
def borrow_book(book_id: int, reader_id: int):
    book = next((b for b in books_db if b.id == book_id), None)
    if not book or book.copies <= 0:
        raise HTTPException(status_code=400, detail="Book not available.")

    if len([b for b in borrowed_books_db if b.reader_id == reader_id]) >= 3:
        raise HTTPException(status_code=400, detail="Reader cannot borrow more than 3 books.")

    book.copies -= 1
    borrowed_book = BorrowedBook(
        id=len(borrowed_books_db) + 1,
        book_id=book_id,
        reader_id=reader_id,
        borrow_date=datetime.now()
    )
    borrowed_books_db.append(borrowed_book)

    # Отправка уведомления о выдаче книги
    reader = next((r for r in readers_db if r.id == reader_id), None)
    if reader:
        mail_sender.send_email(
            recipient=reader.email,
            subject="Book Borrowed",
            body=f"You have borrowed the book: {book.title}."
        )

    return {"detail": "Book borrowed successfully."}

@app.post("/return/", dependencies=[Depends(get_current_user)])
def return_book(book_id: int, reader_id: int):
    borrowed_book = next((b for b in borrowed_books_db if b.book_id == book_id and b.reader_id == reader_id and b.return_date is None), None)
    if not borrowed_book:
        raise HTTPException(status_code=400, detail="Book not borrowed by this reader.")

    borrowed_book.return_date = datetime.now()
    book = next(b for b in books_db if b.id == book_id)
    book.copies += 1
    return {"detail": "Book returned successfully."}

@app.get("/readers/{reader_id}/borrowed_books/", dependencies=[Depends(get_current_user)])
def get_borrowed_books(reader_id: int):
    borrowed_books = [b for b in borrowed_books_db if b.reader_id == reader_id and b.return_date is None]
    return borrowed_books
