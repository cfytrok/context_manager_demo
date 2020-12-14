"""
Использует xmlproxy.ru для определения позиции в поиске
"""
import os
import pathlib
import sys
import django
from aiohttp import ServerDisconnectedError
from django.conf import settings

module_path = pathlib.Path(__file__).parent
sys.path.insert(0, str(module_path))

# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
# django.setup()

import asyncio
from datetime import datetime
import logging
import re
import time
from collections import OrderedDict

import aiohttp
import requests
from asgiref.sync import sync_to_async
from django.db import connection

from .models import *
from .deserializer import XML_Deserializer
from context_helper import common


class YaXMLSearch:

    def __init__(self, domain, region_id=None, max_page=0):
        self.domain = domain  # домен, если найден, поиск по запросу останавливается
        self.region_id = region_id  # id региона
        self.max_page = max_page  # максимальный индекс страницы, который можно запросить (начиная с 0). Если он больше 1, то яндекс может сказать, что запрашивается слишком далекий документ
        self.sema = asyncio.BoundedSemaphore(value=100)  # ограничивает максимальное число одновременных запросов
        self.last_balance_time = None  # время, когда последний раз пополнили баланс
        self.last_low_price_time = None  # время, когда ставка за запрос стала достаточно низкой

    def get_domain_positions(self, queries):
        """
        Возвращает список позиций по запросу. Индексация с 0. Если не найден до позиции max_position, возвращает None
        :param queries: тексты запросов
        :return:
        """
        # нормализуем запросы
        normal_queries = [common.normalize_phrase(q) for q in queries]
        # скачиваем отсутствующие данные
        self._populate_db(normal_queries)
        # выдаем результат
        query_positions = []
        # разбиваем запрос на куски, т.к. в SQLITE есть ограничение на 999 параметров
        for normal_queries_chunk in common.chunks(normal_queries, 900):
            query_positions += list(
                YaXmlRequest.objects.filter(query__in=normal_queries_chunk, region_id=self.region_id,
                                            group__position__lte=(self.max_page + 1) * 100 - 1,
                                            group__domain=self.domain).values_list('query', 'group__position'))
        query_positions_dict = dict(query_positions)
        return [query_positions_dict.get(q, None) for q in normal_queries]

    def get_query_domains(self, queries, include_urls=None, exclude_urls=None):
        """
        Получает список доменов, у которых в url содержится include_urls.
        url должен начинаться с домена и заканчиваться перед/.
        Запрос страниц останавливается, если найден основной домен или запрошено максимум страниц.
        :param queries: список поисковых запросов
        :param include_urls: части url, которые должны быть, чтобы считать url подходящим, None выводит все домены
        :param exclude_urls: части url, которых не должно быть, чтобы считать url подходящим
        :return: {query:[domain1,domain2,...],) для тех доменов, которые нашли
        """
        # проверяем валидность
        if (include_urls and not all([re.match(r'.*\..*', u) and not u.endswith('/') for u in include_urls])) \
                or (exclude_urls and not all([re.match(r'.*\..*', u) and not u.endswith('/') for u in exclude_urls])):
            raise Exception('url должен начинаться с домена и заканчиваться перед/')
        # нормализуем запросы
        normal_queries = [common.normalize_phrase(q) for q in queries]
        # скачиваем отсутствующие данные
        self._populate_db(normal_queries)
        # выдаем результат
        if include_urls:
            include_regex = self.urls_to_regex(include_urls)
        if exclude_urls:
            exclude_regex = self.urls_to_regex(exclude_urls)
        data = []
        # разбиваем запрос на куски, т.к. в SQLITE есть ограничение на 999 параметров
        for normal_queries_chunk in common.chunks(normal_queries, 900):
            q = Group.objects.filter(request__region_id=self.region_id,
                                     request__query__in=normal_queries_chunk,
                                     position__lte=(self.max_page + 1) * 100 - 1).order_by('request__query',
                                                                                           'position')
            if include_urls:
                q = q.filter(doc__url__iregex=include_regex)
            if exclude_urls:
                q = q.exclude(doc__url__iregex=exclude_regex)
            data += q.distinct().values_list('request__query', 'domain')
        result = {}
        normal_queries_mapper = dict(zip(normal_queries, queries))
        for normal_query, url in data:
            result.setdefault(normal_queries_mapper[normal_query], []).append(url)
        return result

    def get_domain_groups(self, queries):
        """
        Возвращает список групп для каждого запроса. Если данные по запросу есть в базе, возвращает их. Если нет, ищет по запросу + site:domain.
        Если по site:domain не найдено, запроса в ответе не будет.
        :param queries:
        :return:
        """
        # нормализуем запросы
        normal_queries = [common.normalize_phrase(q) for q in queries]

        # запросы, по которым домен найден
        domain_found_queries = set()
        for normal_queries_chunk in common.chunks(normal_queries, 900):
            domain_found_queries.update(
                YaXmlRequest.objects.filter(query__in=normal_queries_chunk, region_id=self.region_id,
                                            group__position__lte=(self.max_page + 1) * 100 - 1,
                                            group__domain=self.domain).values_list('query', flat=True))
        not_found_queries = set(normal_queries) - domain_found_queries
        # пополняем базу
        site_search_queries = ['site:%s ' % self.domain + q for q in not_found_queries]
        # запросы с адресом сайта, по которым домен найден
        domain_found_queries_w_site = set()
        for site_search_queries_chunk in common.chunks(site_search_queries, 900):
            domain_found_queries_w_site.update(YaXmlRequest.objects.filter(query__in=site_search_queries_chunk,
                                                                           region_id=self.region_id,
                                                                           group__position__lte=(
                                                                                                        self.max_page + 1) * 100 - 1,
                                                                           group__domain=self.domain).values_list(
                'query',
                flat=True))
        not_found_site_search_queries = set(site_search_queries) - set(domain_found_queries_w_site)
        queries_start_pages = list(zip(not_found_site_search_queries, [0] * len(not_found_site_search_queries)))
        asyncio.get_event_loop().run_until_complete(
            self.async_populate_db(queries_start_pages,
                                   stop_criteria=lambda x: re.search(
                                       '<domain>.*' + re.escape(self.domain) + '</domain>', x)))
        # возвращаем данные
        result_queries = list(domain_found_queries) + site_search_queries
        groups = []
        for result_queries_chunk in common.chunks(result_queries, 900):
            groups += list(Group.objects.filter(domain=self.domain,
                                                request__region_id=self.region_id,
                                                request__query__in=result_queries_chunk).all())
        normal_queries_mapper = dict(zip(normal_queries, queries))
        result = {}
        for g in groups:
            q = g.request.query
            if q.startswith('site:'):
                site, q = q.split(' ', 1)
            result[normal_queries_mapper[q]] = g
        return result

    def urls_to_regex(self, url_list):
        """
        Преобразует список url в regex, который будет искать содержит ли строка один из url
        :param url_list:
        :return:
        """
        return '|'.join([r'((\.|/)' + re.escape(u) + r'(/|$))' for u in url_list])

    def get_url_str(self, query, page=0, deep=True, groups_on_page=100, docs_in_group=3,
                    maxpassages=5):
        """
        Формирует ссылку запроса
        :param query:
        :param page:
        :param deep: группировать ли результаты из одного домена
        :param groups_on_page: количество групп на странице
        :param docs_in_group: ссылок в одной группе
        :return:
        """
        # query запрос
        # lr регион 225 - Россия, 1 - Мск и обл, 2 - СПб
        # l10n - Язык
        # sortby - порядок сортировки
        # filter фильтр
        # maxpassages количество сниппетов текста
        # groupby группировка результатов с одного домена
        # page номер страницы, начиная с 0
        attr, mode = ('d', 'deep') if deep else ('', 'flat')
        groupby = f'attr={attr}.mode={mode}.groups-on-page={groups_on_page}.docs-in-group={docs_in_group}'
        region_id = self.region_id if self.region_id else ''
        url = f'http://xmlproxy.ru/search/xml?user={settings.YA_XML["user"]}&' \
              f'key={settings.YA_XML["key"]}&' \
              f'query={query}&' \
              f'lr={region_id}&' \
              f'l10n=ru&' \
              f'sortby=rlv&' \
              f'filter=none&' \
              f'maxpassages={maxpassages}&' \
              f'groupby={groupby}&' \
              f'page={page}'
        return url

    async def get_query_data(self, session, query, start_page, stop_criteria):
        """
        Постранично запрашивает XML Яндекса для одного запроса и записывает результат в базу, пока не найдет домен или не достигнет max_page
        :param session: сейссия соединения
        :param query:
        :param start_page:
        :return:
        """
        for page in range(start_page, self.max_page + 1):
            url = self.get_url_str(query, page=page)
            response_text = None
            # 5 попыток получить валидный ответ
            for i in range(5):
                try:
                    async with self.sema, session.get(url) as response:
                        response_text = await response.text()
                        if self.is_response_valid(response, response_text):
                            thread_sensitive = True  # connection.vendor == 'sqlite' todo: для ускорения сделать XML_Deserializer thread save. Для этого его надо создать один раз и id объестов сделать thread save. Тогда можно будет сделать thread_sensitive = False. И запросы к базе данных пойдут параллельно в разных потоках. Сейчас запросы в одном потоке.
                            await sync_to_async(XML_Deserializer, thread_sensitive=thread_sensitive)(response_text,
                                                                                                     self.region_id)
                            break
                except (ServerDisconnectedError, UnicodeError) as e:
                    logging.error(e)
                    continue
            else:
                raise Exception(response_text)
            # больше не запрашиваем страницы, если нашли домен
            if stop_criteria(response_text):
                break

    def is_response_valid(self, response, response_text):
        """
        Проверяет, получили ли качественный ответ. В случае недостатка баланса или нехватки ставки вызывает соответствующие функции
        :param response:
        :param response_text:
        :return:
        """
        server_time = datetime.strptime(response.headers['Date'], '%a, %d %b %Y %H:%M:%S GMT')
        if not response_text:
            return False
        # недостаточная максимальная ставка
        if '<error code="-132">' in response_text:
            self.wait_low_price(server_time)
            return False
        # недостаточный баланс
        if '<error code="-32">' in response_text:
            self.wait_balance(
                server_time)
            return False
        if not response_text.endswith('</yandexsearch>'):
            return False
        # Если групп нет и найдены искомые комбинации
        if not '<results><grouping' in response_text and '<error code="15">' not in response_text:
            return False
        return True

    def wait_balance(self, server_time):
        # если ответ сервера был до того, как пополнили баланс, просто выходим и перезапрашиваем
        # Это надо, т.к. запросы выполняются параллельно и обработка нескольких ответов может попасть в эту функцию. Выполнить проверку баланса надо только для первого запроса.
        if self.last_balance_time and server_time < self.last_balance_time:
            return
        input("Деньги на xmlproxy кончились. Пополните баланс и нажмите любую клавишу")
        self.last_balance_time = datetime.utcnow()

    def wait_low_price(self, server_time):
        # если ответ сервера был до того, как получили инфу, что ставка снизилась, просто выходим и перезапрашиваем. см. wait_balance
        if self.last_low_price_time and server_time < self.last_low_price_time:
            return
        logging.info("Ждем, когда будет снижена ставка")
        while True:
            if self.is_low_current_cost():
                break
            time.sleep(5)
        self.last_low_price_time = datetime.utcnow()

    def is_low_current_cost(self):
        """
        Узнает текущую ставку за 1000 запросов. Возвращете True, если она меньше или равна максимальной ставке
        :return:
        """
        url = "http://xmlproxy.ru/balance.php?user=%s&key=%s" % (self.__user, self.__key)
        response = requests.get(url).json()
        logging.info('current cost:{cur_cost} max cost:{max_cost}'.format(**response))
        return response['cur_cost'] <= response['max_cost']

    def _populate_db(self, normal_queries):
        """
        Определяет, данных по каким запросам нехватает (мало страниц и домен не найден).
        Делает серию параллельных запросов к yandex XML и сохраняет в базу.
        :param response: нормализованные тексты запросов
        :return:
        """
        # находим запросы, данных по которым нехватает данных
        # запросы, по которым получено максимум результатов
        max_pages_queries = set()
        domain_found_queries = set()

        # разбиваем запрос на куски, т.к. в SQLITE есть ограничение на 999 параметров
        for normal_queries_chunk in common.chunks(normal_queries, 900):
            # запросы, по которым получено максимум результатов
            max_pages_queries |= set(
                YaXmlRequest.objects.filter(query__in=normal_queries_chunk, region_id=self.region_id,
                                            last_page__gte=self.max_page).values_list('query', flat=True))
            # запросы, по которым выполнено условие остановки, то есть домен найден
            domain_found_queries |= set(
                YaXmlRequest.objects.filter(query__in=normal_queries_chunk, region_id=self.region_id,
                                            group__position__lte=(self.max_page + 1) * 100 - 1,
                                            group__domain=self.domain).values_list('query', flat=True))

        not_found_queries = set(normal_queries) - set(domain_found_queries) - set(max_pages_queries)
        # с какой страницы надо дополучить данные
        need_more_data_queries = []
        for not_found_queries_chunk in common.chunks(not_found_queries, 900):
            need_more_data_queries += YaXmlRequest.objects.filter(query__in=not_found_queries_chunk,
                                                                  region_id=self.region_id,
                                                                  last_page__lt=self.max_page).values_list('query',
                                                                                                           'last_page')
        # получаем начиная с первой неполученной страницы для тех, которые есть в базе
        # [(запрос, номер страницы с которой начать),...]
        queries_start_pages = list([(q, last_page + 1) for q, last_page in need_more_data_queries])
        # для остальных с 0 страницы
        not_found_queries -= {q for q, _ in queries_start_pages}
        queries_start_pages.extend([(q, 0) for q in not_found_queries])
        # запрашиваем xml
        asyncio.get_event_loop().run_until_complete(
            self.async_populate_db(queries_start_pages,
                                   stop_criteria=lambda x: re.search(
                                       '<domain>.*' + re.escape(self.domain) + '</domain>', x)))

    async def async_populate_db(self, queries_start_pages, stop_criteria):
        # stop_criteria: функция, которая на вход получает текст ответа, должна вернуть True, если больше страниц запрашивать не нужно
        logging.info('Получаем результаты поиска для %s запросов' % len(queries_start_pages))
        tasks = []
        async with aiohttp.ClientSession() as session:
            for query, first_page in queries_start_pages:
                tasks.append(self.get_query_data(session, query, first_page, stop_criteria))
            await asyncio.gather(*tasks)


# нет результатов ответе
class NoResults(Exception):
    pass


# недостаточная ставка
class NotEnoughBid(Exception):
    pass


# недостаточно денег
class NotEnoughBalance(Exception):
    pass


if __name__ == '__main__':
    pass
