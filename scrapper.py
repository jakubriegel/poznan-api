from bs4 import BeautifulSoup
from requests import Response, adapters, RequestException
from requests_html import AsyncHTMLSession, HTMLResponse
from typing import Dict, Set, Tuple, List
import time
import util
import asyncio

DeparturesRow = Tuple[str, str, str]
StopRow = Tuple[List[DeparturesRow], int, int]
StopsDict = Dict[str, StopRow]


class Scrapper:

    VM_URL = 'http://www.peka.poznan.pl/vm'

    TEST_URL = 'https://httpbin.org/ip'
    PROXIES_URL = 'https://free-proxy-list.net/'

    PROXY_TIMEOUT = 1
    GET_TIMEOUT = 2
    HTML_RENDER_SLEEP = 2

    STANDARD_PROXY_NUMBER = 15
    MINIMAL_PROXY_NUMBER = 10

    DATA_COLLECTING_TIME = 300

    UPDATE_PROXY_INTERVAL = 30
    UPDATE_DEPARTURES_INTERVAL = 20

    def __init__(self) -> None:
        self.stops: StopsDict = dict()
        self.proxies: Set[str] = set()

        self.__start_update_tasks()

        util.log('scrapper ready')

    def __start_update_tasks(self) -> None:
        asyncio.ensure_future(self.__update_proxy_task())
        asyncio.ensure_future(self.__update_departures_task())

    async def __update_proxy_task(self) -> None:
        while True:
            await self.__update_proxies()
            await asyncio.sleep(Scrapper.UPDATE_PROXY_INTERVAL)

    async def __update_departures_task(self) -> None:
        while True:
            await self.__update_departures()
            await asyncio.sleep(Scrapper.UPDATE_DEPARTURES_INTERVAL)

    async def __update_proxies(self, n: int = STANDARD_PROXY_NUMBER) -> None:
        util.log('updating proxies')
        if len(self.proxies) < n:
            util.log('low proxies number')

            if len(self.proxies) == 1:
                self.proxies.clear()

            await self.__get_working_proxies(n)
            util.log('proxies updated, current number {}'.format(len(self.proxies)))

    async def __get_working_proxies(self, n: int) -> Set[str]:
        new_proxies = await Scrapper.__get_proxies()
        working_proxies = set()

        util.log("testing {} proxies ".format((len(new_proxies))))
        for proxy in new_proxies:
            try:
                await Scrapper.__get(Scrapper.TEST_URL, proxy)
                await Scrapper.__get(Scrapper.VM_URL, proxy)
                util.log("got working proxy")
                self.proxies.add(proxy)
            except RequestException:
                pass

            if 0 < len(self.proxies) and n <= len(self.proxies):
                break

        return working_proxies

    @staticmethod
    async def __get_proxies() -> List[str]:
        r = await Scrapper.__get(Scrapper.PROXIES_URL)
        soup = BeautifulSoup(r.text, 'html.parser')
        proxies = list()
        proxies_table = soup.find(id='proxylisttable')
        for proxyRow in proxies_table.tbody.find_all('tr'):
            proxies.append(str(proxyRow.find_all('td')[0].string) + ':' + str(proxyRow.find_all('td')[1].string))
        r.close()
        return proxies

    def __get_next_proxy(self) -> str:
        proxy = self.proxies.pop()

        if len(self.proxies) < 1:
            self.proxies.add(proxy)

        return proxy

    async def __update_departures(self) -> None:
        util.log('updating departures')

        for s in list(self.stops):
            util.log('updating {}'.format(s))
            if Scrapper.__time_elapsed(self.stops[s][2]) <= Scrapper.DATA_COLLECTING_TIME:
                util.log('updating departures for {}'.format(s))
                await self.__add_departures(s)
            else:
                util.log('deleting departures of {}'.format(s))
                self.stops.pop(s)

    async def __add_departures(self, stop: str, from_request: bool = False) -> None:
        util.log('adding departures for {}'.format(stop))

        departures = await self.__live_departures(stop)
        current_time = Scrapper.__current_time()
        last_request_time = current_time if from_request else self.stops[stop][2]
        self.stops[stop] = (departures, current_time, last_request_time)

    async def __live_departures(self, stop: str) -> List[DeparturesRow]:
        util.log('getting departures for {}'.format(stop))

        r = await self.__get_vm(stop)
        await r.html.arender(sleep=Scrapper.HTML_RENDER_SLEEP)

        soup = BeautifulSoup(r.html.raw_html, 'html.parser')
        r.close()

        content = soup.find(class_='content_in')
        items = content.find_all('div', class_='row')

        departures = list()
        for i in items:
            departures.append((
                i.find('div', class_='line').text,
                i.find('div', class_='direction').text,
                i.find('div', class_='time').text
            ))

        return departures

    async def get_departures(self, stop: str) -> List[DeparturesRow]:
        util.log('getting departures for stop {}'.format(stop))

        if stop not in self.stops.keys():
            util.log('stop {} not in data'.format(stop))
            await self.__add_departures(stop, True)

        return self.stops[stop][0]

    @staticmethod
    async def __get(url: str, proxy: str = None) -> Response:
        session = AsyncHTMLSession()
        result = await session.get(url, proxies=Scrapper.__proxies(proxy), timeout=Scrapper.PROXY_TIMEOUT) \
            if proxy is not None \
            else await session.get(url, timeout=Scrapper.GET_TIMEOUT)
        await session.close()
        return result

    async def __get_vm(self, stop: str) -> HTMLResponse:
        url = '{}/?przystanek={}'.format(Scrapper.VM_URL, stop)
        session = AsyncHTMLSession()
        adapter = adapters.HTTPAdapter(max_retries=5)
        session.mount('http://', adapter)
        session.mount('https://', adapter)

        result = None
        while not isinstance(result, HTMLResponse):
            proxy = self.__get_next_proxy()
            try:
                result = await session.get(url, proxies=Scrapper.__proxies(proxy), timeout=Scrapper.GET_TIMEOUT)
            except RequestException:
                if len(self.proxies) == 1:
                    raise Exception('no working proxy available')
                pass

        await session.close()
        return result

    @staticmethod
    def __proxies(proxy: str) -> dict:
        return {"http": proxy, "https": proxy}

    @staticmethod
    def __current_time() -> int:
        return int(time.time())

    @staticmethod
    def __time_elapsed(past: int) -> int:
        return Scrapper.__current_time() - past
