# Тесты системы аренды пауэрбанков

## Структура тестов

```
tests/
├── conftest.py              # Общие fixtures для всех тестов
├── test_health.py           # Тесты health check
├── test_quotes.py           # Тесты создания и истечения офферов
├── test_rentals.py          # Тесты жизненного цикла аренды
├── test_billing.py          # Тесты биллинга
├── test_buyout.py           # Тесты автовыкупа
└── test_debt.py             # Тесты работы с долгами
```

## Требования

- Python 3.11+
- Запущенные сервисы (rental-core, billing-worker, db, redis, external-stubs)

## Установка зависимостей

```bash
pip install -r tests/requirements.txt
```

## Запуск тестов

### Все тесты
```bash
pytest tests/
```

### Только быстрые тесты (без slow)
```bash
pytest tests/ -m "not slow"
```

### Только integration тесты
```bash
pytest tests/ -m integration
```

### Только billing тесты
```bash
pytest tests/ -m billing
```

### С покрытием кода
```bash
pytest tests/ --cov=services --cov-report=html
```

### Конкретный файл
```bash
pytest tests/test_quotes.py
```

### Конкретный тест
```bash
pytest tests/test_quotes.py::test_create_quote_success -v
```

## Переменные окружения

Тесты используют следующие переменные окружения (со значениями по умолчанию):

- `RENTAL_CORE_BASE` - URL rental-core API (default: http://localhost:8000)
- `EXTERNAL_BASE` - URL external stubs (default: http://localhost:3629)
- `DATABASE_URL` - PostgreSQL connection string (default: postgresql+psycopg2://app:app@localhost:5432/rental)
- `R_BUYOUT` - Порог выкупа (default: 5000)
- `SKIP_DEBT_TESTS` - Пропустить тесты долгов, требующие docker control (default: 0)

Пример:
```bash
export RENTAL_CORE_BASE=http://localhost:8000
export R_BUYOUT=3000
pytest tests/
```

## Покрываемые сценарии

### Базовые сценарии
- ✅ Health check работает
- ✅ Создание оффера (quote)
- ✅ Оффер сохраняется в БД
- ✅ Оффер истекает через заданное время
- ✅ Старт аренды с валидным оффером
- ✅ Идемпотентность старта аренды
- ✅ Ошибка при старте без idempotency key
- ✅ Ошибка при старте с невалидным оффером
- ✅ Получение статуса аренды
- ✅ Завершение аренды

### Биллинг
- ✅ Автоматическое списание после прошедшего времени
- ✅ Уважение бесплатного периода
- ✅ Накопление платежей
- ✅ Прекращение биллинга после завершения аренды

### Автовыкуп
- ✅ Переход в статус BUYOUT при достижении порога
- ✅ Остановка списаний после выкупа
- ✅ Ручное завершение до выкупа

### Долги
- ✅ Создание долга при ошибке платежа
- ✅ Повторные попытки с backoff
- ✅ Успешное погашение долга
- ✅ Отображение долга в статусе

## Структура тест-кейсов

Каждый тест следует структуре:

1. **Arrange** - подготовка данных (создание quote, rental)
2. **Act** - выполнение действия (API call, изменение времени)
3. **Assert** - проверка результата

## Fixtures

### Основные fixtures

- `api_client` - HTTP клиент для вызова API
- `db_session` - SQLAlchemy сессия для работы с БД
- `test_user_id` - ID тестового пользователя
- `test_station_id` - ID тестовой станции
- `wait_for_billing` - Helper для ожидания billing worker
- `cleanup_db` - Очистка БД после теста

### Использование fixtures

```python
def test_example(api_client, db_session, test_user_id, cleanup_db):
    # api_client - для вызовов API
    response = api_client.post("/api/v1/rentals/quote", 
                                json={"user_id": test_user_id, ...})
    
    # db_session - для проверки БД
    result = db_session.execute(text("SELECT * FROM quotes"))
    
    # cleanup_db автоматически очистит БД после теста
```

## CI/CD Integration

Добавьте в `.github/workflows/test.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Start services
        run: docker-compose up -d
      
      - name: Install dependencies
        run: pip install -r tests/requirements.txt
      
      - name: Wait for services
        run: sleep 10
      
      - name: Run tests
        run: pytest tests/ -v --cov=services
      
      - name: Stop services
        run: docker-compose down
```

## Отладка

### Просмотр логов при падении теста
```bash
pytest tests/ -v --tb=long
```

### Остановка на первой ошибке
```bash
pytest tests/ -x
```

### Запуск с отладчиком
```bash
pytest tests/ --pdb
```

### Показать print statements
```bash
pytest tests/ -s
```