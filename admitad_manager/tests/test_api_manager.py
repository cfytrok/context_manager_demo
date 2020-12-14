from django.test import TestCase

from admitad_manager.api_manager import AdmitadAPI
from admitad_manager.models import *
from unify_context.models import Program


class TestAPIManager(TestCase):
    def test_get_admitad_stats(self):
        AdmitadAPI().get_stats()

    def test_sync(self):
        # первый раз загружаем
        AdmitadAPI().get_websites()
        ws_cnt = Website.objects.count()
        self.assertGreater(ws_cnt, 0)

        AdmitadAPI().get_campaigns()
        program_cnt = Program.objects.count()
        self.assertGreater(program_cnt, 0)

        AdmitadAPI().get_stats()
        action_cnt = AdmitadAction.objects.count()
        self.assertGreater(action_cnt, 0)

        # второй раз обновляем
        AdmitadAPI().get_websites()
        self.assertEqual(Website.objects.count(), ws_cnt)
        AdmitadAPI().get_campaigns()
        self.assertEqual(Program.objects.count(), program_cnt)
        AdmitadAPI().get_stats()
        self.assertEqual(AdmitadAction.objects.count(), action_cnt)
