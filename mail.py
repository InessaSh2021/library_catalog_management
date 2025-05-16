import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import HTTPException

class MailSender:
    def __init__(self, smtp_server: str, smtp_port: int, username: str, password: str):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password

    def send_email(self, recipient: str, subject: str, body: str):
        # Создаем сообщение
        msg = MIMEMultipart()
        msg['From'] = self.username
        msg['To'] = recipient
        msg['Subject'] = subject

        # Добавляем текстовое сообщение
        msg.attach(MIMEText(body, 'plain'))

        try:
            # Устанавливаем соединение с SMTP сервером
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()  # Защищаем соединение
                server.login(self.username, self.password)  # Входим в аккаунт
                server.send_message(msg)  # Отправляем сообщение
            print("Email sent successfully!")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to send email: {e}")

# Запуск (Точка входа)
if __name__ == "__main__":
    mail_sender = MailSender(
        smtp_server="smtp.example.com",
        smtp_port=587,
        username="your_email@example.com",
        password="your_password"
    )
    mail_sender.send_email(
        recipient="recipient@example.com",
        subject="Test Email",
        body="This is a test email sent from Python!"
    )
