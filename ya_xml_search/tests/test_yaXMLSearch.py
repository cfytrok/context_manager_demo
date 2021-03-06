from django.test import TestCase

from ya_xml_search.xml_search import YaXMLSearch


class TestYaXMLSearch(TestCase):
    def setUp(self) -> None:
        self.search = YaXMLSearch(domain='chistka-kovrov.ru', region_id=1, max_page=1)

    def test_get_domain_positions(self):
        queries = ['чистка ковров', 'почистить ковер']
        res = self.search.get_domain_positions(queries)
        self.assertEqual(len(res), len(queries))
        print(res)

    def test_get_query_domains(self):
        queries = ['чистка ковров', 'почистить ковер', 'настройка компьютеров']
        res = self.search.get_query_domains(queries, include_urls=['chistka-kovrov.ru'])
        self.assertEqual(len(res), len(queries)-1)
        self.assertEqual(len(res['чистка ковров']),1)
        self.assertEqual(len(res['почистить ковер']), 1)
        self.assertIsNone(res.get('настройка компьютеров', None))

        # запрашиваем все домены, найденные по запросу
        res2 = self.search.get_query_domains(queries)
        self.assertEqual(len(res2), len(queries))
        for v in res2.values():
            self.assertGreater(len(v), 90)
        print(res)

    def test_sandbox(self):
        queries = ['свежие объявления авто', 'hyundai creta', 'авто нова цена', 'выкуп автомобилей битые авто', 'объявления куплю', 'куплю продажа авто ру', 'модельный ряд китайских авто', 'выкуп авто скупка', 'купи продай', 'частные объявления куплю', 'частное продажа авто', 'купить пробег', 'область объявления пробегом', 'покупка продажа авто', 'авито объявления пробегом', 'продажа новых авто цена', 'авто объявления покупке', 'авто е1 область пробег свердловский', 'автомобиль покупка помощь', 'авито нижегородская область авто', 'распечатать куплю продажу авто', 'купить авто 0', 'договор куплю продажи авто', 'фото подать объявление', 'договор купли 2020', 'продажа автомобилей пробегом авто', 'залоговые автомобили', 'полировка', 'куплю продажу бланк', 'диалог авто', 'авто авторынок край краснодарский пробег частный', 'купить киа цены', 'автосалон авто', 'авто область', 'авто объявления цены', 'авто ру частные', 'бланк договора купли', 'авто сайт', 'выкуп продажа', 'авто ру челябинская область продажа', 'объявления куплю авто недорого', 'купить авто цена', 'бланк продажи автомобиля', 'авто выгодно', 'продажа матиз', 'купля продажа 2020', 'китайские авто', 'авто ру продажа автомобилей', 'авито область объявления', 'авто объявления ру', 'продажа авто фото цены', 'договор продажи автомобиля', 'бланк договора автомобиля', 'сайт автомобилей', 'авито купить объявление', 'срочно', 'авито пробегом частные', 'дан', 'выкуп автомобиля хендай солярис', 'дром челябинская область продажа авто', 'область продажа автомобилей', 'купить авто свежие объявления', 'продажа машин', 'люба', 'куплю продажу авто 2020', 'продажа авто цены', 'выкуп аварийных битых автомобилей', 'купить автомобиль', 'купить выкуп', 'купить авто цена фото', 'авточел ру', 'новые авто россии', 'куплю продажа', 'частное', 'продажи автомобилей 2020', 'объявления продажа авто ру', 'договор купли автомобиля', 'авто ваз', 'авто пробег юла', 'мото', 'выкуп авто хендай', 'авто купить новое цена', 'авито авто пробег', 'купить битое авто', 'хендай genesis', 'цена выкупа', '2020 бланк договор', 'куплю продажа авто образец', 'свежие', 'хендай цены', 'объявления продам', 'выкуп солярис', 'выкуп авто хендай солярис', 'объявление продажа', '2020 автомобиля договор', 'kz объявления продажа авто', 'продажа бланков договоров', 'авито авто купить', 'бланк купли продажи', 'авито авто купить цены', 'договор куплю продажи', 'авто продажа автомобилей', 'выкуп автомобилей хендай', 'авто скидка', 'е1 авто свердловская область', 'покупка авто цены', 'авто область объявления', 'частные объявления область', '2020 автомобиля купля', 'авто крым купить', 'выкуп продал', 'продаже авто бил', 'дром продажа авто', 'автомалиновка продажа авто цены', 'дром продажа объявления авто', 'выкуп авто дорога', 'купля продажа автомобиля', 'авито авто объявления', 'подать', 'срочный выкуп автомобилей', 'авито область пробегом', 'авито авто область', 'срочный выкуп авто дорого', 'продажа жк', 'бланк купли автомобиля', 'выкуп битых машин', 'подать объявление автомобиля', 'продам цена', 'genesis цена', 'авито область частные', 'авито авто нижегородский область пробег', '24 авто продажа', 'договор купли продажи', 'продажа продам', 'объявление дром куплю авто', 'объявление пробегом', '2020 автомобиля бланк', 'авто пробегом ру', 'куплю авто покупка', 'срочный выкуп авто', 'покупка машины', 'выкуп объявления', 'автосалон цена', 'выкуп автомобилей срочно авто', 'срочный выкуп битых автомобилей', 'фото авто', 'выкуп автомобилей скупка', 'договор купли автомобиля', 'пробегом ру частные', 'дром', 'область авто пробегом', 'выкуп любых авто', 'бесплатные объявления', 'область продажа авто', 'сайт знакомств', 'битые', '74 ru авто', 'авто официальный', 'автоподбор', 'бланк купли 2020', 'объявления пробегом ру', 'область пробегом частные', 'подбор авто', 'пробегом продам', 'арестованные автомобили', 'продажа нексия', 'под', 'авито авто', 'авито объявления частные', '2020 договор продажи', 'куплю пробегом частные', 'авто пробег', '0 алиэкспресс', 'частные объявления ру', 'срочные продажи авто', 'срочный выкуп битых авто', 'купить рено логан', 'авто крым продажа', '2020 бланк купли', 'авто пробегом продажа', '2020 бланк продажу', 'купить автомобиль 2020', 'abw', 'покупка автомобиля', 'автомобиль обмен', 'договор купли 2020', 'бланк купли автомобиля', 'авто область продажа челябинский', 'купля продажа 2020', 'авто пробегом частные', 'авто е1 пробег', 'продажа иномарок', 'бланки договора купли', 'автомобиль объявление', 'авто выкуп автомобилей', 'авто область частные', 'авто продавать', 'выкуп машина хендай солярис', 'скупка', 'куплю продажа авто бланк', 'ру', 'подам бесплатное объявление', 'купить авто частное', 'авто область пробег ру челябинский', 'срочный выкуп битых машин', 'бит', 'автовыкуп', 'автомобилей пробегом продажа', 'бюджетные авто', 'авто пробегом купить цена', 'авто аукцион купить япония', 'авито частные авто', 'авто лада', 'пробегом частные объявления', 'авто дром пробег', 'выкуп битых авто дорого', 'трейд ин авто', 'выгодный продавать', 'выкуп битых авто']
        search = YaXMLSearch(domain='carprice.ru', region_id=1, max_page=0)
        res = search.get_query_domains(queries)
        print(res)
