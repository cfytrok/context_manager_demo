#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import logging
import os
import sys


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'context_manager.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    # меняем рабочую папку на папку со скриптом
    script_directory = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_directory)
    # пишем логи в файл и в консоль
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s\t%(message)s',
                        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler('admitad.log')])
    main()
