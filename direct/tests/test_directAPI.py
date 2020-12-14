import datetime
from collections import OrderedDict

from django.test import TestCase

from direct.api_manager import DirectAPI
from direct.models import *
from unify_context.models import ProgramCampaign, Program
from django.conf import settings


class TestDirectAPI(TestCase):

    def setUp(self) -> None:
        self.api = DirectAPI(accounts=OrderedDict({settings.DIRECT['login']: settings.DIRECT['token']}),
                             sandbox=True)
        self.acc = Account.objects.create(login=settings.DIRECT['login'], auth_token=settings.DIRECT['token'])
        # создаем программу адмитад
        self.program = Program.objects.create(name='tests', site_url='ya.ru', rating=1, ecpc=1, cr=1,
                                              rate_of_approve=1, goto_cookie_lifetime=90, avg_money_transfer_time=10,
                                              avg_hold_time=10,
                                              currency='RUB')


    def test_load_data(self):
        self.api.load_data()
        # for i in range(2):
        #     api.get_campaigns()
        #     for cmp in Campaign.objects.all():
        #         api.get_ad_groups(cmp.id)
        #         api.get_text_ads(cmp.id)
        #         api.get_keywords(cmp.id)
        #         api.get_stats()
        self.assertGreater(Region.objects.count(), 0)
        self.assertGreater(TextCampaign.objects.count(), 0)
        self.assertGreater(AdGroup.objects.count(), 0)
        self.assertGreater(GroupNegativeKeyword.objects.count(), 0)
        self.assertGreater(TextAd.objects.count(), 0)
        self.assertGreater(Keyword.objects.count(), 0)
        #self.assertGreater(DirectStats.objects.count(), 0)

        # архивируем кампанию
        cmp=TextCampaign.objects.filter(state__in=['ON','OFF']).first()
        self.api.archive_campaigns([cmp])

        # загружаем данные повторно, что б проверить запрос изменений
        self.api.load_data()

        # активируем каманию
        self.api.unarchive_campaigns([cmp])

        self.api.load_data()

    def test_get_stats(self):
        api = DirectAPI()
        api.get_stats()
        self.assertGreater(DirectStats.objects.count(), 0)

    def test_send_changes(self):

        # создаем программу адмитад
        self.program = Program.objects.create(name='tests', site_url='ya.ru', rating=1, ecpc=1, cr=1,
                                              rate_of_approve=1, goto_cookie_lifetime=90, avg_money_transfer_time=10,
                                              avg_hold_time=10,
                                              currency='RUB')

        # создаем кампанию в базе
        cmp_id = -TextCampaign.objects.filter(id__lt=0).count() - 1
        cmp = TextCampaign.objects.create(name='tests', account=self.acc, id=cmp_id)
        ProgramCampaign.objects.create(direct_campaign=cmp, program=self.program) # привязываем к программе
        cmp.save()
        reg = Region.objects.create(id=0, geo_region_name='All',geo_region_type='World')
        gr_id = -AdGroup.objects.filter(id__lt=0).count() - 1
        group = AdGroup.objects.create(name='test_gr', campaign=cmp, id=gr_id)
        group.regions.add(reg)
        group.groupnegativekeyword_set.create(text='стоп фраза')
        ad_id = -TextAd.objects.filter(id__lt=0).count() - 1
        ad = TextAd.objects.create(ad_group=group, title='tests', title2='test2', text='tests text', mobile='NO',
                                   id=ad_id, href='http://ya.ru')
        kw_id = -Keyword.objects.filter(id__lt=0).count() - 1
        kw = Keyword.objects.create(ad_group=group, text='ключевое слово', id=kw_id)
        # отправляем в директ
        self.api.send_account_changes(self.acc)
        # проверяем, что id обновились
        self.assertEqual(TextCampaign.objects.count(), 1)
        cmp = TextCampaign.objects.first()
        self.assertEqual(cmp.programcampaign.program_id, self.program.id)
        self.assertGreater(cmp.id, 0)
        self.assertEqual(cmp.adgroup_set.count(), 1)
        gr = cmp.adgroup_set.first()
        self.assertGreater(gr.id, 0)
        self.assertEqual(gr.textad_set.count(), 1)
        self.assertGreater(gr.textad_set.first().id, 0)
        self.assertEqual(Keyword.objects.filter(ad_group=gr).count(), 1)
        self.assertGreater(Keyword.objects.filter(ad_group=gr).first().id, 0)

        # вносим изменения
        self.acc.sync_time=datetime.datetime.now()
        self.acc.save()
        # изменяем ключевое слово
        kw=Keyword.objects.filter(ad_group=gr).first()
        kw.text='ключевая фраза'
        kw.save()
        # изменяем объевление
        ad = gr.textad_set.first()
        ad.title='Измененный заголовок'
        # останавливаем объявление (нельзя останавить объявление, если оно не отправлено на модерацию)
        ad.state='SUSPENDED'
        ad.save()
        # изменяем минус фразы на группу
        nf=gr.groupnegativekeyword_set.first()
        nf.text='изменная фраза'
        nf.save()
        # отправляем в директ
        self.api.send_account_changes(self.acc)

        # вносим изменения
        self.acc.sync_time = datetime.datetime.now()
        self.acc.save()
        # включаем объявление
        ad = gr.textad_set.first()
        ad.state = 'ON'
        ad.save()
        # отправляем в директ
        self.api.send_account_changes(self.acc)

        # удаляем группу
        self.acc.sync_time = datetime.datetime.now()
        self.acc.save()
        gr.delete_direct()

        self.assertEqual(Keyword.objects.last().state,'DELETE')
        self.assertEqual(TextAd.objects.last().state,'DELETE')
        self.assertEqual(AdGroup.objects.last().state,'DELETE')
        # отправляем в директ
        self.api.send_account_changes(self.acc)
        self.assertEqual(Keyword.objects.count(), 0)
        self.assertEqual(TextAd.objects.count(), 0)
        self.assertEqual(AdGroup.objects.count(), 0)

        # Загружаем данные
        #проверить корректность изменение статусов объявлений на модерации



