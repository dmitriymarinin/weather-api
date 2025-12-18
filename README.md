# [Weather Service](https://github.com/dmitriymarinin/weather-api.git)
__Пример решения задачи [weather-api-wrapper-service](https://roadmap.sh/projects/weather-api-wrapper-service) с сайта [roadmap.sh](https://roadmap.sh/).__

Простой API погоды на Python с использованием FastAPI, внешнего сервиса Visual Crossing и кэша в Redis.  
Проект показывает, как работать со сторонними API, кэшированием и переменными окружения, а также запускать сервис в Docker/Docker Compose.

---

### Стек

- **Python** + **FastAPI**
- **Visual Crossing Weather API** (внешний поставщик данных)
- **Redis** для кэширования
- **Docker** и **docker-compose** для оркестрации
- **slowapi** для ограничения частоты запросов (rate limiting)

---

### Как запустить

1. **Склонировать репозиторий:**

  
   git clone https://github.com/dmitriymarinin/weather-api.git
   cd weather-api
   2. **Создать файл `.env` в корне проекта:**

  
   VISUALCROSSING_API_KEY=ваш_ключ_из_Visual_Crossing
   CACHE_TTL_SECONDS=43200
   3. **Запустить сервисы через Docker Compose:**

  
   docker-compose up --build
   После запуска:

- API доступно по адресу: `http://localhost:8000`
- Redis работает как отдельный сервис и доступен внутри сети Docker по имени `redis`

---

### Основные эндпоинты

- **GET** `/health`  
  Проверка состояния сервиса.  
  **Пример ответа:**
 
  { "status": "ok" }
  - **GET** `/weather`  
  Получить текущую погоду по городу (и опционально, стране).

  **Параметры:**
  - `city` – обязательный, название города или код (например, `Moscow`)
  - `country` – необязательный, код страны (например, `RU`, `US`)

  **Пример запроса:**
 
  GET http://localhost:8000/weather?city=Moscow&country=RU
    **Пример ответа:**
 
  {
    "city": "Moscow, Russia",
    "country": "RU",
    "temperature_c": 5.2,
    "conditions": "Partially Cloudy",
    "humidity": 78.0,
    "wind_kph": 12.3,
    "source": "live"
  }
  При повторных запросах с теми же параметрами `city`/`country` данные берутся из Redis-кэша (поле `source` будет `"cache"`), пока кэш не истечёт.