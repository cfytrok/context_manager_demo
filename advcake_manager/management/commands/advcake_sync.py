
from django.core.management.base import BaseCommand
from advcake_manager.api_manager import AdvCakeAPI


class Command(BaseCommand):
    help = 'Загружает статистику действий в AdvCake'

    def handle(self, *args, **options):
        AdvCakeAPI().sync()

