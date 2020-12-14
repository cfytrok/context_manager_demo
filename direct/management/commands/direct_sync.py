from collections import OrderedDict

from django.core.management.base import BaseCommand

from direct.api_manager import *


class Command(BaseCommand):
    help = 'Загружает статистику действий в admitad'

    def handle(self, *args, **options):
        accs = OrderedDict([(acc.login, acc.auth_token) for acc in Account.objects.exclude(disable=True).all()])
        api = DirectAPI(accounts = accs)
        api.load_data()
