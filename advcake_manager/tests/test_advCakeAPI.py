from django.test import TestCase

from advcake_manager.api_manager import AdvCakeAPI
from advcake_manager.models import AdvCakeProgram,AdvCakeAction



class TestAdvCakeAPI(TestCase):
    def test_get_stats(self):
        AdvCakeAPI().get_stats()
        program = AdvCakeProgram.objects.first()
        self.assertEqual(program.name, 'skillbox')
        action_cnt=program.action_set.count()
        self.assertGreater(action_cnt, 0)
        # обновляем
        AdvCakeAPI().get_stats()
        self.assertEqual(action_cnt, AdvCakeAction.objects.count())
