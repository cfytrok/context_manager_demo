import logging
import datetime

import pytz
import requests
from bulk_sync import bulk_sync
from django.conf import settings
from django.db.models import Q
from singleton import Singleton
import xmltodict

from unify_context.models import Tariff, Position
from unify_context.subidparser import BadSubid, SubIdParser
from advcake_manager.models import AdvCakeProgram, AdvCakeAction


class AdvCakeAPI(metaclass=Singleton):

    stats_url = 'https://my.advcake.com/export/webmaster/{token}?date_from={{date_from}}&date_to={{date_to}}'.format(
        token=settings.ADV_CAKE['token'])
    offers_url = 'https://api.advcake.com/offers?pass={token}'.format(token=settings.ADV_CAKE['token'])

    status_mapper = {
        '1': 'pending',
        '2': 'approved',
        '3': 'declined',
    }
    google_device_mapper = {'c': "desktop", 'm': "mobile", 't': "tablet"}

    def sync(self):
        self.get_programs()
        self.get_stats()

    def get_programs(self):
        """Загружаем партнерские программы и тарифы"""
        r = requests.get(self.offers_url)
        result = r.json()['data']
        for offer_data in result:
            program, _ = AdvCakeProgram.objects.update_or_create(id=offer_data['id'],
                                                                 defaults={'name': offer_data['name']})
            # загружаем тарифы
            tariffs = []
            for tariff_data in offer_data['bids']:
                tariff = Tariff(id=tariff_data['id'],
                                size=tariff_data['value'],
                                name=tariff_data['text'],
                                is_percentage=tariff_data['type'] == 'percent',
                                program=program)
                if tariff.is_percentage:
                    tariff.size /= 100
                else:
                    # переводим в копейки
                    tariff.size = round(tariff.size * 100)
                tariffs.append(tariff)
            bulk_sync(tariffs, key_fields=['pk'], filters=Q(program=program))

    def get_stats(self):
        """
        Загружает все действия AdvCake в базу за все время или с последнего необработанного действия или с последнейго действия.
        :return:
        """
        actions = []
        positions = []

        batch_date_to = date_to = datetime.datetime.now(pytz.timezone('Europe/Moscow')).date() - datetime.timedelta(
            days=1)  # вчера
        date_from = AdvCakeAction.get_stats_date_from()  # None, значит действий нет, загружаем все данные
        batch_date_from = batch_date_to - datetime.timedelta(days=70 - 1)

        # Загружаем данные блоками по max_days, пока не получим пустой или действие раньше date_from
        while True:
            # загружаем статистику включая данный в date_from и date_to
            r = requests.get(
                self.stats_url.format(date_from=batch_date_from.isoformat(), date_to=batch_date_to.isoformat()))
            result = xmltodict.parse(r.text)
            # если в результатах нет действий, значит загрузили все данные
            if not result['items']:
                break
            for item in result['items']['item']:  # действия идут в обратном порядке. последним будет самое раннее
                action = self.action_from_api_item(item)
                actions.append(action)
                positions.extend(self.positions_from_api_item(action))
            # если получили действие с датой меньше или равно date_from, останавливаемся
            if date_from and actions[-1].action_time.date() <= date_from:
                break
            # получаем данный за предыдыдущие 70 дней
            batch_date_to = batch_date_from - datetime.timedelta(days=1)
            batch_date_from = batch_date_to - datetime.timedelta(days=70 - 1)
        filter = Q(action_time__gte=date_from) if date_from else Q(pk__isnull=False)
        bulk_sync(new_models=actions, key_fields=['id'], filters=filter)  # сохраняем действия
        bulk_sync(new_models=positions, key_fields=['id'],
                  filters=Q(action__in=actions))  # сохраняем позиции в действии

    @classmethod
    def action_from_api_item(cls, advcake_item):
        """Преобразует ответ API в объект базы"""
        subid_data = SubIdParser().parse(advcake_item)

        action = AdvCakeAction(**subid_data)
        action.status = cls.status_mapper[advcake_item['status']]
        action.action_time = datetime.datetime.fromisoformat(advcake_item['date'])
        # clicked_at не всегда указан
        action.click_time = datetime.datetime.fromisoformat(advcake_item['clicked_at']) if advcake_item[
            'clicked_at'] else action.action_time
        if action.status != 'pending':
            action.closing_time = datetime.datetime.fromisoformat(advcake_item['dateChange'])
        action.program_id = int(advcake_item['offer_id'])
        # переводим валюту в копейки по курсу на дату действия
        action.cart = round(float(advcake_item['price']) * 100)
        action.payment = round(float(advcake_item['commission']) * 100)
        action.id = int(advcake_item['order_id'])
        action.pk = action.id
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
    def positions_from_api_item(cls, action):
        # возвращает список позиций для действия.
        # todo: advcacke не возвращает тарифы и позиции, поэтому для одного заказа возвращаем позицию с первым тарифом, которая соответствует действию
        position = Position(id=action.id,
                            tariff=action.program.tariff_set.first(),
                            amount=action.cart,
                            action_id=action.id)
        yield position
