# Дорожная карта развития Asyncly

## Summary

Развивать Asyncly как aiohttp-first toolkit из двух связанных глубоких модулей:

- `srvmocker` воспроизводит реальные сетевые условия через локальный `aiohttp.TestServer`.
- `BaseHttpClient` предоставляет небольшие composable policies для устойчивого поведения клиента.
- Каждая клиентская возможность принимается только вместе с socket-level сценарием, который её проверяет. Такой подход соответствует рекомендации aiohttp тестировать внешние интеграции через локальный fake server, а не патчить transport internals ([aiohttp testing documentation](https://docs.aiohttp.org/en/stable/testing.html)).
- Текущая baseline: версия 0.8.0, 98 тестов проходят.

## Первый вертикальный срез: retries и transport faults

- Добавить `RetryPolicy`, передаваемый явно в `_make_req(..., retry=...)`; без policy поведение полностью совпадает с текущим.
- Policy определяет максимальное число попыток, retryable statuses/exceptions, допустимые методы, backoff и обработку `Retry-After`.
- Безопасные defaults: только идемпотентные HTTP-методы; cancellation не повторяется; streaming/non-replayable body подавляет retry с наблюдаемой причиной.
- Последний HTTP response обрабатывается существующим status handler; последняя transport exception пробрасывается без новой обёртки.
- Добавить `DisconnectResponse()` для разрыва до headers и `TruncatedResponse` для неполного body. Status-based сценарии строить существующими `SequenceResponse` и `RawResponse`.
- Каждую попытку учитывать как отдельный физический request. Необязательный retry observer сообщает `scheduled`, `suppressed` и `exhausted`.

## Публичные interfaces и 1.0 cleanup

- Ввести неизменяемые `RetryPolicy`, `RetryContext` и `RetryEvent`; backoff задавать callable-стратегией, чтобы тесты могли отключить jitter и реальное ожидание.
- Не вводить общий middleware pipeline: retry orchestration остаётся внутри клиента, instrumentation оборачивает отдельную попытку.
- Заменить живой `aiohttp.BaseRequest` в истории на immutable `RecordedRequest` с method, URL/path, headers, query, path params, body и выбранным handler. В 0.9 оставить deprecated alias `RequestHistory`.
- Включить строгую регистрацию handlers: неизвестное имя вызывает `UnknownHandlerError`, а отсутствие response у выбранного route даёт диагностируемую ошибку вместо `KeyError`.
- Экспортировать рекомендуемые response primitives, включая `LatencyResponse`, непосредственно из `asyncly.srvmocker`.
- До фактической реализации убрать из документации обещание специальной поддержки SSE/WebSocket.

## Последующие вертикальные срезы

1. **Streaming и cancellation:** `ChunkedResponse`, управляемые паузы/обрывы, `SseResponse`, handlers для byte stream, NDJSON и SSE, корректный cleanup при cancellation и early break.
2. **Auth lifecycle:** `CallbackResponse`, stateful mock-сценарии expiry/refresh, клиентский `AuthProvider` и single-flight refresh конкурентных запросов.
3. **Async test ergonomics:** `await wait_for_call(...)`, assertions порядка запросов, подробные mismatch diffs, matchers для cookies/path params/custom predicates.
4. **Отложить до подтверждённого спроса:** универсальную pagination abstraction, OpenAPI codegen, record/replay, WebSocket subsystem, httpx adapter и transport-neutral core.

## Test Plan

- Unit-тесты policy: method safety, лимит попыток, status/exception filters, оба формата `Retry-After`, backoff, cancellation и replayability body.
- Socket-level тесты: `503→200`, `429→200`, disconnect→success, truncated body→success/exhaustion, освобождение response между попытками.
- Проверить конкурентное использование одной immutable policy без общего attempt state.
- Проверить отдельные метрики физических requests и logical retry events, включая практически бесплатный Noop path.
- Для каждого следующего среза требовать end-to-end тест через реальный сокет.
- Acceptance gate: текущие тесты после миграционных корректировок, новые тесты, ruff, mypy и strict docs build проходят.

## Assumptions

- Проект остаётся aiohttp-first и Python 3.10+.
- До 1.0 допустим контролируемый cleanup публичного interface через deprecation-период 0.9.
- Приоритет — composable primitives, а не высокоуровневые batteries-included workflows.
- Первый релиз новой линии ограничен retries, fault injection, диагностикой и необходимым 1.0 cleanup.
