# Архитектура системы аренды пауэрбанков

## Общая схема микросервисов

```mermaid
graph TB
    subgraph "Клиент"
        UI[Web UI<br/>Демо интерфейс]
    end
    
    subgraph "Основные микросервисы"
        RC[rental-core<br/>FastAPI<br/>:8000]
        BW[billing-worker<br/>Фоновый процесс]
    end
    
    subgraph "Хранилище данных"
        PG[(PostgreSQL<br/>:5432)]
        RD[(Redis<br/>:6379)]
    end
    
    subgraph "Внешние сервисы"
        ES[external-stubs<br/>:3629<br/>stations, tariffs,<br/>users, configs,<br/>payments]
    end
    
    UI -->|HTTP/REST| RC
    RC -->|SQL| PG
    RC -->|Cache| RD
    RC -->|HTTP| ES
    
    BW -->|SQL| PG
    BW -->|HTTP| ES
    
    style RC fill:#667eea,stroke:#333,stroke-width:2px,color:#fff
    style BW fill:#48bb78,stroke:#333,stroke-width:2px,color:#fff
    style PG fill:#336791,stroke:#333,stroke-width:2px,color:#fff
    style RD fill:#dc382d,stroke:#333,stroke-width:2px,color:#fff
    style ES fill:#f39c12,stroke:#333,stroke-width:2px,color:#fff
    style UI fill:#3498db,stroke:#333,stroke-width:2px,color:#fff
```

## Компоненты системы

### rental-core
- **Роль:** Обработка HTTP-запросов пользователей
- **Технологии:** Python 3.11, FastAPI, SQLAlchemy
- **Порт:** 8000
- **Функции:**
  - Создание офферов
  - Старт/стоп аренды
  - Получение статуса
  - Идемпотентность запросов

### billing-worker
- **Роль:** Периодическое начисление и списание платежей
- **Технологии:** Python 3.11, SQLAlchemy
- **Функции:**
  - Расчет начислений каждые 30 сек
  - Списание платежей
  - Управление долгами
  - Автовыкуп при достижении R_BUYOUT

### PostgreSQL
- **Роль:** Основное хранилище данных
- **Таблицы:**
  - rentals - активные аренды
  - quotes - офферы с TTL
  - payment_attempts - аудит платежей
  - debts - долги пользователей
  - idempotency_keys - защита от дублей

### Redis
- **Роль:** Кеширование (опционально)
- **Использование:** Кеш офферов, конфигов

### external-stubs
- **Роль:** Имитация внешних систем
- **Эндпоинты:**
  - /station-data - данные станций
  - /tariff - тарифы
  - /user-profile - профили пользователей
  - /configs - конфигурация
  - /eject-powerbank - выдача банки
  - /hold-money-for-order - удержание депозита
  - /clear-money-for-order - списание средств

---

## API Endpoints

### rental-core REST API

```mermaid
graph LR
    subgraph "Public API v1"
        Q[POST /api/v1/rentals/quote]
        S[POST /api/v1/rentals/start]
        E[POST /api/v1/rentals/stop]
        G[GET /api/v1/rentals/:id]
        H[GET /api/v1/health]
    end
    
    Q -->|Создать оффер| QR[Quote Response]
    S -->|Начать аренду| SR[Rental Response]
    E -->|Завершить аренду| ER[Rental Response]
    G -->|Получить статус| GR[Rental Status]
    H -->|Проверка здоровья| HR[Health Status]
    
    style Q fill:#48bb78,stroke:#333,stroke-width:2px,color:#fff
    style S fill:#48bb78,stroke:#333,stroke-width:2px,color:#fff
    style E fill:#48bb78,stroke:#333,stroke-width:2px,color:#fff
    style G fill:#3498db,stroke:#333,stroke-width:2px,color:#fff
    style H fill:#95a5a6,stroke:#333,stroke-width:2px,color:#fff
```

#### POST /api/v1/rentals/quote
**Назначение:** Создание оффера на аренду

**Request:**
```json
{
  "user_id": "user-123",
  "station_id": "station-456"
}
```

**Response 200:**
```json
{
  "quote_id": "quote-789",
  "price_per_hour": 60,
  "free_period_min": 5,
  "deposit": 500,
  "expires_in_sec": 60
}
```

---

#### POST /api/v1/rentals/start
**Назначение:** Начало аренды по офферу

**Headers:**
- `Idempotency-Key: <uuid>` (обязательный)

**Request:**
```json
{
  "quote_id": "quote-789"
}
```

**Response 200:**
```json
{
  "rental_id": "rental-abc",
  "powerbank_id": "pb-001",
  "status": "ACTIVE",
  "started_at": "2025-11-29T10:00:00Z",
  "total_amount": 0
}
```

**Response 400:**
```json
{
  "error": "Quote expired"
}
```

---

#### POST /api/v1/rentals/stop
**Назначение:** Завершение аренды

**Headers:**
- `Idempotency-Key: <uuid>` (обязательный)

**Request:**
```json
{
  "rental_id": "rental-abc",
  "station_id": "station-456"
}
```

**Response 200:**
```json
{
  "rental_id": "rental-abc",
  "status": "FINISHED",
  "started_at": "2025-11-29T10:00:00Z",
  "finished_at": "2025-11-29T11:30:00Z",
  "total_amount": 90,
  "duration_minutes": 90
}
```

---

#### GET /api/v1/rentals/:id
**Назначение:** Получение статуса аренды

**Response 200:**
```json
{
  "rental_id": "rental-abc",
  "status": "ACTIVE",
  "powerbank_id": "pb-001",
  "started_at": "2025-11-29T10:00:00Z",
  "total_amount": 45,
  "current_debt": 0,
  "duration_minutes": 45
}
```

---

#### GET /api/v1/health
**Назначение:** Проверка состояния сервиса

**Response 200:**
```json
{
  "status": "healthy",
  "database": "connected",
  "external_services": {
    "stations": "available",
    "tariffs": "available",
    "users": "available",
    "payments": "available"
  }
}
```

---

## External Services API

### external-stubs (имитация внешних систем)

```mermaid
graph LR
    subgraph "Read-only источники"
        SD[GET /station-data]
        T[GET /tariff]
        UP[GET /user-profile]
        C[GET /configs]
    end
    
    subgraph "Write операции"
        EP[POST /eject-powerbank]
        HM[POST /hold-money-for-order]
        CM[POST /clear-money-for-order]
    end
    
    style SD fill:#3498db,stroke:#333,stroke-width:2px,color:#fff
    style T fill:#3498db,stroke:#333,stroke-width:2px,color:#fff
    style UP fill:#3498db,stroke:#333,stroke-width:2px,color:#fff
    style C fill:#3498db,stroke:#333,stroke-width:2px,color:#fff
    style EP fill:#e67e22,stroke:#333,stroke-width:2px,color:#fff
    style HM fill:#e67e22,stroke:#333,stroke-width:2px,color:#fff
    style CM fill:#e67e22,stroke:#333,stroke-width:2px,color:#fff
```

#### GET /station-data
**Назначение:** Получение данных о станции

**Query params:**
- `id` - ID станции

**Response 200:**
```json
{
  "id": "station-456",
  "tariff_id": "tariff-1",
  "location": {"lat": 55.7558, "lon": 37.6173},
  "available_powerbanks": 5
}
```

---

#### GET /tariff
**Назначение:** Получение тарифа

**Query params:**
- `id` - ID тарифа

**Response 200:**
```json
{
  "id": "tariff-1",
  "price_per_hour": 60,
  "free_period_min": 5,
  "deposit": 500
}
```

---

#### GET /user-profile
**Назначение:** Получение профиля пользователя

**Query params:**
- `id` - ID пользователя

**Response 200:**
```json
{
  "id": "user-123",
  "trusted": true,
  "has_subscription": false
}
```

---

#### GET /configs
**Назначение:** Получение конфигурации системы

**Response 200:**
```json
{
  "R_BUYOUT": 5000,
  "BILLING_TICK_SEC": 30,
  "DEBT_CHARGE_STEP": 100
}
```

---

#### POST /eject-powerbank
**Назначение:** Выдача пауэрбанка из станции

**Request:**
```json
{
  "station_id": "station-456"
}
```

**Response 200:**
```json
{
  "success": true,
  "powerbank_id": "pb-001"
}
```

---

#### POST /hold-money-for-order
**Назначение:** Удержание депозита

**Request:**
```json
{
  "user_id": "user-123",
  "order_id": "rental-abc",
  "amount": 500
}
```

**Response 200:**
```json
{
  "status": "success"
}
```

**Response 400:**
```json
{
  "status": "error",
  "message": "Insufficient funds"
}
```

---

#### POST /clear-money-for-order
**Назначение:** Списание средств

**Request:**
```json
{
  "user_id": "user-123",
  "order_id": "rental-abc",
  "amount": 100
}
```

**Response 200:**
```json
{
  "status": "success"
}
```

**Response 400:**
```json
{
  "status": "error",
  "message": "Insufficient funds"
}
```

