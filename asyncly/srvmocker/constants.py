from aiohttp.web import AppKey

from asyncly.srvmocker.models import MockService

SERVICE_KEY = AppKey("service", MockService)
