# Процесс биллинга и управления долгами

## Периодическое начисление платежей

```mermaid
sequenceDiagram
    participant BW as billing-worker
    participant PGB as db-billing
    participant ES as external-stubs
    
    Note over BW: Тик каждые 30 сек
    
    loop Обработка активных аренд
        BW->>PGB: SELECT rentals (ACTIVE)
        PGB-->>BW: active_rentals[]
        
        BW->>BW: Расчет due_amount<br/>(price × billable_sec / 3600)
        
        BW->>PGB: SELECT SUM(payment_attempts)
        PGB-->>BW: paid_amount
        
        BW->>PGB: SELECT debts
        PGB-->>BW: debt_amount
        
        BW->>BW: to_charge = due - paid - debt
        
        alt Достигнут R_BUYOUT
            BW->>BW: paid + debt >= R_BUYOUT?
            BW->>PGB: UPDATE rental (BUYOUT)
            Note over BW,PGB: Автовыкуп
        else Новое начисление (to_charge > 0)
            BW->>ES: POST /clear-money {to_charge}
            
            alt Списание успешно
                ES-->>BW: success
                BW->>PGB: INSERT payment_attempt (success)
                BW->>PGB: UPDATE rental.total_amount
                Note over BW,PGB: Оплачено
            else Недостаточно средств
                ES-->>BW: 400 error
                BW->>PGB: INSERT payment_attempt (fail)
                BW->>PGB: UPDATE debt (+to_charge)
                Note over BW,PGB: Долг увеличен
            end
            
            BW->>BW: Проверка R_BUYOUT
            alt Порог достигнут
                BW->>PGB: UPDATE rental (BUYOUT)
            end
        else Нет начислений (to_charge <= 0)
            alt Есть долг
                BW->>PGB: SELECT debt
                PGB-->>BW: amount, attempts, last_attempt
                
                BW->>BW: Расчет backoff<br/>(60 × 2^attempts, max 3600s)
                
                BW->>BW: Проверка интервала
                
                alt Время для retry
                    BW->>BW: charge = min(debt, step)
                    BW->>ES: POST /clear-money {charge}
                    
                    alt Погашение успешно
                        ES-->>BW: success
                        BW->>PGB: UPDATE debt (-charge, attempts=0)
                        BW->>PGB: UPDATE rental.total_amount
                        Note over BW,PGB: Долг погашен
                    else Погашение неуспешно
                        ES-->>BW: 400 error
                        BW->>PGB: UPDATE debt (attempts+1)
                        Note over BW,PGB: Счетчик попыток++
                    end
                else Backoff период
                    Note over BW: Пропуск попытки
                end
            end
        end
    end
    
    BW->>BW: Логирование метрик
```

## Формула расчета начислений

```
total_seconds = current_time - started_at
free_seconds = free_period_min * 60
billable_seconds = max(0, total_seconds - free_seconds)

due_amount = ceil((price_per_hour * billable_seconds) / 3600)
```

**Пример:**
- Цена: 60 ₽/час
- Бесплатный период: 5 минут
- Прошло времени: 7 минут = 420 секунд
- Начисление: `ceil((60 * (420 - 300)) / 3600) = ceil(2) = 2 ₽`

## Exponential Backoff для долгов

```
Попытка 0: через 60 секунд
Попытка 1: через 120 секунд (60 * 2¹)
Попытка 2: через 240 секунд (60 * 2²)
Попытка 3: через 480 секунд (60 * 2³)
...
Попытка 8+: через 3600 секунд (максимум 1 час)
```

**Цель:** Не перегружать систему платежей при отсутствии средств у пользователя

## Автовыкуп (R_BUYOUT)

**Условие:** `paid_amount + debt_amount >= R_BUYOUT`

**Действие:**
1. Установить `status = 'BUYOUT'`
2. Установить `finished_at = now()`
3. Прекратить начисления
4. Пользователь выкупил пауэрбанк

**Пример:** R_BUYOUT = 5000 ₽
- Если пользователь накатал на 5000 ₽ → банка его
- Долг при этом учитывается (даже если не оплачен)

