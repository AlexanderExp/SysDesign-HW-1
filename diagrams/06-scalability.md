# Масштабируемость системы (Scalability)

## Параметры нагрузки (Команда 8)

```
X = 10 RPS  - создание аренд (/rentals/start)
Y = 10      - пользователей, просматривающих статус
Z = 1 KB    - размер записи об аренде
```

## Горизонтальное масштабирование

```mermaid
graph TB
    subgraph "Load Balancer"
        LB[nginx / ALB]
    end
    
    subgraph "rental-core (stateless)"
        RC1[rental-core-1<br/>:8000]
        RC2[rental-core-2<br/>:8000]
        RC3[rental-core-N<br/>:8000]
    end
    
    subgraph "billing-worker (stateful)"
        BW1[billing-worker-1<br/>Аренды 0-999]
        BW2[billing-worker-2<br/>Аренды 1000-1999]
        BW3[billing-worker-N<br/>Аренды 2000+]
    end
    
    subgraph "Хранилище"
        PG[(PostgreSQL<br/>Master)]
        PGR1[(Replica 1)]
        PGR2[(Replica 2)]
        RD[(Redis<br/>Cluster)]
    end
    
    LB --> RC1
    LB --> RC2
    LB --> RC3
    
    RC1 --> PG
    RC2 --> PG
    RC3 --> PG
    
    RC1 -.->|Read| PGR1
    RC2 -.->|Read| PGR2
    RC3 -.->|Read| PGR1
    
    RC1 --> RD
    RC2 --> RD
    RC3 --> RD
    
    BW1 --> PG
    BW2 --> PG
    BW3 --> PG
    
    PG -.->|Репликация| PGR1
    PG -.->|Репликация| PGR2
    
    style RC1 fill:#667eea,stroke:#333,stroke-width:2px,color:#fff
    style RC2 fill:#667eea,stroke:#333,stroke-width:2px,color:#fff
    style RC3 fill:#667eea,stroke:#333,stroke-width:2px,color:#fff
    style BW1 fill:#48bb78,stroke:#333,stroke-width:2px,color:#fff
    style BW2 fill:#48bb78,stroke:#333,stroke-width:2px,color:#fff
    style BW3 fill:#48bb78,stroke:#333,stroke-width:2px,color:#fff
    style PG fill:#336791,stroke:#333,stroke-width:2px,color:#fff
    style PGR1 fill:#5499c7,stroke:#333,stroke-width:2px,color:#fff
    style PGR2 fill:#5499c7,stroke:#333,stroke-width:2px,color:#fff
    style RD fill:#dc382d,stroke:#333,stroke-width:2px,color:#fff
```

## Считаем нагрузку

### Сколько запросов летит в API

**Запросы на запись:**
```
POST /rentals/quote:  ~10 RPS (пользователи создают офферы)
POST /rentals/start:  ~10 RPS (начинают аренду)
POST /rentals/stop:   ~10 RPS (возвращают банки)
-----------------------------------
Итого write:          ~30 RPS
```

**Запросы на чтение:**
```
GET /rentals/{id}/status: Y / 60 = 10 / 60 ≈ 0.17 RPS
(каждый пользователь смотрит статус 10 раз за всю аренду)
```

**Всего:** ~30 RPS write + 0.2 RPS read = **30.2 RPS** (легкая нагрузка)

### Что происходит с базой данных

**Один запрос /start делает:**
- 1 SELECT - проверяем, не дубликат ли (idempotency_key)
- 1 SELECT - достаем оффер
- 1 DELETE - удаляем использованный оффер
- 1 INSERT - создаем аренду
- 1 INSERT - сохраняем idempotency_key
- 0-1 INSERT - если платеж не прошел, создаем долг

**Итого:** ~50-60 запросов в БД в секунду (легко)

**Billing-worker работает каждые 30 секунд:**
- 1 SELECT - берем все активные аренды
- N × 3 SELECT - для каждой аренды читаем rental, payments, debts
- N × 1-2 INSERT/UPDATE - записываем payment_attempt и обновляем rental/debt

**Если активных аренд 100:** ~600 операций каждые 30 сек = **20 операций/сек**

**Итого нагрузка на БД:** ~80 операций/сек (PostgreSQL переживет)

### Сколько места займет в базе

**За час работы (X = 10 RPS):**
```
10 аренд/сек × 3600 сек = 36,000 аренд
36,000 × 1 KB = 36 MB (почти ничего)
```

**За сутки:**
```
864,000 аренд × 1 KB ≈ 864 MB (меньше гигабайта)
```

**За месяц:**
```
~25,000,000 аренд × 1 KB ≈ 25 GB
```

**С учетом всех попыток платежей и долгов:**
```
25 GB × 1.5 ≈ 37.5 GB/месяц (влезет на обычный SSD)
```

Вывод: при X=10 RPS места нужно мало, можно годами не чистить.

## Как масштабировать, если нагрузка вырастет

### 1. rental-core (легко масштабируется)

**Почему легко:**
- ✅ Не хранит состояние - каждый запрос независим
- ✅ Идемпотентность через БД, а не в памяти
- ✅ Можно просто запустить больше копий

**Как добавить инстансов:**
```yaml
# docker-compose.yml
rental-core:
  deploy:
    replicas: 3  # Было 1, стало 3 - втрое больше мощности
```

**Load Balancer на выбор:**
- nginx с round-robin (самое простое)
- AWS ALB / GCP Load Balancer (если в облаке)
- Kubernetes Service (если на k8s)

**Когда пора масштабировать:**
- CPU > 70% → добавляем инстанс
- Latency p95 > 500ms → добавляем инстанс
- RPS на один инстанс > 50 → добавляем инстанс

---

### 2. billing-worker (сложнее масштабируется)

**Проблема:**
- ⚠️ Нельзя просто запустить 10 копий - они будут обрабатывать одни и те же аренды
- ⚠️ Нужна координация, чтобы не списать деньги дважды

**Вариант 1: Шардирование по rental_id**
```python
# Worker 1 берет аренды, где rental_id % 3 == 0
# Worker 2 берет аренды, где rental_id % 3 == 1
# Worker 3 берет аренды, где rental_id % 3 == 2

def get_active_rental_ids(self, shard_id: int, total_shards: int):
    return [
        r_id for r_id in all_active_rentals
        if hash(r_id) % total_shards == shard_id
    ]
```
Плюс: легко реализовать. Минус: нужно перезапускать все воркеры при изменении их числа.

**Вариант 2: Работаем по очереди**
```python
# Worker 1 работает в 00:00, 00:02, 00:04...
# Worker 2 работает в 00:01, 00:03, 00:05...

import time
worker_id = 0
total_workers = 2

while True:
    if int(time.time() / 30) % total_workers == worker_id:
        process_all_rentals()
    time.sleep(30)
```
Плюс: простота. Минус: воркеры простаивают.

**Вариант 3: Leader Election (для прода)**
```python
# Используем Redis или etcd
# Один воркер активен, остальные в standby на случай падения
```
Плюс: надежность. Минус: сложность реализации.

---

### 3. PostgreSQL (база данных)

**Вертикальное масштабирование (проще всего):**
- Купить сервер помощнее (больше CPU/RAM)
- Поставить SSD вместо HDD (в разы быстрее)
- Подкрутить настройки (shared_buffers, work_mem)

**Горизонтальное масштабирование (если вертикальное не помогло):**
```
Master (пишем) → Replicas (читаем)
```

**Как разделить нагрузку:**
```python
# Запись всегда в master
rental_repo.create_rental(rental)  # → Master

# Чтение можно из реплики
rental_repo.get_rental_status(order_id)  # → Replica
```

**Обязательные индексы (без них будет медленно):**
```sql
CREATE INDEX idx_rentals_status ON rentals(status);
CREATE INDEX idx_rentals_user_id ON rentals(user_id);
CREATE INDEX idx_payment_attempts_rental_id ON payment_attempts(rental_id);
```
Без индексов БД будет сканировать всю таблицу → тормоза.

---

### 4. Redis (кеш)

**Зачем нужен:**
- Кешируем офферы (живут 60 сек)
- Кешируем тарифы (живут 10 минут)
- Кешируем конфиги (живут 1 минуту)
- Можно хранить сессии

**Если Redis упадет:** ничего страшного, просто будет чуть медленнее (пойдем в БД).

**Масштабирование:**
```
Redis Cluster (3 мастера + 3 реплики)
```
Но при X=10 RPS хватит одного инстанса.

---

## Сколько железа нужно

### Для нашей нагрузки X = 10 RPS

**rental-core:**
- 2 инстанса × 2 CPU × 4 GB RAM
- Каждый справится с ~15 RPS (есть запас)

**billing-worker:**
- 1 инстанс × 1 CPU × 2 GB RAM
- Потянет до 1000 активных аренд

**PostgreSQL:**
- 1 master × 4 CPU × 16 GB RAM (для записи)
- 1 replica × 2 CPU × 8 GB RAM (для чтения, опционально)

**Redis:**
- 1 инстанс × 1 CPU × 2 GB RAM (хватит с головой)

**Итого:** ~10 CPU, ~32 GB RAM (недорого)

---

### Если нагрузка вырастет в 10 раз (X = 100 RPS)

**rental-core:**
- 6 инстансов × 2 CPU × 4 GB RAM
- Каждый справится с ~17 RPS

**billing-worker:**
- 3 инстанса × 2 CPU × 4 GB RAM
- Делим аренды между ними (шардирование)

**PostgreSQL:**
- 1 master × 8 CPU × 32 GB RAM (помощнее)
- 2 replicas × 4 CPU × 16 GB RAM (для чтения)

**Redis:**
- 3 ноды в кластере × 2 CPU × 4 GB RAM

**Итого:** ~40 CPU, ~120 GB RAM (всё еще недорого)

---

## Узкие места и как их решать

| Что тормозит | Как понять | Что делать |
|------------|----------|---------|
| rental-core не справляется | Высокая latency, таймауты | Добавить инстансов |
| PostgreSQL медленно пишет | Slow INSERT/UPDATE | Мощнее сервер, проверить индексы |
| PostgreSQL медленно читает | Slow SELECT | Добавить реплики, больше кеша |
| billing-worker не успевает | Долги растут, обработка > 30 сек | Шардирование, больше воркеров |
| external-stubs тормозят | Таймауты | Увеличить timeout, retry, кеш |

---

## Что мониторить

**Ключевые метрики:**
- RPS (сколько запросов в секунду)
- Latency (p50, p95, p99 - время ответа)
- Error rate (процент ошибок 4xx/5xx)
- DB connections (сколько используется)
- Active rentals (сколько активных аренд)
- Debt collection rate (процент успешного списания долгов)

**Когда бить тревогу:**
- Latency p95 > 1s (слишком медленно)
- Error rate > 1% (много ошибок)
- DB connections > 80% (скоро кончатся)
- Active rentals > 5000 (пора масштабировать billing-worker)

**Инструменты (на выбор):**
- Prometheus + Grafana (метрики и графики)
- ELK Stack (логи и поиск по ним)
- Jaeger / OpenTelemetry (трейсинг запросов)

