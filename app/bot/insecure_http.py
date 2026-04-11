import json
import aiohttp


class InsecureAiohttpClient:
    """
    Аварийный HTTP-клиент для vkbottle:
    - отключает проверку SSL (ssl=False)
    - реализует request_text и request_json, как ожидает vkbottle
    """

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(ssl=False)
            self._session = aiohttp.ClientSession(connector=connector)
        return self._session

    async def request_text(self, url: str, method: str = "POST", data=None, **kwargs) -> str:
        session = await self._get_session()
        async with session.request(url=url, method=method, data=data, **kwargs) as resp:
            return await resp.text()

    async def request_json(self, url: str, method: str = "POST", data=None, **kwargs):
        text = await self.request_text(url=url, method=method, data=data, **kwargs)
        return json.loads(text)