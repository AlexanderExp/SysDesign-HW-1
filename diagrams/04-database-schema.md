# Схема базы данных

## ER-диаграмма

```mermaid
erDiagram
    RENTALS ||--o{ PAYMENT_ATTEMPTS : "имеет"
    RENTALS ||--o| DEBTS : "может иметь"
    RENTALS ||--o| IDEMPOTENCY_KEYS : "создается через"
    
    RENTALS {
        string id PK "UUID"
        string user_id "ID пользователя"
        string powerbank_id "ID пауэрбанка"
        int price_per_hour "Цена за час"
        int free_period_min "Бесплатный период"
        int deposit "Депозит"
        string status "ACTIVE|FINISHED|BUYOUT"
        int total_amount "Списанная сумма"
        datetime started_at "Время начала"
        datetime finished_at "Время окончания"
    }
    
    PAYMENT_ATTEMPTS {
        int id PK "Auto increment"
        string rental_id FK "ID аренды"
        int amount "Сумма попытки"
        boolean success "Успешность"
        string error "Текст ошибки"
        datetime created_at "Время попытки"
    }
    
    DEBTS {
        string rental_id PK_FK "ID аренды"
        int amount_total "Текущий долг"
        datetime updated_at "Время обновления"
        int attempts "Число попыток"
        datetime last_attempt_at "Последняя попытка"
    }
    
    QUOTES {
        string id PK "UUID"
        string user_id "ID пользователя"
        string station_id "ID станции"
        int price_per_hour "Цена за час"
        int free_period_min "Бесплатный период"
        int deposit "Депозит"
        datetime expires_at "Время протухания"
        datetime created_at "Время создания"
    }
    
    IDEMPOTENCY_KEYS {
        string key PK "Idempotency-Key"
        string scope "start|stop|payment"
        string user_id "ID пользователя"
        text response_json "Кешированный ответ"
        datetime created_at "Время создания"
    }
```

## Описание таблиц

### rentals
**Назначение:** Основная таблица аренд

**Ключевые поля:**
- `status`: 
  - `ACTIVE` - аренда в процессе
  - `FINISHED` - завершена пользователем
  - `BUYOUT` - автовыкуп при достижении R_BUYOUT
- `total_amount`: Сумма успешно списанных платежей
- `started_at` / `finished_at`: Для расчета длительности

**Индексы:**
- PK на `id`
- Index на `status` (для быстрого поиска активных аренд)

---

### payment_attempts
**Назначение:** Аудит всех попыток списания

**Ключевые поля:**
- `success`: `true` - успех, `false` - ошибка
- `error`: Текст ошибки при неуспехе
- `amount`: Сумма попытки

**Индексы:**
- PK на `id`
- Index на `rental_id` (для агрегации по аренде)

**Использование:**
```sql
-- Получить сумму успешных платежей
SELECT SUM(amount) 
FROM payment_attempts 
WHERE rental_id = ? AND success = true
```

---

### debts
**Назначение:** Управление долгами пользователей

**Ключевые поля:**
- `amount_total`: Текущая сумма долга
- `attempts`: Счетчик неуспешных попыток списания
- `last_attempt_at`: Для расчета exponential backoff

**Индексы:**
- PK на `rental_id` (один долг на аренду)

**Логика:**
- Долг создается при неуспехе платежа
- Уменьшается при успешном погашении
- `attempts` сбрасывается в 0 при успехе
- `attempts` увеличивается при неуспехе

---

### quotes
**Назначение:** Временные офферы с TTL

**Ключевые поля:**
- `expires_at`: Время протухания (now() + 60 секунд)
- `price_per_hour`, `deposit`: Зафиксированные условия

**Жизненный цикл:**
1. Создается при `POST /rentals/quote`
2. Проверяется при `POST /rentals/start`
3. Удаляется после успешного старта (поглощение)

**Очистка:** Можно добавить cron для удаления протухших офферов

---

### idempotency_keys
**Назначение:** Защита от дублирования запросов

**Ключевые поля:**
- `key`: Уникальный ключ из заголовка `Idempotency-Key`
- `scope`: Тип операции (`start`, `stop`, `payment`)
- `response_json`: Кешированный ответ для повторных запросов

**Использование:**
```python
# При повторном запросе с тем же ключом
cached = get_cached_response(idempotency_key)
if cached:
    return cached  # Вернуть сохраненный ответ
```

**Очистка:** Можно удалять записи старше N дней

---

## Размер данных (Z = 1 KB)

**Одна аренда:**
```
rentals:           ~200 bytes
payment_attempts:  ~100 bytes * N попыток
debts:             ~100 bytes (если есть)
idempotency_keys:  ~300 bytes
quotes:            ~200 bytes (удаляется после старта)
-----------------------------------
Итого:             ~600-800 bytes + N * 100 bytes
```

**При X = 10 RPS:**
- За час: 36,000 аренд × 1 KB ≈ 36 MB
- За сутки: 864,000 аренд × 1 KB ≈ 864 MB
- За месяц: ~25 GB

**Оптимизация:**
- Архивирование старых аренд (> 30 дней)
- Удаление payment_attempts после завершения
- Очистка idempotency_keys

