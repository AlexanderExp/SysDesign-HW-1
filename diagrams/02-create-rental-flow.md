# Последовательность создания аренды

## Полный цикл: от оффера до старта аренды

```mermaid
sequenceDiagram
    actor User
    participant UI
    participant RC as rental-core
    participant PG as PostgreSQL
    participant ES as external-stubs
    
    Note over User,ES: Создание оффера
    
    User->>UI: Выбрать станцию
    UI->>RC: POST /quote {user_id, station_id}
    
    RC->>ES: GET /station-data
    ES-->>RC: tariff_id, location
    
    RC->>ES: GET /tariff
    ES-->>RC: price, free_period, deposit
    
    RC->>ES: GET /user-profile
    ES-->>RC: trusted, subscription
    
    RC->>RC: Расчет цены<br/>(trusted → deposit/2)
    
    RC->>PG: INSERT quote (TTL=60s)
    PG-->>RC: quote_id
    
    RC-->>UI: 200 {quote_id, price, deposit}
    UI-->>User: Показать оффер
    
    Note over User,ES: Начало аренды
    
    User->>UI: "Начать аренду"
    UI->>UI: Генерация<br/>Idempotency-Key
    UI->>RC: POST /start {quote_id}<br/>Header: Idempotency-Key
    
    RC->>PG: SELECT idempotency_keys
    alt Дубликат запроса
        PG-->>RC: Запись найдена
        RC-->>UI: 200 (кешированный ответ)
    else Новый запрос
        PG-->>RC: Не найдено
        
        RC->>PG: SELECT quote
        PG-->>RC: quote_data
        
        RC->>RC: Проверка expires_at
        
        alt Оффер истек
            RC-->>UI: 400 "Quote expired"
        else Оффер валиден
            RC->>PG: INSERT rental (PENDING)
            PG-->>RC: rental_id
            Note over RC,PG: Сначала БД, потом банка!
            
            RC->>ES: GET /eject-powerbank
            alt Выдача успешна
                ES-->>RC: powerbank_id
                RC->>PG: UPDATE rental (powerbank_id)
            else Выдача неуспешна
                ES-->>RC: error
                RC->>PG: UPDATE rental (FAILED)
                RC-->>UI: 500 "Eject failed"
            end
            
            RC->>ES: POST /hold-money {deposit}
            alt Депозит удержан
                ES-->>RC: success
            else Недостаточно средств
                ES-->>RC: 400 error
                RC->>PG: INSERT debt (deposit)
                Note over RC: Долг зафиксирован,<br/>аренда продолжается
            end
            
            RC->>PG: INSERT idempotency_key
            PG-->>RC: OK
            
            RC->>PG: DELETE quote
            Note over RC,PG: Оффер использован
            
            RC-->>UI: 200 {rental_id, ACTIVE}
            UI-->>User: Аренда активна
        end
    end
```

## Ключевые особенности

### Правильный порядок операций (критично!)
**Проблема:** Если сначала выдать пауэрбанк, а потом записать в БД - при падении БД пользователь получит банку бесплатно.

**Решение:**
1. Сначала создаем запись в БД со статусом `PENDING`
2. Только после успешной записи выдаем пауэрбанк
3. Обновляем `powerbank_id` в БД
4. Если выдача не удалась → помечаем аренду как `FAILED`

**Результат:** Если БД упала - пауэрбанк не выдается. Если выдача упала - есть запись в БД для отладки.

### Идемпотентность
- Каждый запрос `/start` требует уникальный `Idempotency-Key`
- Повторный запрос с тем же ключом возвращает кешированный ответ
- Защита от дублирования аренд при сетевых проблемах

### Контроль свежести оффера
- Оффер живет 60 секунд (`expires_at`)
- При старте аренды проверяется актуальность
- Протухший оффер → ошибка 400

### Fallback для платежей
- Если депозит не удалось удержать → добавляем в долг
- Аренда начинается в любом случае (требование NFR)
- Долг будет списываться периодически billing-worker'ом

### Поглощение оффера
- После успешного старта оффер удаляется
- Один оффер = одна аренда
- Защита от повторного использования

