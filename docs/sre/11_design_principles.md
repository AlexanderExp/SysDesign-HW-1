# 11. Принципы проектирования

> **Сложность:** ⭐⭐ Средний уровень
> **Дополнительная тема** — не было в вопросах, но важно знать

---

## Зачем нужны принципы проектирования?

Принципы проектирования — это **правила**, которые помогают писать код, который:
- Легко понимать
- Легко изменять
- Легко тестировать
- Легко переиспользовать

```
┌─────────────────────────────────────────────────────────┐
│              КРИТЕРИИ ХОРОШЕЙ АРХИТЕКТУРЫ               │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. ЭФФЕКТИВНОСТЬ                                       │
│     Система решает поставленные задачи                  │
│                                                         │
│  2. ГИБКОСТЬ                                            │
│     Легко вносить изменения                             │
│                                                         │
│  3. РАСШИРЯЕМОСТЬ                                       │
│     Легко добавлять новый функционал                    │
│                                                         │
│  4. ТЕСТИРУЕМОСТЬ                                       │
│     Легко писать тесты                                  │
│                                                         │
│  5. ПОНЯТНОСТЬ                                          │
│     Новый разработчик быстро разберётся                 │
│                                                         │
│  6. ПЕРЕИСПОЛЬЗУЕМОСТЬ                                  │
│     Компоненты можно использовать в других местах       │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## SOLID принципы

**SOLID** — это 5 принципов объектно-ориентированного проектирования.

### S — Single Responsibility Principle (Принцип единственной ответственности)

```
┌─────────────────────────────────────────────────────────┐
│           SINGLE RESPONSIBILITY PRINCIPLE               │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Правило: У класса должна быть только ОДНА причина      │
│           для изменения                                 │
│                                                         │
│  ❌ ПЛОХО: Один класс делает всё                        │
│                                                         │
│  class UserService:                                     │
│      def create_user(self, data):                       │
│          # валидация                                    │
│          # сохранение в БД                              │
│          # отправка email                               │
│          # логирование                                  │
│          # генерация отчёта                             │
│                                                         │
│  ✅ ХОРОШО: Каждый класс — одна задача                  │
│                                                         │
│  class UserValidator:                                   │
│      def validate(self, data): ...                      │
│                                                         │
│  class UserRepository:                                  │
│      def save(self, user): ...                          │
│                                                         │
│  class EmailService:                                    │
│      def send_welcome(self, user): ...                  │
│                                                         │
│  class UserService:                                     │
│      def __init__(self, validator, repo, email):        │
│          self.validator = validator                     │
│          self.repo = repo                               │
│          self.email = email                             │
│                                                         │
│      def create_user(self, data):                       │
│          user = self.validator.validate(data)          │
│          self.repo.save(user)                           │
│          self.email.send_welcome(user)                  │
│                                                         │
│  Преимущества:                                          │
│  • Легче тестировать (можно мокать зависимости)         │
│  • Легче изменять (изменение email не трогает БД)       │
│  • Легче переиспользовать (EmailService в других местах)│
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### O — Open/Closed Principle (Принцип открытости/закрытости)

```
┌─────────────────────────────────────────────────────────┐
│              OPEN/CLOSED PRINCIPLE                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Правило: Открыт для расширения, закрыт для изменения   │
│           Добавляй новое, не меняя старое               │
│                                                         │
│  ❌ ПЛОХО: Изменяем существующий код                    │
│                                                         │
│  class PaymentProcessor:                                │
│      def process(self, payment_type, amount):           │
│          if payment_type == "card":                     │
│              # обработка карты                          │
│          elif payment_type == "paypal":                 │
│              # обработка PayPal                         │
│          elif payment_type == "crypto":  # НОВОЕ!       │
│              # обработка крипты                         │
│                                                         │
│  Проблема: Каждый новый способ оплаты требует           │
│            изменения класса PaymentProcessor            │
│                                                         │
│  ✅ ХОРОШО: Расширяем через новые классы                │
│                                                         │
│  class PaymentMethod(ABC):                              │
│      @abstractmethod                                    │
│      def process(self, amount): ...                     │
│                                                         │
│  class CardPayment(PaymentMethod):                      │
│      def process(self, amount): ...                     │
│                                                         │
│  class PayPalPayment(PaymentMethod):                    │
│      def process(self, amount): ...                     │
│                                                         │
│  class CryptoPayment(PaymentMethod):  # НОВОЕ!          │
│      def process(self, amount): ...                     │
│                                                         │
│  class PaymentProcessor:                                │
│      def process(self, method: PaymentMethod, amount):  │
│          method.process(amount)  # Не меняется!         │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### L — Liskov Substitution Principle (Принцип подстановки Лисков)

```
┌─────────────────────────────────────────────────────────┐
│           LISKOV SUBSTITUTION PRINCIPLE                 │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Правило: Подклассы должны быть заменяемы на базовый    │
│           класс без изменения поведения программы       │
│                                                         │
│  ❌ ПЛОХО: Подкласс нарушает контракт                   │
│                                                         │
│  class Rectangle:                                       │
│      def set_width(self, w): self.width = w             │
│      def set_height(self, h): self.height = h           │
│      def area(self): return self.width * self.height    │
│                                                         │
│  class Square(Rectangle):                               │
│      def set_width(self, w):                            │
│          self.width = w                                 │
│          self.height = w  # Нарушение! Меняем и высоту  │
│                                                         │
│  # Код, который работал с Rectangle, сломается:         │
│  def test(rect):                                        │
│      rect.set_width(5)                                  │
│      rect.set_height(10)                                │
│      assert rect.area() == 50  # Для Square будет 100!  │
│                                                         │
│  ✅ ХОРОШО: Не наследовать, если поведение разное       │
│                                                         │
│  class Shape(ABC):                                      │
│      @abstractmethod                                    │
│      def area(self): ...                                │
│                                                         │
│  class Rectangle(Shape):                                │
│      def __init__(self, w, h): ...                      │
│      def area(self): return self.width * self.height    │
│                                                         │
│  class Square(Shape):                                   │
│      def __init__(self, side): ...                      │
│      def area(self): return self.side ** 2              │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### I — Interface Segregation Principle (Принцип разделения интерфейсов)

```
┌─────────────────────────────────────────────────────────┐
│          INTERFACE SEGREGATION PRINCIPLE                │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Правило: Много специализированных интерфейсов лучше,   │
│           чем один универсальный                        │
│                                                         │
│  ❌ ПЛОХО: Толстый интерфейс                            │
│                                                         │
│  class Worker(ABC):                                     │
│      @abstractmethod                                    │
│      def work(self): ...                                │
│      @abstractmethod                                    │
│      def eat(self): ...                                 │
│      @abstractmethod                                    │
│      def sleep(self): ...                               │
│                                                         │
│  class Robot(Worker):                                   │
│      def work(self): ...                                │
│      def eat(self): raise NotImplementedError()  # ??   │
│      def sleep(self): raise NotImplementedError() # ??  │
│                                                         │
│  ✅ ХОРОШО: Маленькие интерфейсы                        │
│                                                         │
│  class Workable(ABC):                                   │
│      @abstractmethod                                    │
│      def work(self): ...                                │
│                                                         │
│  class Eatable(ABC):                                    │
│      @abstractmethod                                    │
│      def eat(self): ...                                 │
│                                                         │
│  class Human(Workable, Eatable):                        │
│      def work(self): ...                                │
│      def eat(self): ...                                 │
│                                                         │
│  class Robot(Workable):  # Только то, что нужно         │
│      def work(self): ...                                │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### D — Dependency Inversion Principle (Принцип инверсии зависимостей)

```
┌─────────────────────────────────────────────────────────┐
│          DEPENDENCY INVERSION PRINCIPLE                 │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Правило: Зависи от абстракций, а не от реализаций      │
│                                                         │
│  ❌ ПЛОХО: Зависимость от конкретного класса            │
│                                                         │
│  class MySQLDatabase:                                   │
│      def save(self, data): ...                          │
│                                                         │
│  class UserService:                                     │
│      def __init__(self):                                │
│          self.db = MySQLDatabase()  # Жёсткая связь!    │
│                                                         │
│  Проблема: Нельзя заменить MySQL на PostgreSQL          │
│            без изменения UserService                    │
│                                                         │
│  ✅ ХОРОШО: Зависимость от абстракции                   │
│                                                         │
│  class Database(ABC):                                   │
│      @abstractmethod                                    │
│      def save(self, data): ...                          │
│                                                         │
│  class MySQLDatabase(Database):                         │
│      def save(self, data): ...                          │
│                                                         │
│  class PostgreSQLDatabase(Database):                    │
│      def save(self, data): ...                          │
│                                                         │
│  class UserService:                                     │
│      def __init__(self, db: Database):  # Абстракция!   │
│          self.db = db                                   │
│                                                         │
│  # Теперь можно подставить любую реализацию:            │
│  service = UserService(MySQLDatabase())                 │
│  service = UserService(PostgreSQLDatabase())            │
│  service = UserService(MockDatabase())  # Для тестов!   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Другие важные принципы

### DRY — Don't Repeat Yourself

```
┌─────────────────────────────────────────────────────────┐
│                        DRY                              │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Правило: Не повторяй себя. Каждое знание должно        │
│           иметь единственное представление в системе    │
│                                                         │
│  ❌ ПЛОХО: Дублирование кода                            │
│                                                         │
│  def create_user(data):                                 │
│      if not data.get('email'):                          │
│          raise ValueError("Email required")             │
│      if '@' not in data['email']:                       │
│          raise ValueError("Invalid email")              │
│      # ...                                              │
│                                                         │
│  def update_user(data):                                 │
│      if not data.get('email'):                          │
│          raise ValueError("Email required")  # Копия!   │
│      if '@' not in data['email']:                       │
│          raise ValueError("Invalid email")   # Копия!   │
│      # ...                                              │
│                                                         │
│  ✅ ХОРОШО: Выносим общую логику                        │
│                                                         │
│  def validate_email(email):                             │
│      if not email:                                      │
│          raise ValueError("Email required")             │
│      if '@' not in email:                               │
│          raise ValueError("Invalid email")              │
│                                                         │
│  def create_user(data):                                 │
│      validate_email(data.get('email'))                  │
│      # ...                                              │
│                                                         │
│  def update_user(data):                                 │
│      validate_email(data.get('email'))                  │
│      # ...                                              │
│                                                         │
│  ⚠️ Но! Не путай с преждевременной абстракцией          │
│     Дублирование кода ≠ дублирование знания             │
│     Иногда похожий код — это случайное совпадение       │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### KISS — Keep It Simple, Stupid

```
┌─────────────────────────────────────────────────────────┐
│                        KISS                             │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Правило: Делай проще. Простое решение лучше сложного   │
│                                                         │
│  ❌ ПЛОХО: Переусложнение                               │
│                                                         │
│  class AbstractFactoryBuilderStrategyFacade:            │
│      def create_builder_for_strategy_with_facade(self): │
│          factory = AbstractFactory()                    │
│          builder = factory.create_builder()             │
│          strategy = builder.build_strategy()            │
│          return FacadeWrapper(strategy)                 │
│                                                         │
│  # Для простой задачи: сохранить пользователя           │
│                                                         │
│  ✅ ХОРОШО: Простое решение                             │
│                                                         │
│  def save_user(user):                                   │
│      db.users.insert(user)                              │
│                                                         │
│  Правила:                                               │
│  • Не добавляй абстракции "на будущее"                  │
│  • Используй простые структуры данных                   │
│  • Избегай premature optimization                       │
│  • Если можно обойтись без паттерна — обойдись          │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### YAGNI — You Aren't Gonna Need It

```
┌─────────────────────────────────────────────────────────┐
│                       YAGNI                             │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Правило: Не делай того, что не нужно прямо сейчас      │
│                                                         │
│  ❌ ПЛОХО: Код "на будущее"                             │
│                                                         │
│  class UserService:                                     │
│      def create_user(self, data):                       │
│          # Основная логика                              │
│          pass                                           │
│                                                         │
│      def create_user_async(self, data):                 │
│          # Вдруг понадобится асинхронность!             │
│          pass                                           │
│                                                         │
│      def create_user_batch(self, users):                │
│          # Вдруг нужно будет создавать пачками!         │
│          pass                                           │
│                                                         │
│      def create_user_with_retry(self, data):            │
│          # Вдруг нужны будут ретраи!                    │
│          pass                                           │
│                                                         │
│  ✅ ХОРОШО: Только то, что нужно сейчас                 │
│                                                         │
│  class UserService:                                     │
│      def create_user(self, data):                       │
│          # Только то, что нужно                         │
│          pass                                           │
│                                                         │
│  Правила:                                               │
│  • Реализуй только текущие требования                   │
│  • Не угадывай будущее                                  │
│  • Добавляй функционал когда он реально нужен           │
│  • Удаляй неиспользуемый код                            │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Принципы связанности и зацепления

### Coupling (Связанность) — должна быть НИЗКОЙ

```
┌─────────────────────────────────────────────────────────┐
│                LOW COUPLING                             │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Coupling — степень зависимости между модулями          │
│  Чем меньше — тем лучше!                                │
│                                                         │
│  ❌ ВЫСОКАЯ связанность:                                │
│                                                         │
│  ┌─────────┐                                            │
│  │    A    │──────────────────────┐                     │
│  └────┬────┘                      │                     │
│       │                           │                     │
│  ┌────▼────┐     ┌─────────┐     │                     │
│  │    B    │────►│    C    │◄────┘                     │
│  └────┬────┘     └────┬────┘                           │
│       │               │                                 │
│       └───────►┌──────▼──────┐                         │
│                │      D      │                          │
│                └─────────────┘                          │
│                                                         │
│  Изменение D требует изменения A, B, C!                 │
│                                                         │
│  ✅ НИЗКАЯ связанность:                                 │
│                                                         │
│  ┌─────────┐     ┌─────────┐     ┌─────────┐           │
│  │    A    │     │    B    │     │    C    │           │
│  └────┬────┘     └────┬────┘     └────┬────┘           │
│       │               │               │                 │
│       └───────────────┼───────────────┘                 │
│                       ▼                                 │
│              ┌─────────────────┐                        │
│              │   Interface D   │                        │
│              └─────────────────┘                        │
│                                                         │
│  Модули зависят только от интерфейса!                   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Cohesion (Зацепление) — должно быть ВЫСОКИМ

```
┌─────────────────────────────────────────────────────────┐
│                HIGH COHESION                            │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Cohesion — насколько элементы модуля связаны           │
│             по смыслу и функциональности                │
│  Чем больше — тем лучше!                                │
│                                                         │
│  ❌ НИЗКОЕ зацепление (God Object):                     │
│                                                         │
│  class Utils:                                           │
│      def format_date(self): ...                         │
│      def send_email(self): ...                          │
│      def calculate_tax(self): ...                       │
│      def compress_image(self): ...                      │
│      def validate_phone(self): ...                      │
│                                                         │
│  Методы никак не связаны между собой!                   │
│                                                         │
│  ✅ ВЫСОКОЕ зацепление:                                 │
│                                                         │
│  class DateFormatter:                                   │
│      def format(self, date): ...                        │
│      def parse(self, string): ...                       │
│      def to_iso(self, date): ...                        │
│                                                         │
│  class EmailService:                                    │
│      def send(self, to, subject, body): ...             │
│      def send_template(self, to, template): ...         │
│      def validate_address(self, email): ...             │
│                                                         │
│  Каждый класс — одна тема!                              │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Закон Деметры (Law of Demeter)

```
┌─────────────────────────────────────────────────────────┐
│                  LAW OF DEMETER                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Правило: "Разговаривай только с друзьями"              │
│           Не лезь в чужие внутренности                  │
│                                                         │
│  ❌ ПЛОХО: Цепочки вызовов                              │
│                                                         │
│  order.get_customer().get_address().get_city()          │
│                                                         │
│  Проблемы:                                              │
│  • Order знает о структуре Customer и Address           │
│  • Изменение Address ломает код Order                   │
│                                                         │
│  ✅ ХОРОШО: Делегирование                               │
│                                                         │
│  order.get_shipping_city()                              │
│                                                         │
│  class Order:                                           │
│      def get_shipping_city(self):                       │
│          return self.customer.get_shipping_city()       │
│                                                         │
│  class Customer:                                        │
│      def get_shipping_city(self):                       │
│          return self.address.city                       │
│                                                         │
│  Аналогия: Если хочешь, чтобы собака побежала,          │
│            командуй собаке, а не её лапам!              │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Композиция vs Наследование

```
┌─────────────────────────────────────────────────────────┐
│            КОМПОЗИЦИЯ vs НАСЛЕДОВАНИЕ                   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Правило: Предпочитай композицию наследованию           │
│                                                         │
│  ❌ НАСЛЕДОВАНИЕ: Жёсткая связь                         │
│                                                         │
│  class Animal:                                          │
│      def move(self): ...                                │
│      def eat(self): ...                                 │
│                                                         │
│  class Bird(Animal):                                    │
│      def fly(self): ...                                 │
│                                                         │
│  class Penguin(Bird):  # Проблема! Пингвин не летает    │
│      def fly(self):                                     │
│          raise NotImplementedError()  # Костыль!        │
│                                                         │
│  ✅ КОМПОЗИЦИЯ: Гибкость                                │
│                                                         │
│  class FlyBehavior(ABC):                                │
│      @abstractmethod                                    │
│      def fly(self): ...                                 │
│                                                         │
│  class CanFly(FlyBehavior):                             │
│      def fly(self): print("Flying!")                    │
│                                                         │
│  class CannotFly(FlyBehavior):                          │
│      def fly(self): print("Can't fly")                  │
│                                                         │
│  class Bird:                                            │
│      def __init__(self, fly_behavior: FlyBehavior):     │
│          self.fly_behavior = fly_behavior               │
│                                                         │
│      def fly(self):                                     │
│          self.fly_behavior.fly()                        │
│                                                         │
│  eagle = Bird(CanFly())                                 │
│  penguin = Bird(CannotFly())                            │
│                                                         │
│  Когда использовать наследование:                       │
│  • Отношение "является" (is-a)                          │
│  • Подкласс действительно специализация                 │
│                                                         │
│  Когда использовать композицию:                         │
│  • Отношение "имеет" (has-a)                            │
│  • Нужна гибкость                                       │
│  • Поведение может меняться                             │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Ключевые термины

| Термин | Определение |
|--------|-------------|
| **SOLID** | 5 принципов ООП (SRP, OCP, LSP, ISP, DIP) |
| **SRP** | Single Responsibility — одна причина для изменения |
| **OCP** | Open/Closed — открыт для расширения, закрыт для изменения |
| **LSP** | Liskov Substitution — подклассы заменяемы на базовый |
| **ISP** | Interface Segregation — много маленьких интерфейсов |
| **DIP** | Dependency Inversion — зависи от абстракций |
| **DRY** | Don't Repeat Yourself — не дублируй код |
| **KISS** | Keep It Simple — делай проще |
| **YAGNI** | You Aren't Gonna Need It — не делай лишнего |
| **Coupling** | Связанность между модулями (должна быть низкой) |
| **Cohesion** | Зацепление внутри модуля (должно быть высоким) |

---

## Что запомнить

1. **SOLID** — база для хорошего ООП кода
2. **DRY** — не дублируй, но не переусердствуй с абстракциями
3. **KISS** — простое решение лучше сложного
4. **YAGNI** — не пиши код "на будущее"
5. **Low Coupling, High Cohesion** — модули независимы, но внутренне связны
6. **Композиция > Наследование** — гибче и проще

---

*Следующий файл: [12. Паттерны отказоустойчивости](12_resilience_patterns.md)*

