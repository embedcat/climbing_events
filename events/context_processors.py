from django.conf import settings


def analytics(request):
    """ Номер счётчика Метрики для шаблонов; пустой — счётчик не подключаем (тестовый сайт) """
    return {'METRIKA_ID': settings.METRIKA_ID}
