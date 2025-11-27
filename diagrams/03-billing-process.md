# Процесс биллинга и управления долгами

## Периодическое начисление платежей

```mermaid
sequenceDiagram
    participant BW as billing-worker
    participant PG as PostgreSQL
    participant ES as external-stubs
    
    Note over BW: Каждые 30 секунд (BILLING_TICK_SEC)
    
    loop Для каждой активной аренды
        BW->>PG: SELECT * FROM rentals<br/>WHERE status = 'ACTIVE'
        PG-->>BW: Список активных аренд
        
        BW->>BW: Рассчитать due_amount<br/>= (price_per_hour * billable_seconds) / 3600<br/>billable_seconds = total - free_period
        
        BW->>PG: SELECT SUM(amount) FROM payment_attempts<br/>WHERE rental_id = ? AND success = true
        PG-->>BW: paid_amount
        
        BW->>PG: SELECT amount_total FROM debts<br/>WHERE rental_id = ?
        PG-->>BW: debt_amount
        
        BW->>BW: to_charge = due_amount - paid_amount - debt_amount
        
        alt Достигнут порог выкупа
            BW->>BW: Проверить: paid + debt >= R_BUYOUT?
            BW->>PG: UPDATE rentals<br/>SET status = 'BUYOUT', finished_at = now()
            Note over BW,PG: Аренда завершена автоматически
        else Есть что начислить (to_charge > 0)
            BW->>ES: POST /clear-money-for-order<br/>{user_id, order_id, to_charge}
            
            alt Платеж успешен
                ES-->>BW: {status: "success"}
                BW->>PG: INSERT INTO payment_attempts<br/>(amount, success=true)
                BW->>PG: UPDATE rentals<br/>SET total_amount += to_charge
                Note over BW,PG: Деньги списаны
            else Платеж не прошел
                ES-->>BW: 400 Error (нет средств)
                BW->>PG: INSERT INTO payment_attempts<br/>(amount, success=false, error)
                BW->>PG: INSERT/UPDATE debts<br/>SET amount_total += to_charge
                Note over BW,PG: Долг увеличен
            end
            
            BW->>BW: Проверить: paid + debt >= R_BUYOUT?
            alt Достигнут порог после начисления
                BW->>PG: UPDATE rentals<br/>SET status = 'BUYOUT', finished_at = now()
            end
        else Нет новых начислений (to_charge <= 0)
            alt Есть исторический долг
                BW->>PG: SELECT * FROM debts<br/>WHERE rental_id = ?
                PG-->>BW: {amount_total, attempts, last_attempt_at}
                
                BW->>BW: Рассчитать backoff<br/>= base * 2^attempts<br/>(max 1 час)
                
                BW->>BW: Проверить: now - last_attempt >= backoff?
                
                alt Можно повторить попытку
                    BW->>BW: charge_amount = min(debt, DEBT_CHARGE_STEP)
                    BW->>ES: POST /clear-money-for-order<br/>{user_id, order_id, charge_amount}
                    
                    alt Долг погашен частично/полностью
                        ES-->>BW: {status: "success"}
                        BW->>PG: UPDATE debts<br/>SET amount_total -= charge_amount,<br/>attempts = 0
                        BW->>PG: UPDATE rentals<br/>SET total_amount += charge_amount
                        Note over BW,PG: Долг уменьшен
                    else Долг не погашен
                        ES-->>BW: 400 Error
                        BW->>PG: UPDATE debts<br/>SET attempts += 1,<br/>last_attempt_at = now()
                        Note over BW,PG: Увеличен счетчик попыток
                    end
                else Еще в периоде backoff
                    Note over BW: Пропускаем попытку
                end
            end
        end
    end
    
    BW->>BW: Логировать результаты:<br/>active_rentals, total_charged, debt_delta
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

