import logging

from django.core.management.base import BaseCommand

from admitad_manager.api_manager import AdmitadAPI


class Command(BaseCommand):
    help = 'Загружает статистику действий в admitad'

    def handle(self, *args, **options):
        AdmitadAPI().sync()

