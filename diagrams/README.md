# Диаграммы архитектуры системы аренды пауэрбанков

## Содержание

1. **[Общая архитектура](01-architecture-overview.md)**
   - Схема микросервисов
   - Компоненты системы
   - Технологический стек

2. **[Создание аренды](02-create-rental-flow.md)**
   - Sequence diagram: от оффера до старта
   - Идемпотентность
   - Контроль свежести оффера
   - Fallback для платежей

3. **[Процесс биллинга](03-billing-process.md)**
   - Периодическое начисление
   - Управление долгами
   - Exponential backoff
   - Автовыкуп (R_BUYOUT)

4. **[Схема базы данных](04-database-schema.md)**
   - ER-диаграмма
   - Описание таблиц
   - Индексы
   - Оценка размера данных

5. **[Паттерны надежности](05-reliability-patterns.md)**
   - Кеширование и fallback
   - HTTP retry стратегия
   - Идемпотентность
   - Graceful degradation

6. **[Масштабируемость](06-scalability.md)**
   - Горизонтальное масштабирование
   - Расчет нагрузки
   - Оценка ресурсов
   - Bottlenecks и решения

## Ключевые решения

### Архитектура
- 2 микросервиса: rental-core + billing-worker
- PostgreSQL для персистентности
- Redis для кеширования
- external-stubs для имитации внешних систем

### Надежность
- Fallback для некритичных источников
- Кеширование (configs, tariffs)
- Идемпотентность через idempotency_keys
- HTTP retry с exponential backoff

### Масштабируемость
- Stateless rental-core → горизонтальное масштабирование
- Шардирование billing-worker по rental_id
- PostgreSQL replicas для read
- Redis cluster для кеша

### Биллинг
- Периодическое начисление каждые 30 сек
- Управление долгами с exponential backoff
- Автовыкуп при R_BUYOUT = 5000 ₽
- Аудит всех платежей в payment_attempts
