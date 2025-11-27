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

