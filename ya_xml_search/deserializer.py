import xmltodict
from django.db import transaction
from django.db.models import Max
from .models import *
from tldextract import extract
from collections import OrderedDict


class XML_Deserializer:
    def __init__(self, xml, region_id):
        self._init_ids()
        edited_xml = xml.replace('</hlword>', '𝐁').replace('<hlword>', '𝐁')  # заменяем тэги на спецсимвол 𝐁
        yandex_dict = xmltodict.parse(edited_xml)['yandexsearch']
        self.groups = []  # группы формируются по домену
        self.docs = []
        self.passages = []
        with transaction.atomic():
            xml_request = self.deserialize_request(yandex_dict, region_id)

    def _init_ids(self):
        try:
            self.group_id = int(Group.objects.latest('id').id) + 1
        except:
            self.group_id = 0
        try:
            self.doc_id = int(Doc.objects.latest('id').id) + 1
        except:
            self.doc_id = 0
        try:
            self.passage_id = int(Passage.objects.last().id) + 1
        except:
            self.passage_id = 0

    def deserialize_request(self, xml_response, region_id=None):
        data = xml_response['request']
        r, _ = YaXmlRequest.objects.get_or_create(query=data['query'],
                                                  region_id=region_id)
        # Если документы найдены
        if 'found' in xml_response['response']:
            r.found = xml_response['response']['found'][0]['#text']
        else:
            r.found = 0
        r.last_page = max(r.last_page or 0, int(data['page']))
        r.save()
        if 'found' in xml_response['response']:
            response_data = xml_response['response']['results']['grouping']['group']
            groups_data = self.join_groups(guaranteed_list(response_data))
            last_position = r.group_set.aggregate(Max('position'))['position__max'] if r.group_set.exists() else 0
            for i, group_data in enumerate(groups_data):
                g = self.deserialize_group(group_data, position=i + last_position + 1)
                g.request = r
                self.groups.append(g)
        # Проверяем, есть ли группы с одинаковым доменом. Т.к. домен и субдомен могут оказаться в разных группах

        Group.objects.bulk_create(self.groups)
        Doc.objects.bulk_create(self.docs)
        Passage.objects.bulk_create(self.passages)
        return r

    def join_groups(self, groups):
        """
        Объединяем группы одного домена в одну
        # todo: при многостраничной выдаче могут создаваться дубликаты доменов. Что бы этого избежать надо пдтягивать группу из базы
        :param groups:
        :return:
        """
        g_dict = OrderedDict()
        for g in groups:
            docs = guaranteed_list(g['doc'])
            g['doc'] = docs
            subdomain, domain, suffix = extract(docs[0]['domain'])
            g['domain'] = domain + '.' + suffix
            # если домен уже найден
            if g['domain'] in g_dict:
                # переносим в него документы из текущего
                g_dict[g['domain']]['doc'].extend(docs)
            else:
                g_dict[g['domain']] = g
        return list(g_dict.values())

    # def deserialize_response(data):
    #     r = YaXmlResponse()
    #     r.id = data['reqid']
    #     r.date = data['@date']
    #     r.found = data['found'][0]['#text']
    #     r.save()
    #     page = int(data['results']['grouping']['page']['#text'])
    #     groups_on_page = int(data['results']['grouping']['@groups-on-page'])
    #     for i, group_data in enumerate(guaranteed_list(data['results']['grouping']['group'])):
    #         g = deserialize_group(group_data, position=i + page * groups_on_page)
    #         r.group_set.add(g)
    #     return r

    def deserialize_group(self, data, position):
        g = Group(id=self.group_id, domain=data['domain'])
        self.group_id += 1
        g.position = position
        for i, doc_data in enumerate(guaranteed_list(data['doc'])):
            d = self.deserialize_doc(doc_data, position=i)
            d.group = g
            self.docs.append(d)
        return g

    def deserialize_doc(self, data, position):
        init_dict = get_valid_init_dict(Doc, **data)
        d = Doc(**init_dict, id=self.doc_id)
        self.doc_id += 1
        d.ya_doc_id = data['@id']
        d.lang = data['properties'].get('lang', '')
        d.passages_type = data['properties'].get('_PassagesType', '')
        d.position = position
        # декодируем кириллицу
        old_domain = d.domain
        try:
            d.domain = d.domain.encode().decode('idna')
        except UnicodeError:
            pass # IDNA может некорректно декодироваться, тогда записывем домен как есть
        if old_domain != d.domain:
            d.url = d.url.replace(old_domain, d.domain)
        if 'passages' in data:
            for i, passage_data in enumerate(guaranteed_list(data['passages']['passage'])):
                p = Passage(text=passage_data, position=i, doc=d, id=self.passage_id)
                self.passage_id += 1
                self.passages.append(p)
        return d


def get_valid_init_dict(cls, **kwargs):
    """
    Оставляет только те аргументы, которые есть в модели.
    """
    field_names = {f.name for f in cls._meta.get_fields()}
    field_args = {k: v for k, v in kwargs.items() if k in field_names}
    return field_args


def guaranteed_list(x):
    if not x:
        return []
    elif isinstance(x, list):
        return x
    else:
        return [x]
