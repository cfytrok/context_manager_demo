from django.db import models
from django.db.models import CASCADE, Sum

from unify_context.models import Program, Action


class AdmitadProgram(Program):
    """Площадка, с которой идет трафик в admitad"""
    site_url = models.URLField()
    rating = models.FloatField()  # рейтинг программы
    goto_cookie_lifetime = models.IntegerField()  # время жизни куки
    avg_money_transfer_time = models.IntegerField()  # среднее время от действия до оплаты за 360 дней
    avg_hold_time = models.IntegerField()  # среднее время от действия до обработки за 360 дней
    currency = models.CharField(max_length=3)  # валюта

class Website(models.Model):
    """Площадка, с которой идет трафик в admitad"""
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=50)
    program_set = models.ManyToManyField(AdmitadProgram, through='WebsiteProgram')

class WebsiteProgram(models.Model):
    """
    Параметры партнерской программы для отдельного сайта
    """
    website = models.ForeignKey(Website, on_delete=CASCADE)
    program = models.ForeignKey(AdmitadProgram, on_delete=CASCADE)

    gotolink = models.URLField()  # партнерская ссылка
    products_xml_link = models.URLField()


class AdmitadAction(Action):
    """
    Действия в адмитад. Лиды или продажи
    """



    website_name = models.CharField(max_length=50)

    @property
    def expected_payment(self):
        # ожидаемый заработок, если действие не подтверждено, иначе заработок
        if self.status == 'pending':
            return self.payment * self.program.expected_rate_of_approve  # заработок * вероятность подтверждения
        elif self.status == 'declined':
            return 0
        else:
            return self.payment

    def __repr__(self):
        return "<AdmitadAction(click_date='%s', criterion_id='%s', payment='%s')>" % (
            self.click_time, self.criterion_id, self.payment)



