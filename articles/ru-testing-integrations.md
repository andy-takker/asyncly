Почти каждый сервис, который мы сегодня пишем, ходит куда-то наружу — платёжный шлюз, биллинг, чужой публичный API. И каждый раз, когда садимся писать тесты на этот код, упираемся в один и тот же вопрос: **как протестировать клиента, не ~~привлекая внимания санитаров~~ выходя в реальный мир?**

Эта статья про то, как выбирать инструмент под эту задачу. Не абстрактно — на одном маленьком, но ~~гордом~~ настоящем сервисе [`catfact-demo-service`](https://github.com/andy-takker/catfact-demo-service), в `tests/` которого рядом лежат пять способов протестировать одну и ту же интеграцию. К концу мы их сравним и аргументированно выберем тот, который оставили бы в production-проекте.

## Зачем мокать внешние интеграции?

Прежде чем выбирать инструмент — пара слов про то, **что мы вообще хотим проверять.**

Не сам внешний API. У нас нет ни прав, ни возможностей доказать, что условный catfact.ninja работает. А вот **наш клиент** — правильно ли он формирует запрос, корректно ли парсит ответ, разумно ли реагирует на 5xx, на таймауты, на битый JSON, делает ли ретраи с тем backoff'ом, который мы задумали, — это всё мы и хотим проверить. Исходим из того, что мы не в ответе за внешний сервис, а только за то, как мы можем реагировать на разные его состояния.

Чем ближе мы подбираемся к настоящему HTTP-обмену, тем больше классов ошибок ловим тестами. И тем дороже тест становится: по времени, по сложности фикстур, по нестабильности.

> Сразу насчет использования реального API - в CI этот вариант не годится. Он нестабилен — ушёл на обслуживание, у нас красный CI. У платных API каждый коммит превращается в расходы. В CI нет и не должно быть продакшен-секретов. На ранней стадии партнёрской интеграции реального API может вообще не существовать — клиент пишется параллельно с серверной стороной. Тест, зависящий от внешней погоды, — не тест, а лотерея. Поэтому мы сразу это отбрасываем.

Так что выбор всегда сводится к одному компромиссу: **какую часть реального HTTP-обмена мы готовы заменить макетом**, чтобы получить контроль. Чем больше реального HTTP остаётся в тесте — тем убедительнее зелёный CI. И тем дороже тест.

## На чём будем разбираться?

Представим себе небольшой веб-сервис с одной интеграцией. [catfact-demo-service](https://github.com/andy-takker/catfact-demo-service) — FastAPI-сервис с одним endpoint:

```http
GET /api/v1/catfact/daily-fact
```

Эндпоинт ходит во внешний `https://catfact.ninja/fact` и отдаёт случайный факт о кошках. Само по себе это вообще не задача - недо-прокси какой-то, но надо же тренироваться на кошках. Попробуем добавить ей типичных требований работы с внешним API:

- **Кеш 24 часа.** Не хотим дергать catfact.ninja на каждый запрос пользователя.
- **Retry с экспоненциальной задержкой.** Три попытки, `wait_exponential(multiplier=0.2, max=3)` через `tenacity`.
- **Graceful fallback на stale.** Все попытки провалились, а в кэше есть прошлый факт — отдадим его с `stale=true`. Нет вообще ничего — 503.

Архитектура — чистая, в духе одного [моего старого проекта](https://github.com/andy-takker/example-web-service):

```tree
catfact_service/
├── adapters/catfact/    # HTTP-клиент, кеш-обёртка, dishka-провайдер
├── domains/             # сущности, интерфейсы, use-case
└── presentors/rest/     # FastAPI-приложение
```

![Стрелочки туда, стрелочки сюда](https://www.plantuml.com/plantuml/svg/LL5TgnCn47tFhnZwUcdtAY9o4IdK3mKV1DSdzM5CfjtOx2HaPfL5_UycsRkmVMc7EH_dJFOeYbcdCPX0PmMDaFrbK70-arKVsSZLSyAC8zWufiZ4-bddG509o9T06ueCwE9lpnSuOv0jmj6HK8BdzvjbHhxMvOjxOnBQAru8TYaN8clCqfL9T_3707nzzwQ73fFlVZtfBEePhNOEVPZtTVmEA43iKlIivj_6pSKHFSlgGlgwYjuMpHUX4merwMGBMgIKYnl1XnDgfPo29zPAy7L_OumEK-7BskOnuOHs87UZ_yPz_n6UFXlW3aGnK7sSyACOjMpR54rxgxe39KRhTOPCckU5tS3Qn8OuETWDgaaUkhN6WJt_nAurQfSbqKmu6hC-3-pth-h1astJSbdxXPT_3uUrp_BNA4icF2mGZ5x4BBi6hn65yBxlFq7xLBM0CSSIEetXFm00)

Под капотом две вещи стоит сразу показать — обвязку retry и stale-фоллбэк, потому что именно за их поведением мы и охотимся на разных уровнях лестницы.

`CatFactClient` строится так, что `tenacity` оборачивается прямо в `__init__`: параметры backoff'а приходят из конфига, поэтому декоратор `@retry` на методе не годится — он бы заморозил параметры на момент описания класса. Применяем динамически:

```python
class CatFactClient:
    def __init__(self, config: CatFactConfig, session: aiohttp.ClientSession):
        self._config = config
        self._session = session
        self._get_random_fact_with_retry = retry(
            stop=stop_after_attempt(config.retry_attempts),
            wait=wait_exponential(
                multiplier=config.backoff_multiplier,
                max=config.backoff_max,
            ),
            retry=retry_if_exception_type(
                (aiohttp.ClientError, asyncio.TimeoutError, _UpstreamError)
            ),
            reraise=True,
        )(self._get_random_fact_once)
```

Поверх обёрнутого метода в `get_random_fact` ловим финальное исключение и оборачиваем в свой `CatFactUnavailable` — наружу из адаптера должны идти только доменные исключения.

`CachedCatFactClient` держит два слота: `_stored` с TTL — это сам кеш, и `_last_known` — последний удачный факт как страховка. Когда `_stored` протух, идём в реальный клиент; если он упал, и `_last_known` есть — возвращаем его, поднимая флаг `is_stale=True`:

```python
async def get_random_fact(self) -> tuple[CatFact, bool]:
    now = time.monotonic()
    if self._stored is not None:
        fact, expires_at = self._stored
        if now < expires_at:
            return fact, False  # cache hit, fresh

    try:
        fact, _ = await self._client.get_random_fact()
    except CatFactUnavailable:
        if self._stale_on_failure and self._last_known is not None:
            return self._last_known, True  # stale fallback
        raise

    self._stored = (fact, now + self._ttl)
    self._last_known = fact
    return fact, False
```

DI — `dishka`. Это станет важно на Уровне 1: клиента мы будем подменять через контекст контейнера, а не через `unittest.mock.patch`.

И чтобы не сравнивать яблоки с грушами, на каждом уровне мы прогоняем один и тот же целевой сценарий:

> Upstream первые два раза отвечает 503, на третий — 200 с JSON `{"fact": "...", "length": ...}`. Сервис должен сделать ровно 3 HTTP-запроса, вернуть 200 с этим фактом и `stale=false`, и записать факт в кеш.

В каждом из пяти файлов в [`tests/presentors/rest/api/v1/catfact/`](https://github.com/andy-takker/catfact-demo-service/tree/v1.0-article/tests/presentors/rest/api/v1/catfact) есть тест `test_anchor__retry_503_503_200__returns_fresh_and_caches`.

Помимо пяти ladder-файлов, в репо лежат ещё unit-тесты на каждый слой — `tests/adapters/catfact/` для самого клиента и кеш-обёртки, `tests/domains/use_cases/queries/` для use-case с фейковым `ICatFactClient`. В этой статье мы их не разбираем, фокусируемся на интеграционных через endpoint, но если хочется посмотреть, как тестируется каждый слой отдельно — они там.


## Лестница "реалистичности"

Аналогию с лестницей хочется провести, т. к. чем выше по ступенькам тем ближе мы к реальному запросу как это будет в продакшене, но для этого нужно написать больше обвязок и там на вершине есть свои подводные камни. Получилось пять уровней.

Если посмотреть на цепочку «endpoint → use-case → клиент → сокет → catfact.ninja» сверху вниз, то каждый уровень режет её на своей высоте:

!["Лестница"](https://www.plantuml.com/plantuml/svg/TLBBRXD14BplLxHoIenYYGTN56GK52c72CWD2GthYJruFRDCpoOo9sV3GmWKXCI7M5OM4lBW5tf-WI-XMqEiZQLSaXvFLNLLpMvWK3vKuoB3aR6byceCXR4wJ4eDpeUXQrtWKFNTWR43s5C5wYppEW_A3WeDAviAm-ETBT2sNpfZmmee1Dr6FDNXYJB5P5FbOHTrJw4M45Hjq5PF1G7q2gDjU6bNwPGkOqrDdCRtrD1PF5mJ5fWsQubq1vHnmn3ARlhbkKOqpWeFyZRlHMy7qEKZdUnYbXUkwiDAhi8UwtMjiM-KN87FCWthdDwkFsB7rM8scLdCUPOlPinmCJFPkg31cy4mWDjZ4a2ditqN-WQ78zNfy9d-q1MTq0Kr7FWR1wuXJlametFku1VDuaSwZSUClDaHq2ND04FrEkFkGHOjhylJkdjIYzTOEeiQhvVEOXq_iN8DDyhgllBwRQKntAgAIVK-xEU-d5pBDM8wVg0vYV0N-IzPaijuA3E7cdFM2pcUyz08ynJeYgzEcFQTuH8Pw3UV3eKaKhSQySd80oWdWGsloykZzllQTpgmUg3zw9sk1a1pYBMuuoNDMk8y18KJcnUJBlhzCNy9YVF_yqaKiGhqaneed2kPkFHKyJZM2NOUlxBbAzXzjWr_fp_4lxmTerAY4ucMGUf2eaj04jObDtMMwfdINFw2B16aDC3YlESpArt48u49KqevQfMomMCrBlu1)


### Уровень 1: подмена клиента через DI-контейнер (dishka)

**Файл:** [`test_level1_di_override.py`](https://github.com/andy-takker/catfact-demo-service/blob/main/tests/presentors/rest/api/v1/catfact/test_level1_di_override.py)

Самый дешёвый уровень — и самый слепой. HTTP мы тут вообще не трогаем. У dishka есть удобный механизм — `context`: пары «тип → готовый экземпляр», которые контейнер раздаёт по запросу как обычные зависимости. Production-`CatFactProvider` остаётся на месте, но поверх него мы прокидываем подмену для `ICatFactClient`. Use-case и endpoint про это не знают — для них контракт тот же:

```python
class StubCatFactClient:
    def __init__(self, sequence):
        self._sequence = list(sequence)
        self.call_count = 0

    async def get_random_fact(self) -> tuple[CatFact, bool]:
        self.call_count += 1
        item = self._sequence.pop(0) if self._sequence else CatFactUnavailable()
        if isinstance(item, Exception):
            raise item
        return item


stub = StubCatFactClient(sequence=[(CatFact(fact="Cats sleep a lot.", length=17), False)])
app = create_app(config=config, context_overrides={ICatFactClient: stub})
```

`create_app` пробрасывает `context_overrides` в `make_async_container(..., context=...)`, и stub получает приоритет над тем, что выдал бы `CatFactProvider.client(...)`. На целевом сценарии это **вырождается**: stub не идёт через `tenacity`, поэтому никаких «3 попытки на 503» не получится — `stub.call_count == 1`. Retry-логика живёт **внутри** настоящего клиента, а мы его целиком заменили.

Что L1 действительно умеет — это проверять бизнес-логику поверх клиента: маппинг исключений, формат ответа, fallback на stale. Showcase-тест `test_showcase__fallback_to_stale_marks_response_stale` ровно про это: stub рапортует `is_stale=True`, проверяем, что endpoint аккуратно прокидывает флаг в ответ.

> Если в проекте нет DI — есть вырожденный аналог через знакомый всем `patch.object(CachedCatFactClient, "get_random_fact", AsyncMock(...))`. Пример в [`test_appendix_unittest_mock.py`](https://github.com/andy-takker/catfact-demo-service/blob/v1.0-article/tests/presentors/rest/api/v1/catfact/test_appendix_unittest_mock.py). Работает, но привязывает тест к конкретному классу клиента — переименовали или вынесли в другой модуль, поправили тест. Когда DI уже есть, тратить эту привязку незачем.


### Уровень 2: патч транспорта (`aioresponses`)

**Файл:** [`test_level2_aioresponses.py`](https://github.com/andy-takker/catfact-demo-service/blob/v1.0-article/tests/presentors/rest/api/v1/catfact/test_level2_aioresponses.py)

[`aioresponses`](https://github.com/pnuckowski/aioresponses) патчит `aiohttp.ClientSession._request`. Наш `CatFactClient` об этом не знает: для него `aiohttp` работает обычно, только за кулисами `_request` отдаёт заготовленный ответ.

Наш тест на L2:

```python
with aioresponses() as m:
    m.get("https://catfact.ninja/fact", status=503)
    m.get("https://catfact.ninja/fact", status=503)
    m.get("https://catfact.ninja/fact", payload={"fact": "...", "length": 17})
    resp = await rest_client.get("/api/v1/catfact/daily-fact")
assert resp.status_code == 200
```

`tenacity.retry` сидит вокруг `_get_random_fact_once`, на каждом 503 он делает `await asyncio.sleep(0.2)` → `sleep(0.4)`, на третий раз приходит 200. Снаружи всё выглядит как в проде.

Пара важных вещей этим уровнем сами по себе не подтверждаются. Реальный backoff-таймминг — `tenacity` действительно спит, но настоящего сокета между попытками нет, и сам факт правильных интервалов L2 не доказывает. На практике это лечится отдельным структурным тестом на конфигурацию tenacity — assert на параметры `wait_exponential`, например, — просто не стоит ждать от aioresponses доказательства, что backoff работает в сети. То же с реальным таймаутом: `aiohttp.ClientTimeout` имеет смысл только когда есть сокет, а у `aioresponses` его нет, и поведение «клиент бросает `TimeoutError` через секунду» проверяется на следующих уровнях. И вся обвязка `aiohttp` — дефолтные заголовки, gzip, кодировка multipart-boundary — добавляется на уровне настоящего запроса, который у нас не происходит.

Зато на L2 очень дёшево гонять сотни happy-path кейсов: разные комбинации JSON, разные параметры запроса, разные коды ответа. Юнит-тесты, которые в CI крутятся 100500 раз в день, на `aioresponses` сэкономят секунды на каждом прогоне.

Аналогичный уровень для `httpx` — [`respx`](https://github.com/lundberg/respx) или встроенный `httpx.MockTransport`. Идея та же (патч транспорта, без настоящего сокета), отличия — в DSL.

### Уровень 3: запись/воспроизведение (`vcrpy`)

**Файл:** [`test_level3_vcrpy.py`](https://github.com/andy-takker/catfact-demo-service/blob/v1.0-article/tests/presentors/rest/api/v1/catfact/test_level3_vcrpy.py)

[`vcrpy`](https://github.com/kevin1024/vcrpy) — другая философия. Первый прогон идёт в живой API, ответ сохраняется в YAML-«кассету», все последующие прогоны эту кассету воспроизводят. У vcrpy 6.x поддержка `aiohttp` работает — проверили на aiohttp 3.13 + Python 3.14. Совместимость со свежими версиями всегда стоит перепроверять, но прямо сейчас всё в порядке.

Целевой сценарий плохо ложится на естественный use case vcrpy. Технически кассету `503 → 503 → 200` можно написать руками — но это уже YAML-мок, а не «запись живого взаимодействия», и идея golden-snapshot теряется. Поэтому на L3 целевого теста нет, только showcase:

```python
@vcr.use_cassette("tests/presentors/rest/api/v1/catfact/cassettes/daily_fact_happy.yaml")
async def test_showcase__golden_response_parses_correctly(rest_client):
    resp = await rest_client.get("/api/v1/catfact/daily-fact")
    assert resp.json() == {"fact": "...", "length": 38, "stale": False}
```

Сильная сторона у L3 одна, но очень нужная: golden-snapshot против стабильных публичных API без авторизации (как `catfact.ninja`). Заголовки руками выписывать не надо, ответ берётся как из жизни. А слабости накапливаются. Кассеты протухают — API эволюционирует, поле исчезает, кассета остаётся зелёной, пока кто-то её не перезапишет. Тестировать ошибки невозможно: чтобы записать 503, нужно живое 503. Секреты могут утечь в репо — у vcrpy есть `filter_headers` / `before_record_response`, но это нужно сесть и настроить заранее.

### Уровень 4: настоящий HTTP-сервер в треде (`pytest-httpserver`)

**Файл:** [`test_level4_httpserver.py`](https://github.com/andy-takker/catfact-demo-service/blob/v1.0-article/tests/presentors/rest/api/v1/catfact/test_level4_httpserver.py)

[`pytest-httpserver`](https://github.com/csernazs/pytest-httpserver) поднимает настоящий HTTP-сервер на werkzeug в отдельном треде. Это уже реальный сокет: клиент действительно открывает соединение, действительно ждёт ответа, действительно встречается с таймаутом.

Целевой тест работает в полной форме:

```python
httpserver.expect_oneshot_request("/fact").respond_with_data(status=503)
httpserver.expect_oneshot_request("/fact").respond_with_data(status=503)
httpserver.expect_oneshot_request("/fact").respond_with_json({"fact": "...", "length": 17})

resp = await rest_client.get("/api/v1/catfact/daily-fact")

assert resp.status_code == 200
assert len(httpserver.log) == 3
```

Showcase — настоящий timeout. Хендлер делает `time.sleep(2.0)` в треде werkzeug, клиентский timeout=1.0, `tenacity` ловит `asyncio.TimeoutError` три раза подряд → endpoint отдаёт 503. Это поведенческий тест, а не структурный: мы не патчим время, мы реально его проживаем.

Минус один и не очень страшный: werkzeug в треде. Для async-кода это не блокер — event loop + thread + GIL работают корректно, — но в одном тесте у вас живут две модели исполнения, и фикстура `httpserver` сама синхронная. Плюс DSL у `pytest-httpserver` свой, не совпадает ни с aiohttp, ни с `asyncly.srvmocker`: если в проекте уже используется один стиль, команде придётся осваивать второй.

L4 идеален для sync-кодбейсов, смешанных стеков и когда нужны WireMock-style expectations — «эта ручка должна быть вызвана 3 раза с такими-то заголовками».


### Уровень 5: настоящий aiohttp-сервер в том же event loop

**Файл:** [`test_level5_srvmocker.py`](https://github.com/andy-takker/catfact-demo-service/blob/v1.0-article/tests/presentors/rest/api/v1/catfact/test_level5_srvmocker.py)

Та же реалистичность, что у `pytest-httpserver`, **только без потока**. Берём `aiohttp.test_utils.TestServer`, поднимаем в том же event loop, что и тест, и направляем на него `CatFactClient`. Один процесс, один loop — всё как в проде, никакой межпоточной синхронизации, async-фикстуры работают как обычно.

Чтобы было понятно, что под капотом, — вот как это выглядит на чистом aiohttp, без всяких обёрток:

```python
from aiohttp import web
from aiohttp.test_utils import TestServer

call_count = 0

async def get_fact(_request):
    global call_count
    call_count += 1
    if call_count <= 2:
        return web.Response(status=503)
    return web.json_response({"fact": "Cats sleep a lot.", "length": 17})

app = web.Application()
app.router.add_get("/fact", get_fact)

async with TestServer(app) as server:
    # подменяем CatFactConfig.url на str(server.make_url('')).rstrip('/')
    # прогоняем сценарий через endpoint
    # проверяем call_count == 3
    ...
```

Это работает и реально проверяет всё, что нам нужно: настоящий сокет, настоящие таймауты, настоящий счётчик попыток. Цена — каждый тест пишется примерно так: глобальные счётчики, ручная конфигурация роутов, ручная подмена URL в конфиге, ручная проверка количества вызовов. На один тест — нормально. На двадцать — больно.

Чтобы этот бойлерплейт писать один раз, я в своё время сделал [`asyncly.srvmocker`](https://github.com/andy-takker/asyncly) — маленький слой DSL поверх `aiohttp.test_utils.TestServer`. Тот же целевой сценарий через него:

```python
catfact_service.register(
    "get_fact",
    SequenceResponse([
        ContentResponse(status=503),
        ContentResponse(status=503),
        JsonResponse({"fact": "Cats sleep a lot.", "length": 17}),
    ]),
)

resp = await rest_client.get("/api/v1/catfact/daily-fact")

assert resp.status_code == 200
assert resp.json() == {"fact": "Cats sleep a lot.", "length": 17, "stale": False}
catfact_service.assert_called("get_fact", times=3)
```

`SequenceResponse` описывает «вот так ответь в первый раз, вот так во второй, вот так в третий» — без глобальных счётчиков. `assert_called(times=3)` — то, что мы вручную делали через переменную. URL мок-сервиса прокидывается через фикстуру, а сам сервис — через `start_service(routes)` под капотом, и каждый тест получает свежий.

В файле есть ещё несколько showcase-тестов на штуки, которые на других уровнях принципиально не работают.

Реальный таймаут — через `LatencyResponse`. Оборачиваем любой ответ, добавляется настоящий `await asyncio.sleep(latency)`. Клиент с таймаутом 1.0 действительно бросит `asyncio.TimeoutError` через секунду, потому что секунда действительно прошла. (Мелкая ремарка для въедливого читателя: в 0.6.2 `LatencyResponse` приходится импортировать как `from asyncly.srvmocker.responses.timeout import LatencyResponse`, а не из верха пакета — в 0.6.3 это будет исправлено.)

Битый JSON — через `RawResponse`. Отдаём `b'{"fact": "truncated'`, обрезанные байты, `msgspec.json.decode` падает, `tenacity` это не ретраит (parse-ошибка не в списке retriable), endpoint отдаёт 500. Так ловятся реальные баги клиента по битому payload'у.

Условные ответы — через `Match`. Один и тот же путь, два разных response в зависимости от заголовков/тела/query: premium-юзер получает один факт, бесплатный — другой. В эндпоинте `daily-fact` тело запроса пустое и `Match` к нему напрямую не приклеится, поэтому отдельный showcase запускает второй mock-сервис специально для демонстрации. Это нормальный паттерн: репозиторий — полигон, а не дисциплинированный unit test.

И assertions — `assert_called` / `last_call` / `get_calls`. Можно спросить мок-сервис, что именно ему пришло. Те же предикаты `json` / `body` / `headers` / `query`, что и в `Match`, — симметрия сознательная.

> Все бы у этого уровня хорошо, но есть одна подстава - в некоторых фреймворках реализуют собственный клиент поверх клиента из `httpx` для тестирования и используют [start_blocking_portal](https://anyio.readthedocs.io/en/stable/threads.html#starting-a-blocking-portal) из библиотеки `anyio` ([например, в AsyncTestClient из Litestar](https://github.com/litestar-org/litestar/blob/f45503f546c18052a9d7f0be3ba826b45f198be3/litestar/testing/client/base.py#L9)). Из-за этого когда мы проваливаемся в работу этого клиента в фикстуре или тесте, то мы работаем в другом потоке и не можем получить ответ от сервера, который запущен в основном event loop.
>
> Обычно это используется для синхронных тестов, чтобы можно было работать с асинхронным приложением (например, в FastStream), а именно в Litestar почему-то

---

## Сравнительная таблица

Что каждый уровень способен реально проверить в нашем целевом сценарии:

| Уровень | 3 запроса? | Реальный backoff-таймминг? | Реальный timeout? | Битый JSON? | End-to-end через FastAPI? |
|---------|:---:|:---:|:---:|:---:|:---:|
| L1: dishka override | ❌ | ❌ | ❌ | ❌ | ✅ (без HTTP-стека) |
| L2: aioresponses | ✅ | ❌ | ❌ | ⚠️ | ⚠️ |
| L3: vcrpy |  ⚠️ (только записанное) | ❌ | ❌ | ❌ | ⚠️ |
| L4: pytest-httpserver | ✅ | ✅ | ✅ | ✅ | ✅ |
| L5: asyncly.srvmocker |  ✅ | ✅ | ✅ | ✅ | ✅ |

> ⚠️ означает «технически возможно частично, но не как полноценная проверка реального HTTP/wire-level поведения». Битый JSON у L2 можно эмулировать payload'ом, но настоящую обрезку байтов на проводе — нет; у L3 «три запроса» работают только если вы вручную записали кассету с тремя interactions; end-to-end у L2/L3 идёт через FastAPI, но HTTP-стек на пути не задействуется.

Главный размен — **реалистичность против цены**. Чем выше по таблице — тем дешевле один тест и тем больше классов ошибок он пропускает.

### Что выбрать в реальном проекте

- **Бизнес-логика поверх клиента без HTTP** (use-case, маппинг, fallback) → DI override.
- **Десятки–сотни дешёвых JSON / happy-path кейсов** → `aioresponses` (aiohttp) или `respx` / `httpx.MockTransport` (httpx).
- **Golden-snapshot стабильного публичного API** → `vcrpy`.
- **Retry / timeout / wire-level поведение в sync или смешанном стеке** → `pytest-httpserver`.
- **То же самое в чистом async-проекте без отдельного thread** → `asyncly.srvmocker` (или собственная обёртка над `aiohttp.test_utils`).

На практике в одном проекте обычно сосуществуют 2–3 уровня: DI override для бизнес-логики плюс один из «настоящих» уровней для интеграционных тестов клиента. Лестница — это не последовательный выбор «либо то, либо это», а спектр инструментов под разные классы тестов.

---

## Глубокое погружение в `asyncly.srvmocker`

Дальше — подробнее про сам `asyncly.srvmocker`. Это мой инструмент и тот уровень, на котором я в итоге останавливаюсь в продакшен-коде, поэтому я знаю его лучше других. Не серебряная пуля и не универсальная замена остальным четырём уровням — конкретный DSL поверх `aiohttp.test_utils`, чтобы тесты на L5 не превращались в копипасту. Если вы для себя выбрали другой уровень, секцию можно пролистать к следующей.

Все примеры здесь — реальные тесты из [`test_level5_srvmocker.py`](https://github.com/andy-takker/catfact-demo-service/blob/v1.0-article/tests/presentors/rest/api/v1/catfact/test_level5_srvmocker.py) или из его зеркала в [`example-web-service`](https://github.com/andy-takker/example-web-service/tree/master/tests/adapters/open_library). Код в статью переписывать не буду — буду ссылаться. А по каждому ключевому концепту дам кратко: что и зачем.

### Pytest-плагин: `mock_routes` + `mock_service`

Плагин регистрируется через entry-point. Достаточно в `conftest.py` подключить `tests.plugins.instances.catfact` (или ваш аналог), переопределить фикстуру `mock_routes`, и в тестах вы получаете рабочий `MockService` без бойлерплейта старта-стопа.

### `SequenceResponse` для ретраев

`SequenceResponse([resp1, resp2, resp3])` возвращает разные ответы на каждый последующий запрос. Параметр `on_exhausted` управляет тем, что произойдёт после исчерпания списка:

- `"raise"` (по умолчанию) — на N+1-й запрос летит `SequenceExhausted`. Лучше для целевого теста: если клиент случайно сделал четвёртый запрос, тест упадёт.
- `"cycle"` — после последнего начинается с начала. Удобно для polling-сценариев.
- `"last"` — после последнего возвращает его и дальше.

### `LatencyResponse` для реальных таймаутов

```python
LatencyResponse(wrapped=JsonResponse({"fact": "..."}), latency=2.0)
```

Делает настоящий `await asyncio.sleep(2.0)` перед тем, как отдать обёрнутый ответ. Это **не выдуманное** время — клиент с таймаутом 1.0 действительно бросит `asyncio.TimeoutError`.

### `RawResponse` для битых ответов

```python
RawResponse(body=b'{"fact": "abc', headers={"Content-Type": "application/json"})
```

Тестирует устойчивость к мусору: обрезанный JSON, content-type не совпадает с телом, не-UTF8 байты — всё то, на чём обычно валится клиент в проде.

### `Match` для условных ответов

```python
MockRoute("POST", "/echo", "premium", match=Match(headers={"X-Plan": "premium"}))
MockRoute("POST", "/echo", "free")  # fallback, обязательно последним
```

`Match` поддерживает четыре предиката, все опциональные:

- `json` — распарсенное тело должно совпадать полностью.
- `body` — сырое тело должно совпадать побайтово.
- `headers` — подмножество заголовков должно присутствовать.
- `query` — подмножество query-параметров должно присутствовать.

### `assert_called` / `last_call` / `get_calls`

```python
mock_service.assert_called("create_item", json={"name": "Whiskers"}, times=1)
last = mock_service.last_call("get_fact")
all_calls = mock_service.get_calls("get_fact")
```

`json` и `body` — strict equality; `headers` и `query` — subset. Симметрично с `Match`, и это сделано сознательно.

### HTTPS

`start_service(routes, ssl_context=ctx)` поднимает сервер на HTTPS. `MockService.url` будет с `scheme="https"`.

---

## Когда `asyncly.srvmocker` не нужен

Я писал asyncly под свои задачи и стараюсь не агитировать за него там, где он лишний.

Sync-код проекту asyncly бессмысленен — у вас нет event loop'а, и вы ничего не выиграете от «всё в одном loop'е». Берите [`pytest-httpserver`](https://github.com/csernazs/pytest-httpserver) или [`responses`](https://github.com/getsentry/responses).

Массовые юнит-тесты «счастливых путей» — тоже не сюда. Сотни кейсов парсинга разных полей JSON выгоднее гонять через `aioresponses` или `respx`. Старт настоящего сервера на каждый тест начинает реально влиять на CI, когда тестов несколько сотен.

Golden-snapshot против стабильного публичного API — это `vcrpy`. Записал, ходишь, и пока API не меняется, всё работает. Но не всем нравится думать о поддержке отдельных yaml файлов для это.

WireMock-style expectations поверх нескольких HTTP-клиентов одновременно в одном тесте — лучше у `pytest-httpserver`. В asyncly один `MockService` — один сервер; несколько серверов поднимаются через несколько `start_service` руками, и expectations-DSL у asyncly проще.

Если вы вообще не используете aiohttp в проекте — `asyncly.srvmocker` тянет с собой `aiohttp.test_utils.TestServer`. Клиент-сторону можно держать на чём угодно (httpx, requests), но зависимость от aiohttp в dev-окружении остаётся. На голом FastAPI без aiohttp в dependencies это лишний вес — выберите `respx`/`httpx.MockTransport` для транспортного уровня и `pytest-httpserver` для wire-level.

Mock-server-как-сервис между несколькими микросервисами в docker-compose — это [WireMock](https://wiremock.org/) или [Mockoon](https://mockoon.com/), не asyncly. asyncly — внутрипроцессный инструмент.

Если ни одна из этих ситуаций — не ваша, и вы пишете async-приложение на aiohttp/httpx-async, и хотите тестировать клиентов с реальным HTTP-обменом, — `asyncly.srvmocker` должен подойти.

---

## Итог

Главная мысль этой лестницы простая: не нужно выбирать один мок-инструмент навсегда. Выбирайте уровень реалистичности под риск конкретного теста: бизнес-логику проверяйте дешёво, сетевые эффекты — настоящим HTTP.

И еще раз ссылки:

- **Демо-репозиторий:** [github.com/andy-takker/catfact-demo-service](https://github.com/andy-takker/catfact-demo-service) — пять файлов с тестами, по которым прошлись в этой статье.
- **asyncly:** [github.com/andy-takker/asyncly](https://github.com/andy-takker/asyncly) · [PyPI](https://pypi.org/project/asyncly/) · [CHANGELOG](https://github.com/andy-takker/asyncly/blob/master/CHANGELOG.md)
- **Альтернативные инструменты:**
  - [aioresponses](https://github.com/pnuckowski/aioresponses) · [respx](https://github.com/lundberg/respx) · [responses](https://github.com/getsentry/responses)
  - [vcrpy](https://github.com/kevin1024/vcrpy)
  - [pytest-httpserver](https://github.com/csernazs/pytest-httpserver)
  - [WireMock](https://wiremock.org/) · [Mockoon](https://mockoon.com/) (как stand-alone сервисы)

Если статья оказалась полезной — лучшая обратная связь это звезда на репо и issue с тем, чего вам не хватает. Спасибо за чтение.
