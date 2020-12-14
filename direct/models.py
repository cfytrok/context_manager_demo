"""
!!!!!
Все деньги в базе хранятся в копейках при загрузке и отправке в Яндекс пересчитываются. В Яндекс данных хранятся в рублях * 1_000_000
!!!!!
Объекты, которые есть в базе, но нет в директе создаются с отрицательными идентификаторвами. После создания в директе эти объекты удаляются, создаются их копии с реальными идентификаторами. В связанных записях идентификаторы обновляются.
"""
import functools
import operator
from collections import OrderedDict
from datetime import date, timedelta

import inflection as inflection
from bulk_sync import bulk_sync
from django.db import models, transaction
from django.db.models import CASCADE, ManyToOneRel, ManyToManyRel, Sum, Q, ForeignObject, ManyToManyField
from django.db.models.fields.related import RelatedField
from django.db.models.fields.reverse_related import ForeignObjectRel
from django.db.models.functions import Coalesce
from django.forms import model_to_dict
from django.utils.functional import cached_property
from joinfield.joinfield import JoinField
from simple_history.models import HistoricalRecords
from simple_history.utils import bulk_create_with_history, bulk_update_with_history

from ads_manager.models import AdTemplate

INT_TYPES = {'IntegerField', 'BigIntegerField', 'AutoField', 'BigAutoField'}


class BulkHistoryManager(models.Manager):
    def bulk_create(self, objs, *args, **kwargs):
        # django не поддерживает bulk_create для моделей с multitabel inheritance. В этом случае просто сохраняем каждый объект.
        if is_multitabel_inheritance(self.model):
            # todo: очень тормознутое место. Адаптировать bulk_create для multitabel, что бы ускорить
            with transaction.atomic():
                for obj in objs:
                    obj.save()
            return objs

        # Что бы не остановить бесконечную рекурсию, добавляем флаг при первом вызове
        if hasattr(self, '_bulk_create_recursion'):
            return super().bulk_create(objs, *args, **kwargs)
        else:
            self._bulk_create_recursion = True
            res = bulk_create_with_history(objs, self.model, *args, **kwargs)
            del self._bulk_create_recursion
            return res

    def bulk_update(self, objs, *args, **kwargs):
        if hasattr(self, '_bulk_update_recursion'):
            return super().bulk_update(objs, *args, **kwargs)
        else:
            self._bulk_update_recursion = True
            res = bulk_update_with_history(objs, self.model, *args, **kwargs)
            del self._bulk_update_recursion
            return res


def is_multitabel_inheritance(cls):
    for parent in cls._meta.get_parent_list():
        if parent._meta.concrete_model is not cls._meta.concrete_model:
            return True
    return False


class APIParserMixing:
    exclude_serialize_fields = set()  # поля, которые не выводятся при сериализации
    exclude_serialize_update_fields = exclude_serialize_fields | set()  # дополнительные поля, которые исключаются при обновлении

    @classmethod
    def api_data_to_kwargs(cls, data):
        """
        Преобразует данные, которые возвращает API в словарь для инициализации объекта
        :param data:
        :return: возвращает словарь {field:value,}
        """
        params = {}
        fields = cls.field_names()
        for k, v in data.items():
            # преобразуем CamelCase название в under_score
            field_name = inflection.underscore(k)
            # если такого поля нет, ничего не делаем
            if field_name not in fields:
                continue
            field = cls._meta.get_field(field_name)
            field_type = field.get_internal_type()
            # Для текстовых полей None это ''
            if v is None and field_type in {'CharField', 'TextField', 'URLField'}:
                v = ''
            # если не None и у поля целое значение, приводим строку к целому
            if v is not None and (field_type in INT_TYPES or (field.is_relation and field.foreign_related_fields[
                0].get_internal_type() in INT_TYPES)):
                v = int(v)
            params[field_name] = v
        return params

    @classmethod
    def deserialize(cls, data):
        """
        Берет данные, которые возвращает апи, преобразует и передает их в конструктор класса
        :param data:
        :return: объект и имена параметров, которые были получены по апи
        """
        params = cls.api_data_to_kwargs(data)
        updated_fields = set(params.keys())
        updated_fields.discard(cls._meta.pk.name)  # удаляем primary key, т.к. обновить его нельзя
        obj = cls(**params)
        if is_multitabel_inheritance(cls):
            # устанавливаем id родительского объекта
            obj.pk = obj.id
            # убираем id, т.к. он является неявным primary key при multitable и bulk_update не будет работать
            updated_fields.discard('id')
        return obj, updated_fields

    def to_api_params(self):
        params = {inflection.camelize(k): v for k, v in self._meta.get_fields()}
        return params

    @classmethod
    def sync_response(cls, api_results, filter):
        """
        Обновляет и добавлет объекты, которые были получены по апи.
        :filter: Параметры фильтра - id объектов, которые были запрошены и тип id. Что бы удалять объекты, которые были запрошены но не были получены
        :return:
        """
        if not api_results:
            return

        # Собираем список классов с объектами, которые надо изменить и другими параметрами.
        cls.modified_objects = OrderedDict()  # {class:{'objects':[objects], 'fields':[str]}}. OrderedDict, чтобы сначала создать родительские объекты, потом дочерние

        # десериализируем объекты в ответе
        for item in api_results:
            # получаем объект и поля, которые вернул директ
            obj, recieved_fields = cls.deserialize(item)
            cls.modified_objects.setdefault(cls, {}).setdefault('objects', []).append(obj)
            # десериализируем вложенные объекты
            cls.deserialize_nested(obj, item, filter)

        cls.modified_objects[cls]['fields'] = recieved_fields
        cls.modified_objects[cls]['key_fields'] = ['pk']
        cls.modified_objects[cls]['filter'] = filter

        # синхронизируем с базой (создаем, обновляем, удаляем)
        for db_class, data in cls.modified_objects.items():
            bulk_sync(new_models=data['objects'],
                      key_fields=data['key_fields'],
                      filters=Q(**data['filter']),
                      fields=data['fields'],
                      )

    @classmethod
    def deserialize_nested(cls, obj, item, filter):
        """
        Отвечает за десериализацию вложенных объектов. Переопределяется в классах-потомках
        :param obj: родительский объект
        :param item: ответ сервера с одним объектом
        :param filter: фильтры, объектов, которые были запрошены
        :return:
        """
        pass

    @classmethod
    def field_names(cls):
        return {f.attname for f in cls._meta.get_fields() if
                not isinstance(f, ManyToOneRel) and not isinstance(f, ManyToManyRel)}

    def serialize(self, exclude=None, include_null=False):
        """
        Переобразует модель базы данных в объект для отправки в директ
        :param exclude: название полей, которые нужно исключить
        :param include_null: выводить ли поля без значений
        :return:
        """
        # получаем все поля
        d = self.__dict__

        # получаем названия полей модели, исключая поля, один ко многим. То есть получаем поля которые, хранятся в таблице.
        model_field_names = [field.attname for field in self._meta.get_fields() if
                             not issubclass(type(field),
                                            ForeignObjectRel)]  # not issubclass(type(field), RelatedField) and not issubclass(type(field), ForeignObject)]
        # переводим в CamelCase, удаляем поля с пустыми значениями
        return {inflection.camelize(name): getattr(self, name) for name in model_field_names if
                not (exclude and name in exclude) and (include_null or getattr(self, name))}


class Region(models.Model, APIParserMixing):
    """
    Регион Директа
    """
    TYPE_CHOICES = [(c, c) for c in ["World", "Continent", "Region",
                                     "Country", "Administrative area",
                                     "District", "City", "City district", "Village"]]

    id = models.BigIntegerField(primary_key=True)
    geo_region_name = models.CharField(max_length=255)
    parent = models.ForeignKey("self", on_delete=CASCADE, null=True, blank=True)  # родительский регион
    geo_region_type = models.CharField(max_length=20, choices=TYPE_CHOICES)

    @classmethod
    def deserialize(cls, data):
        modified_data = data
        modified_data['id'] = data.pop('GeoRegionId')
        return super().deserialize(modified_data)


class Account(models.Model):
    login = models.CharField(max_length=50, primary_key=True)
    auth_token = models.CharField(max_length=200)
    # При сохранении в Acceess записей с DateTimeField возможны проблемы из-за разной точности временной метки подробнее: https://coderoad.ru/25088970/MS-Access-ODBC-%D1%81-%D0%BA%D0%BE%D0%BD%D1%84%D0%BB%D0%B8%D0%BA%D1%82%D0%BE%D0%BC-%D0%B7%D0%B0%D0%BF%D0%B8%D1%81%D0%B8-%D0%B2-%D1%82%D0%B0%D0%B1%D0%BB%D0%B8%D1%86%D1%83-PostgreSQL
    last_campaigns_changes_time = models.DateTimeField(null=True,
                                                       blank=True)  # Timestamp последней проверки изменний в кампаниях на сервере, которое сохранено в базе
    last_dictionaries_changes_time = models.DateTimeField(null=True,
                                                          blank=True)  # Timestamp последней проверки изменений в словарях
    sync_time = models.DateTimeField(null=True,
                                     blank=True)  # время завершения загрузки данных из директа
    disable = models.BooleanField(default=False)  # обрабатывать ли аккаунт в программах

    def __repr__(self):
        return "<Account(login='%s')>" % (self.login)


class Campaign(models.Model, APIParserMixing):
    """
    Кампания директа. Свойства отдельных типов кампаний (DynamicCampaign) хранятся в отдельных моделях и ссылаются на эту через foreignkey
    """

    STATE_CHOICES = [(c, c) for c in ["ARCHIVED", "CONVERTED", "ENDED", "OFF", "ON", "SUSPENDED", "UNKNOWN",
                                      'DELETE']]  # статус DELETE нет в директе, он нужен для удаления объекта
    STATUS_CHOICES = [(c, c) for c in ["ACCEPTED", "DRAFT", "MODERATION", "REJECTED", "UNKNOWN"]]
    TYPE_CHOICES = [(c, c) for c in
                    ["TEXT_CAMPAIGN", "MOBILE_APP_CAMPAIGN", "DYNAMIC_TEXT_CAMPAIGN", "SMART_CAMPAIGN", "UNKNOWN"]]
    BUDGET_MODE_CHOICES = [(c, c) for c in ["STANDARD", "DISTRIBUTED"]]

    id = models.BigIntegerField(primary_key=True)  # идентификтор в директе
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=255, blank=True, choices=STATUS_CHOICES)
    state = models.CharField(max_length=255, blank=True, choices=STATE_CHOICES)
    account = models.ForeignKey(Account, on_delete=CASCADE)
    type = models.CharField(max_length=255, blank=True, choices=TYPE_CHOICES)
    start_date = models.DateField(auto_now_add=True)
    daily_budget_amount = models.IntegerField(blank=True, null=True)  # дневной бюджет  в коп.
    daily_budget_mode = models.CharField(max_length=255, blank=True, choices=BUDGET_MODE_CHOICES)

    @classmethod
    def deserialize(cls, data):
        modified_data = data
        blocked_ips = modified_data.pop('BlockedIps')
        excluded_sites = modified_data.pop('ExcludedSites')
        negative_keywords = modified_data.pop('NegativeKeywords')
        daily_budget = modified_data.pop('DailyBudget')
        campaign, update_fields = super().deserialize(modified_data)
        if daily_budget:
            campaign.daily_budget_amount = daily_budget['Amount'] / 10_000
            campaign.daily_budget_mode = daily_budget['Mode']
            update_fields.add('daily_budget_amount')
            update_fields.add('daily_budget_mode')
        return campaign, update_fields

    def __repr__(self):
        return "<Campaign(id='%s', name='%s')>" % (self.id, self.name)

    def serialize(self, *args, **kwargs):
        ser_campaign = super().serialize(*args, **kwargs)
        if 'StartDate' in ser_campaign:
            ser_campaign['StartDate'] = ser_campaign['StartDate'].isoformat()
        return ser_campaign


class TextCampaign(Campaign):
    log = HistoricalRecords(related_name='history')
    objects = BulkHistoryManager()
    exclude_serialize_fields = {'account_id', 'campaign_ptr_id'}

    def serialize(self, *args, **kwargs):
        ser_campaign = super().serialize(*args, **kwargs)
        ser_campaign['TextCampaign'] = {
            "BiddingStrategy": {
                "Search": {
                    "BiddingStrategyType": "HIGHEST_POSITION"
                },
                "Network": {
                    "BiddingStrategyType": "SERVING_OFF",
                }
            }
        }
        return ser_campaign


# class CampaignNegativeKeywords(models.Model):
#     text = models.CharField(max_length=255)
#     campaign = models.ForeignKey(TextCampaign, on_delete=CASCADE)
#
#
# class CampaignBlockedIps(models.Model):
#     ip = models.CharField(max_length=255)
#     campaign = models.ForeignKey(TextCampaign, on_delete=CASCADE)
#
#
# class CampaignExcludedSites(models.Model):
#     url = models.URLField()
#     campaign = models.ForeignKey(TextCampaign, on_delete=CASCADE)


class AdGroup(models.Model, APIParserMixing):
    """
    Класс для групп объявлений всех видов. Здесь хранится общая информация. Детальная информация по конкретным типам групп хранится в отдельной модели, которая ссылакется на эту через ForeignKey
    """
    STATUS_CHOICES = [(c, c) for c in ["ACCEPTED", "DRAFT", "MODERATION", "PREACCEPTED", "REJECTED",
                                       'DELETE']]  # статус DELETE нет в директе, он нужен для удаления объекта
    SERVING_CHOICES = [(c, c) for c in ["ELIGIBLE", "RARELY_SERVED"]]
    STATE_CHOICES = [(c, c) for c in ["DELETE"]]

    exclude_serialize_fields = {'status', 'state', 'serving_status', 'regions'}  # поля, которые не будут сериализованы
    exclude_serialize_update_fields = exclude_serialize_fields | {'campaign_id'}

    id = models.BigIntegerField(primary_key=True)  # идентификтор в директе
    campaign = models.ForeignKey(Campaign, on_delete=CASCADE)
    name = models.CharField(max_length=255)
    state = models.CharField(max_length=255, blank=True,
                             choices=STATE_CHOICES)  # такого свойства нет в директе, нужен только для удаления
    status = models.CharField(max_length=255, blank=True, choices=STATUS_CHOICES)
    serving_status = models.CharField(max_length=255, blank=True, choices=SERVING_CHOICES)
    regions = models.ManyToManyField(Region)
    log = HistoricalRecords(related_name='history')
    objects = BulkHistoryManager()

    @classmethod
    def deserialize_nested(cls, obj, data, parent_filter):
        # создаем объекты минус-фразы и добавляем в списко необработанных объектов
        if not data['NegativeKeywords']:
            return
        for kw in data['NegativeKeywords']:
            cls.modified_objects.setdefault(GroupNegativeKeyword, {}).setdefault('objects', []).append(
                GroupNegativeKeyword(ad_group_id=obj.id, text=kw))

        cls.modified_objects[GroupNegativeKeyword]['fields'] = ['ad_group_id', 'text']
        cls.modified_objects[GroupNegativeKeyword]['key_fields'] = ['ad_group_id', 'text']
        cls.modified_objects[GroupNegativeKeyword]['filter'] = {'ad_group__' + k: v for k, v in parent_filter.items()}

    def __repr__(self):
        return "<AdGroup(id='%s', name='%s')>" % (self.id, self.name)

    def serialize(self, *args, **kwargs):
        gr_serialization = super().serialize(*args, **kwargs)
        # добавлем регионы
        gr_serialization["RegionIds"] = list(self.regions.values_list('id', flat=True))
        # добавляем минус-фразы
        for neg_kw in self.groupnegativekeyword_set.all():
            gr_serialization.setdefault("NegativeKeywords", {"Items": []})['Items'].append(neg_kw.text)
        return gr_serialization

    def delete_direct(self):
        self.state = 'DELETE'
        self.save()
        for ad in self.textad_set.all():
            ad.state = 'DELETE'
            ad.save()
        for kw in Keyword.objects.filter(ad_group=self).all():
            kw.state = 'DELETE'
            kw.save()


class GroupNegativeKeyword(models.Model):
    ad_group = models.ForeignKey(AdGroup, on_delete=CASCADE)
    text = models.CharField(max_length=255)

    log = HistoricalRecords(related_name='history')
    objects = BulkHistoryManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['ad_group', 'text'], name='unique_group_negative_keyword')
        ]


class Criterion(models.Model, APIParserMixing):
    id = models.BigIntegerField(primary_key=True)  # идентификтор в директе
    ad_group = models.ForeignKey(AdGroup, on_delete=CASCADE)

    @cached_property
    def actual_payment_sum(self):
        # сумма оплат по критерию за год, если б ставки были как сейчас
        year_ago = date.today() - timedelta(days=365)
        payment_sum = sum([a.actual_payment for a in self.action_set.filter(payment__gt=0,
                                                                            status__in=['approved',
                                                                                        'approved_but_stalled'],
                                                                            click_time__date__gte=year_ago).all()])
        return payment_sum


class Keyword(Criterion):
    STRATEGY_PRIORITY_CHOICES = [(c, c) for c in ["LOW", "NORMAL", "HIGH"]]
    STATE_CHOICES = [(c, c) for c in ["OFF", "ON", "SUSPENDED",
                                      "DELETE"]]  # статус DELETED в Яндекс не существует. При удалении фразы ее не получить, она видна только в статистике. При изменении текста фразы, фраза удаляется и создается новая с другим идентификатором.
    STATUS_CHOICES = [(c, c) for c in ["ACCEPTED", "DRAFT", "REJECTED", "UNKNOWN"]]
    SERVING_CHOICES = [(c, c) for c in ["ELIGIBLE", "RARELY_SERVED"]]

    exclude_serialize_fields = {'criterion_ptr_id'}
    exclude_serialize_update_fields = exclude_serialize_fields | {'ad_group_id'}

    text = models.CharField(max_length=4096)
    bid = models.IntegerField(blank=True, null=True)  # ставка в копейках
    context_bid = models.IntegerField(blank=True, null=True)  # ставка в сетях в копейках
    strategy_priority = models.CharField(max_length=6, choices=STRATEGY_PRIORITY_CHOICES, blank=True)
    user_param1 = models.CharField(max_length=255, blank=True)
    user_param2 = models.CharField(max_length=255, blank=True)
    state = models.CharField(max_length=255, blank=True, choices=STATE_CHOICES)
    status = models.CharField(max_length=255, blank=True, choices=STATUS_CHOICES)
    serving_status = models.CharField(max_length=255, blank=True, choices=SERVING_CHOICES)
    log = HistoricalRecords(related_name='history')
    objects = BulkHistoryManager()

    @classmethod
    def deserialize(cls, data):
        modified_data = data
        modified_data['Bid'] = modified_data['Bid'] / 10_000  # переводим в копейки
        modified_data['ContextBid'] = modified_data['ContextBid'] / 10_000  # переводим в копейки
        modified_data['Text'] = modified_data['Keyword']
        obj, fields = super().deserialize(modified_data)
        return obj, fields

    def serialize(self, *args, **kwargs):
        keyword_serialization = super().serialize(*args, **kwargs)
        keyword_serialization['Keyword'] = keyword_serialization.pop('Text')
        return keyword_serialization

    def __repr__(self):
        return "<DirectKeyword(keyword='%s', bid='%s')>" % (
            self.keyword, self.bid or self.context_bid)


class DynamicFeedAdTarget(Criterion):
    # условие нацеливания для динамических объявлений по фиду. У директа пока нет API для этого класса, управление только через интерфейс

    min_price = models.IntegerField(blank=True, null=True)  # минимальная стоимость товара в фильтре
    rate = models.FloatField(blank=True, null=True)  # тариф программы по товарам в фильтре
    name = models.CharField(max_length=4096)  # название фильтра

    @cached_property
    # Ожидаемый заработок для действия.
    # Условия нацеливания поделены по стоимости товара. Это значение можно считать ценностью действия от минимальной стоимости товара в группе
    def expected_payment(self):
        return self.min_price * self.rate

class DirectAdTemplate(AdTemplate):
    """Шаблон объявления директа"""
    title = models.TextField()
    title2 = models.TextField(blank=True)
    text = models.TextField()
    href = models.TextField()  # ссылка на страницу рекламодателя (без трекинговых ссылок)

class TextAd(models.Model, APIParserMixing):
    # После создания объявления - state = OFF, т.к не прошло модерацию status = DRAFT
    # После отправки на модераци state = OFF, status = MODERATION
    # Остановить можно только объявление, которое прошло модерацию. Иначе объявление можно удалить.

    STATE_CHOICES = [(c, c) for c in ["OFF", "ON", "SUSPENDED", "OFF_BY_MONITORING", "ARCHIVED", "UNKNOWN",
                                      'DELETE']]  # статус DELETE нет в директе, он нужен для удаления объекта
    STATUS_CHOICES = [(c, c) for c in ["ACCEPTED", "DRAFT", "MODERATION", "PREACCEPTED", "REJECTED", "UNKNOWN"]]
    MOBILE_CHOICES = [(c, c) for c in ["YES", "NO"]]

    exclude_serialize_fields = {'state', 'status', 'status_clarification'}
    exclude_serialize_update_fields = exclude_serialize_fields | {'ad_group_id', 'mobile'}

    id = models.BigIntegerField(primary_key=True)  # идентификтор в директе
    ad_group = models.ForeignKey(AdGroup, on_delete=CASCADE)
    state = models.CharField(max_length=255, blank=True, choices=STATE_CHOICES, default='OFF')
    status = models.CharField(max_length=255, choices=STATUS_CHOICES, default='DRAFT')
    status_clarification = models.TextField(blank=True)
    title = models.CharField(max_length=40)
    title2 = models.CharField(max_length=40, blank=True)
    text = models.CharField(max_length=128)
    href = models.URLField(max_length=1024)
    mobile = models.CharField(max_length=3, choices=MOBILE_CHOICES, default='NO')
    display_domain = models.URLField(blank=True)
    display_url_path = models.CharField(max_length=20, blank=True)
    v_card_id = models.BigIntegerField(blank=True, null=True)
    ad_image_hash = models.CharField(max_length=40, blank=True)
    log = HistoricalRecords(related_name='history')
    objects = BulkHistoryManager()

    @classmethod
    def deserialize(cls, data):
        unpacked_data = data
        unpacked_data.update(unpacked_data['TextAd'])
        unpacked_data.pop('TextAd')
        return super().deserialize(unpacked_data)

    def serialize(self, *args, **kwargs):
        text_ad_serialization = super().serialize(*args, **kwargs)
        ad_serialization = {'TextAd': text_ad_serialization}
        if 'AdGroupId' in text_ad_serialization:
            ad_serialization['AdGroupId'] = text_ad_serialization.pop('AdGroupId')
        if 'Id' in text_ad_serialization:
            ad_serialization['Id'] = text_ad_serialization.pop('Id')
        return ad_serialization

    def __repr__(self):
        return "<TextAd(title='%s', href='%s')>" % (
            self.title, self.href)


class DirectStats(models.Model, APIParserMixing):
    """
    Статистика директа
    """
    DEVICE_CHOICES = [(c, c) for c in ["desktop", "mobile", "tablet"]]
    GENDER_CHOICES = [(c, c) for c in ["GENDER_MALE", "GENDER_FEMALE", "UNKNOWN"]]
    AGE_CHOICES = [(c, c) for c in
                   ["AGE_0_17", "AGE_18_24", "AGE_25_34", "AGE_35_44", "AGE_45", "AGE_45_54", "AGE_55", "UNKNOWN"]]
    CARIER_CHOICES = [(c, c) for c in ["CELLULAR", "STATIONARY", "UNKNOWN"]]
    MOBILE_PLATFORM_CHOICES = [(c, c) for c in ["ANDROID", "IOS", "OTHER", "UNKNOWN"]]
    SLOT_CHOICES = [(c, c) for c in ["PREMIUMBLOCK", "OTHER"]]

    id = models.BigAutoField(primary_key=True)
    date = models.DateField()
    shows = models.IntegerField()
    clicks = models.IntegerField()
    region_id = models.IntegerField()
    device = models.CharField(max_length=20, choices=DEVICE_CHOICES)
    campaign = JoinField(Campaign, on_delete=CASCADE)
    group = JoinField(AdGroup, on_delete=CASCADE)
    ad = JoinField(TextAd, on_delete=CASCADE)
    criterion = JoinField(Criterion, on_delete=CASCADE)
    keyword = models.CharField(max_length=255, blank=True)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES)
    age = models.CharField(max_length=20, choices=AGE_CHOICES)
    carrier_type = models.CharField(max_length=20, choices=CARIER_CHOICES)
    mobile_platform = models.CharField(max_length=20, choices=MOBILE_PLATFORM_CHOICES)
    slot = models.CharField(max_length=20, choices=SLOT_CHOICES)

    @classmethod
    def deserialize(cls, data):
        modified_data = data
        modified_data['region_id'] = modified_data.pop('TargetingLocationId')
        modified_data['Device'] = modified_data.pop('Device').lower()
        modified_data['GroupId'] = modified_data.pop('AdGroupId')
        modified_data['Date'] = date.fromisoformat(modified_data.pop('Date'))
        modified_data['Shows'] = modified_data.pop('Impressions')
        return super().deserialize(modified_data)

    def __repr__(self):
        return "<DirectStats(date='%s', criterion_id='%s', clicks='%s')>" % (
            self.date, self.criterion_id, self.clicks)


def multi_field_in(object_list):
    """
    Создает запрос аналог __in object_list для нескольких полей. object_list - список словарей. В словаре пары название поля - значение
    :param object_list:
    :return:
    """
    return functools.reduce(
        operator.or_,
        (Q(**values) for values in object_list)
    )
