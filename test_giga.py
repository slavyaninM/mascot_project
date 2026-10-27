import os
from gigachat import GigaChat

# Подгружаем переменные из .env.local
if os.path.exists(".env.local"):
    with open(".env.local", "r", encoding="utf-8") as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ[k] = v.strip('"').strip("'").strip()

credentials = os.getenv("GIGACHAT_CREDENTIALS")
verify_ssl = os.getenv("GIGACHAT_VERIFY_SSL_CERTS", "False").lower() in ("true", "1")

print("🔌 Пробуем подключиться к GigaChat API...")
print(f"Ключ найден: {'Да' if credentials else 'Нет, проверьте .env.local'}")

try:
    # Явно задаем актуальный base_url и рабочую модель
    with GigaChat(
            credentials=credentials,
            verify_ssl_certs=verify_ssl,
            base_url="https://api.giga.chat/v1"
    ) as giga:

        response = giga.chat({
            "model": "GigaChat-2",  # Используем актуальную модель
            "messages": [
                {"role": "user", "content": "Привет! Если ты меня слышишь, ответь ровно одним словом: Готово!"}
            ]
        })
        print("\n🎉 Успех! Ответ от ИИ:")
        print(response.choices[0].message.content)
except Exception as e:
    print(f"\n❌ Ошибка подключения.\nДетали: {e}")


