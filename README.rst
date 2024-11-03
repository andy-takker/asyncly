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

+-------------------------------------+----------------------------------+
| example                             | description                      |
+=====================================+==================================+
| ``pip install "asyncly[msgspec]"``  | For using msgspec_ structs       |
+-------------------------------------+----------------------------------+
| ``pip install "asyncly[orjson]"``   | For fast parsing json by orjson_ |
+-------------------------------------+----------------------------------+
| ``pip install "asyncly[pydantic]"`` | For using pydantic_ models       |
+-------------------------------------+----------------------------------+

Quick start guide
-----------------

HttpClient
~~~~~~~~~~~~~~

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


.. _PyPI: https://pypi.org/
.. _aiohttp: https://pypi.org/project/aiohttp/
.. _msgspec: https://github.com/jcrist/msgspec
.. _orjson: https://github.com/ijl/orjson
.. _pydantic: https://github.com/pydantic/pydantic

.. _examples/catfact_client.py: https://github.com/andy-takker/asyncly/blob/master/examples/catfact_client.py
.. _examples/test_catfact_client.py: https://github.com/andy-takker/asyncly/blob/master/examples/test_catfact_client.py