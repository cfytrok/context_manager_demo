"""
Идентификторы объектов в директе положительные.
Идентификаторы объектов, которые еще не отправлены в директ отрицательны. Это сделано что бы после отправки можно поменять id (создать объекты с положительными id, которые получены из директа и удалить объекты с отрицательными id
"""
import inspect
import logging
from datetime import date, timedelta, datetime
from functools import partial

import pytz
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import OneToOneField
from django.db.models.fields.reverse_related import ForeignObjectRel, OneToOneRel
from singleton import Singleton
from yandex_direct_api import Api
from direct.models import *


class DirectAPI(metaclass=Singleton):
    def __init__(self, accounts, sandbox=False):

        self.ya_api = Api(accounts=accounts, sandbox=sandbox)
        self.now = datetime.now(pytz.timezone('Europe/Moscow'))  # Сейчас по московскому времени
        self.today = self.now.date()
        self.yesterday = self.today - timedelta(days=1)
        self.account = None

    def load_data(self):
        # загружаем в локальную базу данныи из директа для всех аккаунтов
        for account in Account.objects.exclude(disable=True).all():
            logging.info("Load yandex data for %s" % account.login)
            self.load_account(account)

    def load_account(self, account):
        # загружает данные из директа
        self.account = account
        # подгружаем постоянные справочники, типо регионов
        self.sync_dictionaries()
        # проверяем, была ли синхронизация. Если нет, загружаем все объекты. Если да, получаем объекты, которые изменились
        changes = self.get_changed_ids()
        if len(changes) == 1:
            # запрашвиваем все данные, если синхронизации еще не было ( в changes только timestamp)
            # удаляем все существующие кампании с их содержанием
            self.account.campaign_set.all().delete()

            self.get_campaigns()
            acc_campaign_ids = list(Campaign.objects.filter(account=self.account).values_list('id', flat=True))
            self.get_ad_groups(cmp_ids=acc_campaign_ids)
            self.get_text_ads(cmp_ids=acc_campaign_ids)
            self.get_keywords(cmp_ids=acc_campaign_ids)
        else:
            # запрашиваем измененные данные
            self.get_campaigns(ids=changes['changed']['campaigns'])
            # обрабатываем только объекты в загруженных кампаниях (архивные, наприме, игнорируются)
            acc_campaign_ids = list(Campaign.objects.filter(account=self.account).values_list('id', flat=True))
            self.get_ad_groups(cmp_ids=acc_campaign_ids, group_ids=changes['changed']['groups'])
            self.get_text_ads(cmp_ids=acc_campaign_ids, ad_ids=changes['changed']['ads'])
            self.get_keywords(cmp_ids=acc_campaign_ids, group_ids=changes['changed']['groups'])
            # Удаляем объекты, которые больше не существуют
            TextAd.objects.filter(id__in=changes['deleted']['ads']).delete()
            AdGroup.objects.filter(id__in=changes['deleted']['groups']).delete()
            Campaign.objects.filter(id__in=changes['deleted']['campaigns']).delete()


        # Сохраняем время проверки изменений
        self.account.last_campaigns_changes_time = changes['timestamp'][:-1]
        self.account.sync_time = datetime.now()
        self.account.save()

        # получаем статистику
        if self.ya_api.sandbox == False:  # в песочница отчеты работают по-другому
            self.get_stats()

    def sync_dictionaries(self):
        """
        Проверяет наличие изменений в справочнике регионов и обновлеят регионы, если надо
        :return:
        """

        # если нет сохраненных изменений, загружаем все регионы
        if not self.account.last_dictionaries_changes_time:
            result = self.ya_api.checkDictionaries_changes()
            self.get_regions()
        else:
            # получаем метку времени либо время последней синхронизации, либо текущее время
            ts = self.account.last_dictionaries_changes_time.isoformat(timespec='seconds') + 'Z'
            result = self.ya_api.checkDictionaries_changes({"Timestamp": ts})
            if result['RegionsChanged'] == 'YES':
                self.get_regions()
        self.account.last_dictionaries_changes_time = result['Timestamp'][:-1]  # удаляе 'Z' с конца
        self.account.save()

    def get_changed_ids(self):
        """
        Возвращет идентификаторы кампаний, групп и объявлений, которые были изменены с последней проверки.
        Если не было синхронизации, возвращает None везде
        :return:
        """
        if not self.account.last_campaigns_changes_time:
            return {'timestamp': self.ya_api.checkDictionaries_changes(client_login=self.account.login)[
                'Timestamp']}  # получаем текущее время сервера
        last_timestamp = self.account.last_campaigns_changes_time.isoformat() + 'Z'
        # получаем объекты, которые нужно загрузить
        # надо полчить списко кампаний, которые надо обновить
        # надо получить список кампаний, для которых запросить изменение дочерних объектов
        campaign_changes = self.ya_api.checkCampaigns_changes({'Timestamp': last_timestamp},
                                                              client_login=self.account.login)
        server_timestamp = campaign_changes['Timestamp']
        changed_campaigns = []
        changed_groups = []
        changed_ads = []
        changed_child_campaigns = []  # кампании в которых изменены дочерние объекты
        for change in campaign_changes.get('Campaigns', []):
            if 'SELF' in change['ChangesIn']:
                changed_campaigns.append(change['CampaignId'])
            if 'CHILDREN' in change['ChangesIn']:
                changed_child_campaigns.append(change['CampaignId'])

        # получаем изменения в группах(сюда входят ключевики) и объявлениях
        if changed_child_campaigns:
            child_changes = self.ya_api.check_changes({'CampaignIds': changed_child_campaigns,
                                                       "FieldNames": ["AdGroupIds", "AdIds"],
                                                       'Timestamp': last_timestamp, }, client_login=self.account.login)

            changed_groups = child_changes['Modified'].get('AdGroupIds', [])
            changed_ads = child_changes['Modified'].get('AdIds', [])

        # получаем идентификаторы удаленных объектов
        # получаем сущетсвующие идентификторы
        existing_cmp_ids = list(Campaign.objects.values_list('id', flat=True))
        existing_group_ids = list(AdGroup.objects.values_list('id', flat=True))
        existing_ad_ids = list(TextAd.objects.values_list('id', flat=True))
        # проверяем наличие изменений
        cmp_check_results = {}
        group_check_results = {}
        ad_check_results = {}
        if existing_cmp_ids:
            cmp_check_results = self.ya_api.check_changes({'CampaignIds': existing_cmp_ids,
                                                           "FieldNames": ["CampaignIds"],
                                                           'Timestamp': last_timestamp, },
                                                          client_login=self.account.login)
        if existing_group_ids:
            group_check_results = self.ya_api.check_changes({'AdGroupIds': existing_group_ids,
                                                             "FieldNames": ["AdGroupIds"],
                                                             'Timestamp': last_timestamp, },
                                                            client_login=self.account.login)
        if existing_ad_ids:
            ad_check_results = self.ya_api.check_changes({'AdIds': existing_ad_ids,
                                                          "FieldNames": ["AdIds"],
                                                          'Timestamp': last_timestamp, },
                                                         client_login=self.account.login)
        # если id не найден, значит объект удален
        deleted_campaigns = cmp_check_results.get('NotFound', {}).get('CampaignIds', [])
        deleted_groups = group_check_results.get('NotFound', {}).get('AdGroupIds', [])
        deleted_ads = ad_check_results.get('NotFound', {}).get('AdIds', [])

        return {'changed': {'campaigns': changed_campaigns,
                            'groups': changed_groups,
                            'ads': changed_ads},
                'deleted': {'campaigns': deleted_campaigns,
                            'groups': deleted_groups,
                            'ads': deleted_ads},
                'timestamp': server_timestamp}

    def get_stats(self):

        # получаем отчет
        params = self._calc_stats_params()
        report = self.ya_api.reports(params, client_login=self.account.login)

        # удаляем старые данные
        first_date = date.fromisoformat(report[0]['Date'])
        deleted = DirectStats.objects.filter(date__gte=first_date,
                                             campaign__account__login=self.account.login).delete()

        # создаем объекты статистики
        stats = self.parse_direct_report(report)

        # добавлем отсутствующие критерии
        self._create_missed_criterions(stats)

        # отправляем статистику в базу
        DirectStats.objects.bulk_create(stats, batch_size=100)
        logging.info("Yandex stats collected")

    def _create_missed_criterions(self, stats):
        # добавлем отсутствующие критерии. Либо фраза удалена, либо критерий не управляется через API
        # получаем id существующих критериев
        kwd_ids = set(
            Criterion.objects.filter(ad_group__campaign__account=self.account).values_list('id', flat=True))
        # создаем удаленные ключевые слова
        deleted_kwds = {}
        for stat in stats:
            # если фразы нет в базе, значит она удалена, создаем ее
            kwd_id = int(stat.criterion_id)
            if kwd_id not in kwd_ids and kwd_id not in deleted_kwds:
                deleted_kwds[kwd_id] = Criterion(id=stat.criterion_id, ad_group_id=stat.group_id)
        # отправляем ключи в базу
        Criterion.objects.bulk_create(list(deleted_kwds.values()), batch_size=100)

    def _calc_stats_params(self):
        try:
            last_stat = DirectStats.objects.filter(campaign__account=self.account).latest('date')
        except ObjectDoesNotExist:
            last_stat = None

        date_criteria = {}
        # Если данных нет, запрашиваем за весь период
        if not last_stat:
            date_params = {"DateRangeType": "ALL_TIME"}
        # если есть за позавчера, в режиме авто: минимум 3 дня, не включая сегодя + дни, когда статистика корректировалась
        elif last_stat.date >= self.yesterday - timedelta(days=1):
            date_params = {"DateRangeType": "AUTO"}
        # иначе с того дня, как была снята статистика - 7 дней, что б учесть все корректировки
        else:
            date_params = {
                "DateRangeType": "CUSTOM_DATE",
            }
            date_criteria = {
                "DateFrom": (last_stat.date - timedelta(days=7)).isoformat(),
                "DateTo": self.yesterday.isoformat()
            }

        account_campaigns = list(
            Campaign.objects.filter(account=self.account).values_list('id', flat=True))
        params = {
            "SelectionCriteria": {
                "Filter": [
                    {
                        "Field": "CampaignId",
                        "Operator": "IN",
                        "Values": account_campaigns
                    },
                    # {
                    #     "Field": "Clicks",
                    #     "Operator": "GREATER_THAN",
                    #     "Values": [0]
                    # }
                ]
            },
            "FieldNames": ["Date", "CampaignId", "AdGroupId", "AdId", "CriterionId", "Clicks", "Impressions", "Device",
                           "TargetingLocationId", "Gender", "Age", "CarrierType", "MobilePlatform", "Slot"],
            "OrderBy": [{
                "Field": "Date"
            }],
            "ReportName": "Yesterday Report %s" % datetime.now(pytz.timezone('Europe/Moscow')).isoformat(),
            "ReportType": "CUSTOM_REPORT",
            "Format": "TSV",
            "IncludeVAT": "YES",
            "IncludeDiscount": "YES"}
        params.update(date_params)
        params['SelectionCriteria'].update(date_criteria)
        return params

    def parse_direct_report(self, report):
        stats = []
        for item in report:
            stat, update_fields = DirectStats.deserialize(item)
            # данные за сегодня не нужны
            if stat.date >= self.today:
                continue
            stats.append(stat)
        return stats

    def get_campaigns(self, ids=None):
        """
        Подгружает кампании в базу
        :param ids: идентификаторы кампаний, которые будут обновлены. Если None, загружаются все кампании
        :return:
        """
        if isinstance(ids, list) and not ids:  # если ids -пустой список, ничего не делаем
            return
        params = {
            "SelectionCriteria": {
                "Types": ["TEXT_CAMPAIGN", "DYNAMIC_TEXT_CAMPAIGN", "SMART_CAMPAIGN"],
                "States": ["OFF", "ON", "SUSPENDED"]
            },
            "FieldNames": ["BlockedIps", "ExcludedSites", "DailyBudget", "Id", "Name", "NegativeKeywords", "State",
                           "Status", "Type", "StartDate"],
        }
        filter = {'account': self.account}
        if ids is not None:
            params["SelectionCriteria"]['Ids'] = ids
            filter['id__in'] = ids
        results = self.ya_api.get_campaigns(params, client_login=self.account.login)

        text_campaigns = []
        other_campaigns = []
        for campaign in results:
            campaign['AccountId'] = self.account.login
            # добавляем логин в параметры
            if campaign['Type'] == 'TEXT_CAMPAIGN':
                text_campaigns.append(campaign)
            else:
                other_campaigns.append(campaign)
        TextCampaign.sync_response(text_campaigns, filter=filter)
        # не нужно менять текстовые кампании, поэтому добавляем условие в фильтры
        filter['type__in'] = {choice[0] for choice in Campaign.TYPE_CHOICES} - {'TEXT_CAMPAIGN'}
        Campaign.sync_response(other_campaigns, filter=filter)

    def get_ad_groups(self, cmp_ids=None, group_ids=None):
        """
        Подгружает группы в базу
        """
        if not cmp_ids and not group_ids:
            return
        params = {
            "SelectionCriteria": {
                "Types": ["TEXT_AD_GROUP", "DYNAMIC_TEXT_AD_GROUP", "SMART_AD_GROUP"]
            },
            "FieldNames": ["CampaignId", "Id", "Name", "ServingStatus", "Status", "TrackingParams", "NegativeKeywords"],
        }
        filter = {'campaign__account': self.account}
        if cmp_ids:
            params['SelectionCriteria']['CampaignIds'] = cmp_ids
            filter['campaign_id__in'] = cmp_ids
        if group_ids:
            params['SelectionCriteria']['Ids'] = group_ids
            filter['id__in'] = group_ids
        results = self.ya_api.get_adgroups(params, client_login=self.account.login)
        AdGroup.sync_response(results, filter)

    def get_text_ads(self, cmp_ids=None, ad_ids=None):
        """
        Подгружает тексты в базу
        """
        if not cmp_ids and not ad_ids:
            return
        params = {
            "SelectionCriteria": {
                "Types": ["TEXT_AD"]
            },
            "FieldNames": ["AdGroupId", "Id", "State", "Status", "StatusClarification"],
            "TextAdFieldNames": ["AdImageHash", "DisplayDomain", "Href", "Text", "Title", "Title2", "Mobile", "VCardId",
                                 "DisplayUrlPath"]
        }
        filter = {'ad_group__campaign__account': self.account}
        if cmp_ids:
            params['SelectionCriteria']['CampaignIds'] = cmp_ids
            filter['ad_group__campaign_id__in'] = cmp_ids
        if ad_ids:
            params['SelectionCriteria']['Ids'] = ad_ids
            filter['id__in'] = ad_ids
        results = self.ya_api.get_ads(params, client_login=self.account.login)
        TextAd.sync_response(results, filter)

    def get_keywords(self, cmp_ids=None, group_ids=None):
        """
        Подгружает ключевики в базу
        """
        if not cmp_ids and not group_ids:
            return

        params = {
            "SelectionCriteria": {
            },
            "FieldNames": ["Id", "Keyword", "State", "Status", "ServingStatus", "AdGroupId", "Bid", "ContextBid",
                           "StrategyPriority", "UserParam1", "UserParam2"]
        }
        filter = {'ad_group__campaign__account': self.account}
        if cmp_ids:
            params['SelectionCriteria']['CampaignIds'] = cmp_ids
            filter['ad_group__campaign_id__in'] = cmp_ids
        if group_ids:
            params['SelectionCriteria']['AdGroupIds'] = group_ids
            filter['ad_group_id__in'] = group_ids
        results = self.ya_api.get_keywords(params, client_login=self.account.login)
        Keyword.sync_response(results, filter)

    def send_bids(self, kwds):
        """Отправляет ставки в базу"""
        # группируем ключевые слова по логину
        data = {}
        for kw in kwds:
            data.setdefault(
                kw.ad_group.campaign.account.login,
                {"KeywordBids": []}
            )["KeywordBids"].append({"KeywordId": kw.id, "SearchBid": kw.bid * 10_000})
        # для каждого логина устанавливаем ставки
        for login, params in data.items():
            results = self.ya_api.set_keywordbids(params, client_login=login)
            logging.info("%s bids updated %s" % (len(results), login))
        # сохраняем в базу
        Keyword.objects.bulk_update(kwds, ['bid'], batch_size=900)
        logging.info("bids comitted to db")

    def get_regions(self):
        params = {
            "DictionaryNames": ["GeoRegions"]
        }
        results = self.ya_api.get_dictionaries(params)

        Region.sync_response(results, filter={})

    def create_text_campaigns(self, names):
        """
        Создает кампании и сохраняет их в базу
        :param names: список имен кампаний
        :return: возвращает список созданных кампаний
        """
        params = {"Campaigns": []}
        for name in names:
            params['Campaigns'].append({
                "Name": name,
                "StartDate": self.today.strftime("YYYY-MM-DD"),
                "TextCampaign": {
                    "BiddingStrategy": {
                        "Search": {
                            "BiddingStrategyType": "HIGHEST_POSITION",
                        },
                        "Network": {
                            "BiddingStrategyType": "SERVING_OFF",
                        }
                    }
                }
            })
        results = self.ya_api.add_campaigns(params, client_login=self.account.login)
        campaigns = []
        for name, result in zip(names, results['AddResults']):
            if 'Id' not in result:
                raise Exception('no id after campaign creation')
            campaigns.append(TextCampaign.objects.create(id=results['AddResults']['Id'], name=name))
            # созраняем в базу
        return campaigns

    def add_objects(self, obj_names, objs):
        if not objs:
            return
        cls = objs[0].__class__
        service = obj_names.lower()
        params = {obj_names: [o.serialize(exclude={'id'} | cls.exclude_serialize_fields) for o in objs]}
        # Отправляем запрос в Директ
        ids = getattr(self.ya_api, '%s_%s' % ('add', service))(params, client_login=self.account.login)
        for cmp, id in zip(objs, ids):
            change_id(cmp, id)

    def update_objects(self, obj_names, objs):

        if not objs:
            return
        cls = objs[0].__class__
        service = obj_names.lower()
        params = {obj_names: [o.serialize(exclude=cls.exclude_serialize_update_fields) for o in objs]}
        # Отправляем запрос в Директ
        ids = getattr(self.ya_api, '%s_%s' % ('update', service))(params, client_login=self.account.login)
        assert len(ids) == len(objs)
        for new_id, obj in zip(ids, objs):
            # если идентификатор изменился, меняем его
            # todo: проверить тестом
            if obj.id != id:
                change_id(obj, new_id)

    def change_object_states(self, obj_names, objs):
        # останавливает или включает объекты на основе стейта в базе
        if not objs:
            return
        cls = objs[0].__class__
        service = obj_names.lower()
        # останавливаем объекты
        suspend_params = {"SelectionCriteria": {'Ids': [o.id for o in objs if o.state == 'SUSPENDED']}}
        if suspend_params["SelectionCriteria"]['Ids']:
            # Отправляем запрос в Директ
            ids = getattr(self.ya_api, '%s_%s' % ('suspend', service))(suspend_params, client_login=self.account.login)
            assert len(ids) == len(suspend_params["SelectionCriteria"]['Ids'])
        # возобновляем объекты
        resume_params = {"SelectionCriteria": {'Ids': [o.id for o in objs if o.state == 'ON']}}
        if resume_params["SelectionCriteria"]['Ids']:
            ids = getattr(self.ya_api, '%s_%s' % ('resume', service))(resume_params, client_login=self.account.login)
            assert len(ids) == len(resume_params["SelectionCriteria"]['Ids'])

    def delete_objects(self, obj_names, ids):
        if not ids:
            return
        params = {"SelectionCriteria": {'Ids': ids}}
        res_ids = getattr(self.ya_api, '%s_%s' % ('delete', obj_names.lower()))(params, client_login=self.account.login)
        assert len(ids) == len(res_ids)

    def send_changes(self):
        # отправляем локальные изменения в базу для всех аккаунтов
        for account in Account.objects.exclude(disable=True).all():
            logging.info("Send yandex data for %s" % account.login)
            self.send_account_changes(account)

    def send_account_changes(self, account):
        """отправляем изменения из локальной базы в директ"""
        self.account = account
        sync_time = self.account.sync_time
        if not sync_time:
            sync_time = datetime.min
        # получаем изменения после синхронизации с аккаунтами

        # Кампании
        # Кампании создаютсы выключенными, их нужно включать отдельно
        self.send_objects_of_class('Campaigns', TextCampaign, q_filter=Q(account=self.account), sync_time=sync_time)

        q_filter_delete = Q(text_campaign__in=account.campaign_set)

        # Группы
        self.send_objects_of_class('AdGroups',
                                   AdGroup,
                                   q_filter=Q(campaign__account=self.account),
                                   sync_time=sync_time,
                                   update_q=Q(
                                       criterion__keyword__history__history_date__gt=sync_time),
                                   # получаем объекты, у которых изменены минус-фразы
                                   before_delete=partial(self.send_ads_and_keywords, sync_time))

    def send_ads_and_keywords(self, sync_time):
        # отдельно отправляет измнения в объявлениях и ключевиках, т.к. это надо делать до удаления групп
        # Объявления
        self.send_objects_of_class('Ads', TextAd, q_filter=Q(ad_group__campaign__account=self.account),
                                   sync_time=sync_time)

        # Ключевики
        self.send_objects_of_class('Keywords', Keyword, q_filter=Q(ad_group__campaign__account=self.account),
                                   sync_time=sync_time)

        # отправляем на модерацию объявления (можно только после создания условий показа)
        self.modrate_new_ads()

    def send_objects_of_class(self, obj_names, cls, q_filter, sync_time, update_q=None, before_delete=None):
        """
        Отправляет изменения объектов указанного класса из локальной базы в Директ
        :param cls:
        :param q_filter: q_filter - фильтр объектов, которые будут обрабатываться (они так же применяются к фильтрации истории, т.к. интерфейс истории такой же)
        :param q_filter: q_filter_delete - то же самое, только для удаления объектов. Отличия, потому что объекты ищутся через историю
        :param sync_time: Время последней синхронизации с сервером. Изменения после него надо отправить на сервер
        :param update_q: Дополнительный Q фильтр для выбора объектов, у которых изменены потомки
        :param before_delete: Функция, которая выполняется перед удалением. Нужна, т.к порядок удаления может отличаться от порядка создания, например для групп
        :return:
        """
        update_q = update_q or Q(pk=None)
        # получаем созданные объекты
        new = cls.objects.filter(q_filter, id__lt=0).all()
        # получяем объекты, которые изменялись после последней синхронизации и не были удалены или созданы c последней синхронизации
        # set нужен, потому что иначе updated может поменятся после создания объектов
        updated = set(cls.objects.filter(q_filter,
                                         Q(history__history_date__gt=sync_time,
                                           history__history_type='~')
                                         ).exclude(state='DELETE').difference(new).all())

        # дополнительно получае объект, которые фильтруются через update_q (то есть были изменены потомки, а не сами объекты)
        child_updated = set(cls.objects.filter(q_filter, update_q
                                               ).exclude(state='DELETE').difference(new).all())

        # разделяем изменения на стейт и другое
        state_changed = []  # список объектов, у которых изменен стейт (они остановлены или возобновлены)
        other_changed = set()  # список объектов, у которых изменены другие параметры
        # в группах и т.п. нельзя изменить стейт, так что все изменения в объектах
        if obj_names in ['AdGroups']:
            other_changed = updated
        # для остальных делим на стейт и остальные изменения
        else:
            for obj in updated:
                # получаем изменения после синхронизации
                last_histories = obj.history.filter(history_date__gt=sync_time).all()
                # сравниваем последнюю версию с объектом до начала изменений
                delta = last_histories.last().diff_against(last_histories[0].prev_record)
                # проверяем измененные поля
                if 'state' in delta.changed_fields:  # если изменилось поле стейт
                    state_changed.append(obj)
                if set(delta.changed_fields) - {'state'}:  # если изменились другие поля изи вложенные объекты
                    other_changed.add(obj)

        other_changed.update(child_updated)

        # получаем идентификаторы удаленных объектов
        delete_objects = cls.objects.filter(q_filter, history__history_date__gt=sync_time, state='DELETE')
        deleted_ids = list(delete_objects.values_list('id', flat=True))

        self.add_objects(obj_names, new)
        cls.objects.filter(q_filter, id__lt=0).delete()  # удаляем объекты со старыми идентификаторами
        self.update_objects(obj_names, list(other_changed))
        self.change_object_states(obj_names, state_changed)
        if before_delete:
            before_delete()
        self.delete_objects(obj_names, deleted_ids)
        delete_objects.delete()  # удаляем объекты из базы

    def modrate_new_ads(self):
        """
        Получаем из базы идентификаторы всех объевляений в статусе черновик и отправляем на модерацию
        :return:
        """
        ids = list(TextAd.objects.filter(status='DRAFT', ad_group__campaign__account=self.account).values_list('id',
                                                                                                               flat=True))
        if not ids:
            return
        params = {'SelectionCriteria': {'Ids': ids}}
        mod_ids = self.ya_api.moderate_ads(params, client_login=self.account.login)
        assert len(mod_ids) == len(ids)
        # обновляем статус
        for ad in TextAd.objects.filter(id__in=ids).all():
            ad.status = 'MODERATION'
            ad.save()

    def __getattr__(self, method_name):
        """
        Определяет функции suspend, archive, resume, unarchive для объектов. Названия функций такие же, как в директ апи, только в функцию передается список объектов, а не параметры
        Для архивации кампания должна быть остановлена и после этого должно пройти 60 мин.
        :param method_name:
        :return:
        """
        # соответствие метода статусу
        status_map={
            'archive':'ARCHIVED',
            'unarchive':'SUSPENDED',
            'suspend':'ARCHIVED',
            'resume':'ON',
        }
        def f(objects, *args, **kwarks):
            if not objects:
                return
            method = method_name.split('_', 1)[0]
            ids = [obj.id for obj in objects]
            params = {'SelectionCriteria': {'Ids': ids}}
            result_ids = getattr(self.ya_api,method_name)(params, client_login=self.account.login)
            assert len(result_ids) == len(ids)
            cls = objects[0].__class__

            for obj in cls.objects.filter(id__in=ids).all():
                obj.status = status_map[method]
                obj.save()

        return f


def change_id(obj, new_pk):
    """
    Создает объект с новым идентификатором и привязывает к нему все объекты, которые были связаны с объектом obj.
    Не удаляет объект со старым идентификатором.
    !!!Это надо сделать вручную!!!!
    :param obj:
    :param new_pk:
    :return:
    """
    # получаем названее полей, которые указывают на связанные объекты
    # получаем объекты
    related_objects = {}
    one_to_one_objects = {}
    for field in obj._meta.get_fields():
        # если обратная связь один к одному. Если объект существует то вернет один объект, иначе вызовет исключение.
        if issubclass(type(field), OneToOneRel):
            field_name = field.get_accessor_name()
            try:
                one_to_one_objects[field_name] = getattr(obj, field_name)
            except ObjectDoesNotExist:
                continue
        # для остальных связанных полей собираем список объектов
        elif issubclass(type(field), ForeignObjectRel):
            field_name = field.get_accessor_name()
            related_objects[field_name] = getattr(obj, field_name).all()

    # сохраняем новый объект, надо обновить и pk и id, т.к. при при multitable inheritance это разные значения. Будут пробемы если pk не id
    obj.id = new_pk
    obj.pk = new_pk
    obj.save()
    # обновляем id у связанных объектов
    for field_name, objects in related_objects.items():
        getattr(obj, field_name).set(objects)

    for field_name, object in one_to_one_objects.items():
        setattr(obj, field_name, object)
        object.save()  # из-за связи 1 к 1 сохранять надо объект, в котором хранится связанный id
    obj.save()
