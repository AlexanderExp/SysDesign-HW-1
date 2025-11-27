# Последовательность создания аренды

## Полный цикл: от оффера до старта аренды

```mermaid
sequenceDiagram
    actor User as Пользователь
    participant UI as Web UI
    participant RC as rental-core
    participant PG as PostgreSQL
    participant ES as external-stubs
    
    Note over User,ES: Шаг 1: Создание оффера
    
    User->>UI: Выбрать станцию
    UI->>RC: POST /api/v1/rentals/quote<br/>{user_id, station_id}
    
    RC->>ES: GET /station-data?id=station_id
    ES-->>RC: {tariff_id, location, slots}
    
    RC->>ES: GET /tariff?id=tariff_id
    ES-->>RC: {price_per_hour, free_period_min, deposit}
    
    RC->>ES: GET /user-profile?id=user_id
    ES-->>RC: {trusted, has_subscription}
    
    RC->>RC: Рассчитать цену и депозит<br/>(trusted → deposit/2)
    
    RC->>PG: INSERT INTO quotes<br/>(expires_at = now() + 60s)
    PG-->>RC: OK
    
    RC-->>UI: 200 OK<br/>{quote_id, price, deposit, expires_in_sec: 60}
    UI-->>User: Показать оффер
    
    Note over User,ES: Шаг 2: Начало аренды
    
    User->>UI: Нажать "Начать аренду"
    UI->>UI: Сгенерировать<br/>Idempotency-Key (UUID)
    UI->>RC: POST /api/v1/rentals/start<br/>{quote_id}<br/>Header: Idempotency-Key
    
    RC->>PG: SELECT * FROM idempotency_keys<br/>WHERE key = ?
    alt Ключ уже существует
        PG-->>RC: Найдена запись
        RC-->>UI: 200 OK (кешированный ответ)
    else Новый запрос
        PG-->>RC: Не найдено
        
        RC->>PG: SELECT * FROM quotes<br/>WHERE id = quote_id
        PG-->>RC: Quote данные
        
        RC->>RC: Проверить expires_at > now()
        
        alt Оффер протух
            RC-->>UI: 400 Bad Request<br/>"Quote expired"
        else Оффер валиден
            RC->>ES: GET /eject-powerbank?station_id
            ES-->>RC: {success: true, powerbank_id}
            
            RC->>PG: INSERT INTO rentals<br/>(status='ACTIVE', total_amount=0)
            PG-->>RC: OK
            
            RC->>ES: POST /hold-money-for-order<br/>{user_id, order_id, deposit}
            alt Депозит удержан
                ES-->>RC: {status: "success"}
            else Нет средств
                ES-->>RC: 400 Error
                RC->>PG: INSERT INTO debts<br/>(amount_total = deposit)
                Note over RC: Долг навешен,<br/>аренда продолжается
            end
            
            RC->>PG: INSERT INTO idempotency_keys<br/>(key, response_json)
            PG-->>RC: OK
            
            RC->>PG: DELETE FROM quotes<br/>WHERE id = quote_id
            Note over RC,PG: Оффер поглощен
            
            RC-->>UI: 200 OK<br/>{order_id, status: "ACTIVE",<br/>powerbank_id, total_amount: 0}
            UI-->>User: Аренда началась!
        end
    end
```

## Ключевые особенности

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

