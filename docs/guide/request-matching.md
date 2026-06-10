# Request matching

Multiple [`MockRoute`](mock-server.md#declaring-routes)s can share the same
`(method, path)`. When a request arrives, it is dispatched to the **first** route
whose [`Match`][asyncly.srvmocker.Match] succeeds. This lets one endpoint return
different responses depending on the request.

```python
from asyncly.srvmocker import Match, MockRoute

routes = [
    MockRoute("POST", "/items", "premium",
              match=Match(headers={"X-Plan": "premium"})),
    MockRoute("POST", "/items", "basic",
              match=Match(headers={"X-Plan": "basic"})),
    MockRoute("POST", "/items", "default"),  # fallback — no match=
]
```

## Predicates

`Match` supports four optional, combinable predicates:

| Predicate | Matches when |
| --- | --- |
| `json` | the parsed JSON body equals this value **exactly** |
| `body` | the raw body bytes equal this value **exactly** |
| `headers` | every listed header is present in the request (**subset**) |
| `query` | every listed query parameter is present (**subset**) |

When several predicates are given, **all** must hold for the route to match:

```python
Match(headers={"X-Plan": "premium"}, query={"region": "eu"})
```

## Fallbacks and ordering

A route with no `match=` always matches, so it acts as a **fallback**. Order
matters: routes are tried top to bottom, so list specific matches first and the
fallback **last** within a `(method, path)` group.

If no route matches and there is no fallback, the server responds with `404`.

## Example

```python
async def test_plan_routing(mock_service) -> None:
    mock_service.register("premium", JsonResponse({"tier": "premium"}))
    mock_service.register("basic", JsonResponse({"tier": "basic"}))
    mock_service.register("default", JsonResponse({"tier": "anonymous"}))

    # a request with X-Plan: premium is dispatched to the "premium" handler
```

!!! note
    `Match` defensively copies the `headers` and `query` dicts at construction,
    so mutating the original dict afterwards never affects matching.
