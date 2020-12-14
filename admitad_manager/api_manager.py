import logging
from datetime import timedelta, datetime, date

from bulk_sync import bulk_sync
from django.db.models import Q
from singleton import Singleton
from forex_python.converter import CurrencyRates

import pytz
from admitad import items, api
from django.conf import settings

from admitad_manager.models import *
from unify_context.models import Tariff, Position
from unify_context.subidparser import BadSubid, SubIdParser


class AdmitadAPI(metaclass=Singleton):
    google_device_mapper = {'c': "desktop", 'm': "mobile", 't': "tablet"}

    def __new__(cls, *args, **kwargs):
        cls.curr_converter = CurrencyRates()
        return super().__new__(cls, *args, **kwargs)

    def __init__(self):
        # подключаемся к API
        scope = ' '.join({items.StatisticActions.SCOPE,
                          items.Campaigns.SCOPE,
                          items.CampaignsForWebsite.SCOPE,
                          items.Websites.SCOPE})
        self.client = api.get_oauth_client_client(
            settings.ADMITAD['client_id'],
            settings.ADMITAD['client_secret'],
            scope
        )

    def sync(self):
        # загружаем вебсайты
        self.get_websites()
        # загружаем партнерские программы
        self.get_campaigns()
        # загружаем статистику
        self.get_stats()

    def get_websites(self):
        websites = self.client.Websites.get()
        created_cnt = 0
        for w in websites['results']:
            data = get_valid_init_dict(Website, **w)
            object, created = Website.objects.update_or_create(id=data.pop('id'), defaults=data)
            if created: created_cnt += 1
        logging.info('Websites created: %s, updated: %s' % (created_cnt, len(websites['results']) - created_cnt))

    def get_campaigns(self):
        for website in Website.objects.all():
            programs_data = self.client.Campaigns.get(website=website.id, limit=500)
            programs_for_website_data = self.client.CampaignsForWebsite.get(website.id, limit=500)
            for program_data, program_for_website_data in zip(programs_data['results'],
                                                              programs_for_website_data['results']):
                assert program_data['id'] == program_for_website_data['id']
                data = get_valid_init_dict(AdmitadProgram, **program_data)
                # переводим из процентов в долю
                data['conversion_rate'] = float(
                    program_data['cr']) / 100  # конверсия: все действия/количество кликов за 20 дней
                data['approve_rate'] = float(program_data['rate_of_approve']) / 100  # доля подтверждения от 0 до 1
                # средний заработок (подтвержденный) за клик в копейках за 20 дней
                earn_per_click = int(self.curr_converter.convert(data['currency'], 'RUB',
                                                                 float(
                                                                     program_data[
                                                                         'ecpc'])) * 100)  # переводим валюту в копейки
                data['avg_approved_payment'] = earn_per_click / data['conversion_rate'] / data['approve_rate']
                program, created = AdmitadProgram.objects.update_or_create(id=data.pop('id'), defaults=data)
                program.website_set.add(website,
                                        through_defaults={'gotolink': program_for_website_data['gotolink'],
                                                          'products_xml_link': program_for_website_data[
                                                              'products_xml_link']})
                # загружаем тарифы и ставки программы
                self.update_rates(program, program_for_website_data)

        logging.info('Campaigns synced')

    def update_rates(self, program, program_for_website):
        """Парсит ставки программы и обновляет их"""
        tariffs = []
        for action_detail in program_for_website['actions_detail']:
            for tariff in action_detail['tariffs']:
                # проверяем все ли ставки имею одинаковую оплату
                rate_size = None
                for rate in tariff['rates']:
                    if rate_size is not None and rate['size'] != rate_size:
                        raise Exception('Different rates in Tariff')
                    rate_size = rate['size']

                tariff_name = f"{action_detail['name']}/{tariff['name']}"
                data = {'id': tariff['id'],
                        'name': tariff_name,
                        'is_percentage': tariff['rates'][0]['is_percentage'],
                        # берем данные первой ставки, т.к. остальные обычно такие-же
                        'size': float(tariff['rates'][0]['size']),
                        'program_id': program.id}
                if data['is_percentage']:
                    data['size'] /= 100
                else:
                    # переводим в копейки
                    data['size'] = round(
                        self.curr_converter.convert(program_for_website['currency'], 'RUB', data['size']) * 100)
                tariff_obj, created = Tariff.objects.update_or_create(id=data.pop('id'), defaults=data)
                tariffs.append(tariff_obj)
        program.tariff_set.exclude(id__in=[t.id for t in tariffs]).delete()  # удаляем старые ставки

    def get_stats(self):
        """
        Загружает статистику Admitad в базу за макс 365 дней или с последнего необработанного действия или с последнейго действия
        :return:
        """
        date_to = datetime.now(pytz.timezone('Europe/Moscow')).date() - timedelta(
            days=1)  # вчера по московскому времени
        # min_date = date(day=5, month=2,
        #                 year=2020)  # дата с которой собираются данные адмитад. До этого неправильно фиксировался subid
        date_from = AdmitadAction.get_stats_date_from()
        if not date_from:
            date_from = date(day=1, month=1, year=2020)  # получаем действия за все время

        # действия будут получены только для существующих программ
        program_ids = set(AdmitadProgram.objects.values_list('id', flat=True))
        actions = []
        positions = []
        offset = 0
        # Загружаем данные блоками
        while True:
            # загружаем статистику включая данный в date_from и date_to
            res = self.client.StatisticActions.get(offset=offset, limit=500,
                                                   date_start=date_from.strftime("%d.%m.%Y"),
                                                   date_end=date_to.strftime("%d.%m.%Y")
                                                   )

            for item in res['results']:
                action = self.action_from_api_item(item)
                # если программа еще существует
                if action.program_id in program_ids:
                    actions.append(action)
                    positions.extend(self.positions_from_api_item(item))
            offset += 500
            if res['_meta']['count'] < res['_meta']['limit'] + res['_meta']['offset']:
                break
        filter = Q(action_time__gte=date_from) if date_from else Q(pk__isnull=False)
        bulk_sync(new_models=actions, key_fields=['id'], filters=filter)  # сохраняем действия в базу
        bulk_sync(new_models=positions, key_fields=['id'],
                  filters=Q(action__in=actions))  # сохраняем позиции в действии
        result_str = f"Admitad stats collected {len(actions)} actions"
        logging.info(result_str)
        return result_str

    @classmethod
    def action_from_api_item(cls, admitad_item):
        """Преобразует ответ API в объект базы"""

        subid_data = SubIdParser().parse(admitad_item)

        action = AdmitadAction(**subid_data)
        action.click_time = datetime.fromisoformat(admitad_item['click_date'])
        action.action_time = datetime.fromisoformat(admitad_item['action_date'])
        if admitad_item['closing_date']:
            action.closing_time = datetime.fromisoformat(admitad_item['closing_date'])
        action.status = admitad_item['status']
        action.program_id = admitad_item['advcampaign_id']
        # переводим валюту в копейки по курсу на дату действия
        action.cart = round(
            cls.curr_converter.convert(admitad_item['currency'], 'RUB', admitad_item['cart'],
                                       action.action_time) * 100) if admitad_item['cart'] is not None else None
        action.payment = round(
            cls.curr_converter.convert(admitad_item['currency'], 'RUB', admitad_item['payment'],
                                       action.action_time) * 100)
        action.id = admitad_item['id']
        action.pk = action.id
        action.website_name = admitad_item['website_name']
        # исправляемя device для google
        if action.source == 'google':
            try:
                action.device = cls.google_device_mapper[action.device]
            except:
                action.device = ''
                logging.warning("not valid device in subid in admitad item: %s' % admitad_item")
            # убираем criteria для динамических кампаний
            if 'dsa' in action.criterion_id:
                action.criterion_id = None
        return action

    @classmethod
    def positions_from_api_item(cls, admitad_item):

        for position_data in admitad_item['positions']:
            position = Position(id=position_data['id'],
                                tariff_id=position_data['tariff_id'],
                                amount=position_data['amount'],
                                action_id=admitad_item['action_id'])
            if position.amount == 'None':
                position.amount = None
            else:
                # переводим в копейки
                position.amount = round(
                    cls.curr_converter.convert(admitad_item['currency'], 'RUB', float(position.amount),
                                               datetime.fromisoformat(admitad_item['action_date'])) * 100)
            yield position


def get_valid_init_dict(cls, **kwargs):
    """
    Оставляет только те аргументы, которые есть в модели.
    """
    field_names = {f.name for f in cls._meta.get_fields()}
    field_args = {k: v for k, v in kwargs.items() if k in field_names}
    return field_args
