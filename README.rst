Asyncly
=======

.. image:: https://img.shields.io/pypi/v/asyncly.svg
   :target: https://pypi.python.org/pypi/asyncly/
   :alt: Latest Version

.. image:: https://img.shields.io/pypi/wheel/asyncly.svg
   :target: https://pypi.python.org/pypi/asyncly/

.. image:: https://img.shields.io/pypi/pyversions/asyncly.svg
   :target: https://pypi.python.org/pypi/asyncly/

.. image:: https://img.shields.io/pypi/l/asyncly.svg
   :target: https://pypi.python.org/pypi/asyncly/

Simple HTTP client and server for your integrations based on aiohttp_.

Installation
------------

Installation is possible in standard ways, such as PyPI or
installation from a git repository directly.

Installing from PyPI_:

.. code-block:: bash

   pip install asyncly

Installing from github.com:

.. code-block:: bash

   pip install git+https://github.com/andy-takker/asyncly

The package contains several extras and you can install additional dependencies
if you specify them in this way.

For example, with msgspec_:

.. code-block:: bash

   pip install "asyncly[msgspec]"

Complete table of extras below:

+------------------------------------------+-----------------------------------+
| example                                  | description                       |
+==========================================+===================================+
| ``pip install "asyncly[msgspec]"``       | For using msgspec_ structs        |
+------------------------------------------+-----------------------------------+
| ``pip install "asyncly[orjson]"``        | For fast parsing json by orjson_  |
+------------------------------------------+-----------------------------------+
| ``pip install "asyncly[pydantic]"``      | For using pydantic_ models        |
+------------------------------------------+-----------------------------------+
| ``pip install "asyncly[prometheus]"``    | To collect Prometheus_ metrics    |
+------------------------------------------+-----------------------------------+
| ``pip install "asyncly[opentelemetry]"`` | To collect OpenTelemetry_ metrics |
+------------------------------------------+-----------------------------------+

Quick start guide
-----------------

HttpClient
~~~~~~~~~~

Simple HTTP Client for `https://catfact.ninja`. See full example in `examples/catfact_client.py`_

.. code-block:: python

   from asyncly import DEFAULT_TIMEOUT, BaseHttpClient, ResponseHandlersType
   from asyncly.client.handlers.pydantic import parse_model
   from asyncly.client.timeout import TimeoutType


   class CatfactClient(BaseHttpClient):
       RANDOM_CATFACT_HANDLERS: ResponseHandlersType = MappingProxyType(
            {
                 HTTPStatus.OK: parse_model(CatfactSchema),
            }
       )

      async def fetch_random_cat_fact(
          self,
          timeout: TimeoutType = DEFAULT_TIMEOUT,
      ) -> CatfactSchema:
          return await self._make_req(
              method=hdrs.METH_GET,
              url=self._url / "fact",
              handlers=self.RANDOM_CATFACT_HANDLERS,
              timeout=timeout,
          )

Test Async Server for client
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pytest plugin (recommended)
***************************

Asyncly ships a pytest plugin auto-registered via entry-point. Override
``mock_routes`` to declare your test server's API surface, then use the
``mock_service`` fixture in tests:

.. code-block:: python

   import pytest
   from asyncly.srvmocker import JsonResponse, MockRoute


   @pytest.fixture
   def mock_routes():
       return [MockRoute("GET", "/fact", "random_catfact")]


   async def test_fetch_random_catfact(mock_service, catfact_client):
       mock_service.register(
           "random_catfact",
           JsonResponse({"fact": "test", "length": 4}),
       )
       fact = await catfact_client.fetch_random_cat_fact()
       assert fact.fact == "test"

The plugin removes the boilerplate of writing your own ``start_service``
fixture for each test module.

Manual fixture (without the plugin)
***********************************

If you prefer not to use the plugin (e.g. you need finer control over the
server lifetime), wire ``start_service`` yourself.

Example
*******

For the HTTP client, we create a server to which he will go and simulate real
responses. You can dynamically change the responses from the server in
a specific test.

Let's prepare the fixtures:

.. code-block:: python

   @pytest.fixture
   async def catafact_service() -> AsyncIterator[MockService]:
       routes = [
           MockRoute("GET", "/fact", "random_catfact"),
       ]
       async with start_service(routes) as service:
           service.register(
               "random_catfact",
               JsonResponse({"fact": "test", "length": 4}),
           )
           yield service


   @pytest.fixture
   def catfact_url(catafact_service: MockService) -> URL:
       return catafact_service.url


   @pytest.fixture
   async def catfact_client(catfact_url: URL) -> AsyncIterator[CatfactClient]:
       async with ClientSession() as session:
           client = CatfactClient(
               client_name="catfact",
               session=session,
               url=catfact_url,
           )
           yield client

Now we can use them in tests. See full example in `examples/test_catfact_client.py`_

.. code-block:: python

    async def test_fetch_random_catfact(catfact_client: CatfactClient) -> None:
        # use default registered handler
        fact = await catfact_client.fetch_random_cat_fact()
        assert fact == CatfactSchema(fact="test", length=4)


    async def test_fetch_random_catfact_timeout(
        catfact_client: CatfactClient,
        catafact_service: MockService,
    ) -> None:
        # change default registered handler to time error handler
        catafact_service.register(
            "random_catfact",
            LatencyResponse(
                wrapped=JsonResponse({"fact": "test", "length": 4}),
                latency=1.5,
            ),
        )
        with pytest.raises(asyncio.TimeoutError):
            await catfact_client.fetch_random_cat_fact(timeout=1)

How is this different from other mocking tools?
-----------------------------------------------

+----------------------+--------------------+----------------+------------------+---------------------+
| Tool                 | Mechanism          | Real HTTP      | Coupled to       | Best for            |
+======================+====================+================+==================+=====================+
| ``aioresponses``     | Patches aiohttp    | No             | aiohttp          | Fast unit tests     |
|                      | transport          |                |                  | without timeouts /  |
|                      |                    |                |                  | streaming           |
+----------------------+--------------------+----------------+------------------+---------------------+
| ``respx``            | Patches httpx      | No             | httpx            | Same as above for   |
|                      | transport          |                |                  | httpx               |
+----------------------+--------------------+----------------+------------------+---------------------+
| ``vcrpy`` (VCR.py)   | Record / replay    | Yes (on first  | aiohttp, httpx,  | When real API is    |
|                      | cassettes          | record)        | requests         | available           |
+----------------------+--------------------+----------------+------------------+---------------------+
| ``pytest-httpserver``| Real WSGI          | Yes            | Any              | Sync / mixed stacks |
|                      | server (werkzeug,  |                |                  | with rich           |
|                      | thread)            |                |                  | expectations API    |
+----------------------+--------------------+----------------+------------------+---------------------+
| ``asyncly.srvmocker``| Real aiohttp test  | Yes            | Any (best with   | Async aiohttp apps  |
|                      | server, same loop  |                | aiohttp)         | needing realistic   |
|                      |                    |                |                  | latencies / WS / SSE|
+----------------------+--------------------+----------------+------------------+---------------------+

The trade-off is realism vs. setup cost. Patching libraries are fastest but
miss sockets, real timeouts, header auto-injection, and serialization quirks.
Asyncly runs a real ``aiohttp.TestServer`` inside your test loop, catches
those classes of bugs, and pairs naturally with the bundled
``BaseHttpClient``.

When to pick something else:

- Pure unit tests of retry logic with dozens of cases — ``aioresponses`` or ``respx`` are cheaper.
- Sync codebase or you need WireMock-style expectations across HTTP clients — ``pytest-httpserver``.
- You have access to the real upstream and want golden recordings — ``vcrpy``.

Useful responses and serializers
--------------------------------

- JsonResponse_: simple JSON response from any object.
  You can setup status code and serializer for it. Using JsonSerializer_

- MsgpackResponse_: response in msgpack_ format with It's like JSON.
  But fast and small. Using MsgpackSerializer_.

- SequenceResponse_: useful response if you want return different responses
  on next request. Accepts BaseMockResponse_'s input.

- TimeoutResponse_: response with latency. For slow testing

- TomlResponse_: return TOML format text response. Using TomlSerializer_.

- YamlResponse_: return YAML format text response. Using YamlSerializer_.

Request matching with ``Match``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Multiple ``MockRoute``\ s can share ``(method, path)``; the request is
dispatched to the first route whose ``Match`` succeeds. Routes without a
``match=`` act as fallbacks and must be listed **last** in their group.

.. code-block:: python

   from asyncly.srvmocker import Match, MockRoute

   routes = [
       MockRoute("POST", "/items", "premium",
                 match=Match(headers={"X-Plan": "premium"})),
       MockRoute("POST", "/items", "basic",
                 match=Match(headers={"X-Plan": "basic"})),
       MockRoute("POST", "/items", "default"),  # fallback

   ]

``Match`` supports four predicates, all optional and combinable:

- ``json``: parsed body must equal this value exactly
- ``body``: raw body bytes must equal this value exactly
- ``headers``: every header listed must be present in the request (subset)
- ``query``: every query parameter listed must be present (subset)

If no route matches and there is no fallback, the server responds ``404``.

Asserting what your client sent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``MockService`` exposes helpers that read from the recorded request history:

.. code-block:: python

   async def test_creates_item(mock_service, client):
       mock_service.register("create", JsonResponse({"id": 1}))
       await client.create_item(name="Whiskers")

       mock_service.assert_called(
           "create",
           json={"name": "Whiskers"},
           headers={"Content-Type": "application/json"},
       )
       assert mock_service.last_call("create").body == b'{"name": "Whiskers"}'

Available methods:

- ``get_calls(name) -> list[RequestHistory]``
- ``last_call(name) -> RequestHistory`` (raises ``AssertionError`` if empty)
- ``assert_called(name, *, times=, json=, body=, headers=, query=)``
- ``assert_not_called(name)``

``RawResponse`` — malformed or arbitrary bytes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For testing client behavior on broken payloads, unexpected content types,
or empty bodies:

.. code-block:: python

   from asyncly.srvmocker import RawResponse

   mock_service.register(
       "broken_json",
       RawResponse(
           body=b'{"truncated":',
           status=200,
           headers={"Content-Type": "application/json"},
       ),
   )

HTTPS / TLS
~~~~~~~~~~~

Pass an ``ssl.SSLContext`` to ``start_service`` to serve over HTTPS.
``MockService.url`` will then report ``scheme="https"``.

.. code-block:: python

   import ssl
   from asyncly.srvmocker import start_service

   ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
   ctx.load_cert_chain("cert.pem", "key.pem")

   async with start_service(routes, ssl_context=ctx) as service:
       ...

Testing through a proxy
~~~~~~~~~~~~~~~~~~~~~~~

``BaseHttpClient`` accepts ``proxy`` and ``proxy_auth`` (forwarded to aiohttp_).
Set them once on the client, or override per request:

.. code-block:: python

   from aiohttp import BasicAuth, ClientSession
   from asyncly import BaseHttpClient

   async with ClientSession() as session:
       client = CatfactClient(
           url=url,
           session=session,
           client_name="catfact",
           proxy="http://127.0.0.1:8080",
           proxy_auth=BasicAuth("user", "secret"),
       )

To test that a client genuinely routes through a proxy, ``start_proxy`` spins
up an in-process forwarding HTTP proxy. It records every request passing
through it and forwards it to the real target (typically another
``start_service``). Pair it with the ``mock_proxy`` fixture or use it directly:

.. code-block:: python

   from aiohttp import BasicAuth, ClientSession
   from asyncly.srvmocker import (
       JsonResponse,
       MockRoute,
       start_proxy,
       start_service,
   )

   async def test_routes_through_proxy() -> None:
       routes = [MockRoute("GET", "/fact", "fact")]
       async with start_service(routes) as target:
           target.register("fact", JsonResponse({"fact": "ok"}))
           async with start_proxy(auth=BasicAuth("user", "secret")) as proxy:
               async with ClientSession() as s:
                   resp = await s.get(
                       target.url / "fact",
                       proxy=proxy.url,
                       proxy_auth=BasicAuth("user", "secret"),
                   )
                   assert (await resp.json()) == {"fact": "ok"}

           proxy.assert_called(times=1, method="GET")

``MockProxyService`` mirrors ``MockService``'s assertion helpers, reading from
the recorded history of forwarded requests:

- ``get_calls() -> list[RequestHistory]``
- ``last_call() -> RequestHistory`` (raises ``AssertionError`` if empty)
- ``assert_called(*, times=, target=, method=, json=, body=, headers=, query=)``
- ``assert_not_called()``

When ``start_proxy(auth=...)`` is set, requests missing or carrying a wrong
``Proxy-Authorization`` header get a ``407 Proxy Authentication Required`` and
are **not** forwarded. Only plain HTTP targets are supported (no ``CONNECT`` /
HTTPS tunnelling).

.. _PyPI: https://pypi.org/
.. _aiohttp: https://pypi.org/project/aiohttp/
.. _msgpack: https://msgpack.org
.. _msgspec: https://github.com/jcrist/msgspec
.. _orjson: https://github.com/ijl/orjson
.. _pydantic: https://github.com/pydantic/pydantic
.. _Prometheus: https://prometheus.io
.. _OpenTelemetry: https://opentelemetry.io

.. _examples/catfact_client.py: https://github.com/andy-takker/asyncly/blob/master/examples/catfact_client.py
.. _examples/test_catfact_client.py: https://github.com/andy-takker/asyncly/blob/master/examples/test_catfact_client.py

.. _BaseMockResponse: https://github.com/andy-takker/asyncly/blob/master/asyncly/srvmocker/responses/base.py
.. _JsonResponse: https://github.com/andy-takker/asyncly/blob/master/asyncly/srvmocker/responses/json.py
.. _MsgpackResponse: https://github.com/andy-takker/asyncly/blob/master/asyncly/srvmocker/responses/msgpack.py
.. _SequenceResponse: https://github.com/andy-takker/asyncly/blob/master/asyncly/srvmocker/responses/sequence.py
.. _TimeoutResponse: https://github.com/andy-takker/asyncly/blob/master/asyncly/srvmocker/responses/timeout.py
.. _TomlResponse: https://github.com/andy-takker/asyncly/blob/master/asyncly/srvmocker/responses/toml.py
.. _YamlResponse: https://github.com/andy-takker/asyncly/blob/master/asyncly/srvmocker/responses/yaml.py

.. _JsonSerializer: https://github.com/andy-takker/asyncly/blob/master/asyncly/srvmocker/serialization/json.py
.. _MsgpackSerializer: https://github.com/andy-takker/asyncly/blob/master/asyncly/srvmocker/serialization/msgpack.py
.. _TomlSerializer: https://github.com/andy-takker/asyncly/blob/master/asyncly/srvmocker/serialization/toml.py
.. _YamlSerializer: https://github.com/andy-takker/asyncly/blob/master/asyncly/srvmocker/serialization/yaml.py
