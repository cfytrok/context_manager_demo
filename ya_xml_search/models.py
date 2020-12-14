from django.db import models


class YaXmlRequest(models.Model):
    class Meta:
        unique_together = ('query', 'region_id')

    query = models.CharField(max_length=255)
    region_id = models.IntegerField(null=True, blank=True)
    date = models.DateField(auto_now=True)
    found = models.BigIntegerField(null=True, blank=True)
    last_page = models.IntegerField(null=True, blank=True)  # последняя страница, которая есть в результатах


class Group(models.Model):
    domain = models.CharField(max_length=255)
    position = models.IntegerField()  # номер по порядку в выдаче
    request = models.ForeignKey(YaXmlRequest, on_delete=models.CASCADE, blank=True, null=True)


class Doc(models.Model):
    ya_doc_id = models.CharField(max_length=50)  # яндексовский идентификатор документа
    position = models.IntegerField()  # номер по порядку в выдаче
    url = models.URLField(max_length=1024)
    domain = models.URLField()
    title = models.TextField()
    headline = models.TextField()
    modtime = models.CharField(max_length=15)
    size = models.BigIntegerField()
    charset = models.CharField(max_length=16)
    passages_type = models.BooleanField()
    lang = models.CharField(max_length=3, blank=True)
    mime_type = models.CharField(max_length=100)
    saved_copy_url = models.URLField(max_length=1024)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, blank=True, null=True)


class Passage(models.Model):
    text = models.TextField()
    doc = models.ForeignKey(Doc, on_delete=models.CASCADE)
    position = models.IntegerField()
