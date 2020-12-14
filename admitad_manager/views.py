import csv
from django.http import HttpResponse

from unify_context.models import Action


def google_conversions(request):
    """
    Возвращает список конверсий в csv формате. Отображаются все действия с ожидаемой ценностью. Ожидаемая ценность считается на момент загрузки.
    При повторной загрузке гугл не обновит ценность конверсии. Для её обновления нужно загрузить корректировку
    :param request:
    :return:
    """

    # Create the HttpResponse object with the appropriate CSV header.
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="conversions.csv"'

    writer = csv.writer(response)
    # указываем timezone
    writer.writerow(['Parameters:TimeZone=Europe/Moscow',])
    # шапка
    writer.writerow(['Google Click ID','Conversion Name','Conversion Time','Conversion Value','Conversion Currency'])

    # получаем конверсии гугла, в которых были gclid
    actions = Action.objects.filter(source='google').exclude(click_id='')
    for action in actions:
        writer.writerow(
            [action.click_id, 'Action', action.action_time.strftime('%Y-%m-%d %H:%M:%S'), action.expected_payment/100, 'RUB'])
    return response


def google_conversion_adjustments(request):
    """
    Возвращает исправляения для конверсий гугла в формате csv после дотверждения действия
    :param request:
    :return:
    """

    # Create the HttpResponse object with the appropriate CSV header.
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="conversion_adjustments.csv"'

    writer = csv.writer(response)
    # указываем timezone
    writer.writerow(['Parameters:TimeZone=Europe/Moscow',])
    # шапка
    writer.writerow(['Google Click ID','Conversion Name','Conversion Time','Adjustment Time','Adjustment Type','Adjusted Value','Adjusted Value Currency'])

    # получаем конверсии гугла, в которых были gclid и произошла обработка
    actions = Action.objects.filter(source='google').exclude(click_id='').exclude(status='pending')
    for action in actions:
        writer.writerow(
            [action.click_id,
             'Action',
             action.action_time.strftime('%Y-%m-%d %H:%M:%S'),
             action.closing_time.strftime('%Y-%m-%d %H:%M:%S'), # время обработки действия
             'RESTATE',action.expected_payment/100, 'RUB'])
    return response