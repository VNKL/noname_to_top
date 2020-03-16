""" Use python 3.7 """


def listens_rate(ads_stat):
    """
    Возвращает конверсию из охвата объявлений в прослушивания плейлистов в виде
    {ad_id: listens_rate}

    """
    listens_rate = {}
    for ad_id, stat in ads_stat.items():
        reach = stat['reach']
        listens = stat['listens']
        rate = round((listens / reach * 100), 2)
        listens_rate[ad_id] = rate
    return listens_rate


def listens_cost(ads_stat):
    """
    Возвращает стоимость одного прослушивания по каждому объявлению в виде
    {ad_id: listen_cost}

    """
    listens_cost = {}
    for ad_id, stat in ads_stat.items():
        spent = stat['spent']
        listens = stat['listens']
        cost = round((spent / listens), 2)
        listens_cost[ad_id] = cost
    return listens_cost


class Calculator:

    def __init__(self, target_rate=0.04, stop_rate=0.03, target_cost=1., stop_cost=2., cpm_step=10.):
        self.target_rate = target_rate
        self.stop_rate = stop_rate
        self.target_cost = target_cost
        self.stop_cost = stop_cost
        self.cpm_step = cpm_step

    def updates_for_rate_target(self, ads_stat):
        """
        Возвращает новые CPM для объявлений + список объявлений, которые нужно остановить,
        выполняя цель по конверсии из охвата в прослушивания

        :param ads_stat:    dict - {ad_id: {'name': str, 'spent': float, 'reach': int, 'cpm': cpm}}

        :return:            ({ad_id: new_cpm}, [ad_id, ...])

        """
        # Получает текущие конверсии
        current_rates = listens_rate(ads_stat)

        cpm_dict = {}
        stop_ads = []
        for ad_id, current_rate in current_rates:
            current_cpm = ads_stat[ad_id]['cpm']

            # Если текущая конверсия ниже целевой, то:
            if current_rate < self.target_rate:
                # Если она еще и ниже порога остановки, добавлет объявление в стоп-лист
                if current_rate < self.stop_rate:
                    stop_ads.append(ad_id)
                # Если объявление не добавлено в стоп-лист, а cpm выше 30, но меньше одного шага:
                elif (30. + self.cpm_step) > current_cpm > 30.:
                    cpm_dict[ad_id] = 30.
                # Если опускать некуда, то пропускает это объявление
                elif current_cpm == 30.:
                    continue
                # В остальных случаях опускает cpm на один шаг
                else:
                    cpm_dict[ad_id] = current_cpm - self.cpm_step

            # Если текущая конверсия больше целевой - повышаем ставку
            else:
                cpm_dict[ad_id] = current_cpm + self.cpm_step

        return cpm_dict, stop_ads

    def updates_for_cost_target(self, ads_stat):
        """
        Возвращает новые CPM для объявлений + список объявлений, которые нужно остановить,
        выполняя цель по стоимости одного прослушивания

        :param ads_stat:    dict - {ad_id: {'name': str, 'spent': float, 'reach': int, 'cpm': cpm}}

        :return:            ({ad_id: new_cpm}, [ad_id, ...])

        """
        # Получает текущие стоимости прослушиваний
        current_costs = listens_cost(ads_stat)

        cpm_dict = {}
        stop_ads = []
        for ad_id, current_cost in current_costs.items():
            current_cpm = ads_stat[ad_id]['cpm']

            # Если текущий кост больше целевого, то:
            if current_cost > self.target_cost:
                # Если Текущий кост еще и больше порога остановки, добавляет объявления в стоп-лист
                if current_cost > self.stop_cost:
                    stop_ads.append(ad_id)
                # Если объявление не добавлено в стоп-лист, а cpm выше 30, но меньше одного шага:
                elif (30. + self.cpm_step) > current_cpm > 30.:
                    cpm_dict[ad_id] = 30.
                # Если опускать некуда, то пропускает это объявление
                elif current_cpm == 30.:
                    continue
                # В остальных случаях опускает cpm на один шаг
                else:
                    cpm_dict[ad_id] = current_cpm - self.cpm_step

            # Если текущий кост меньше целевого - повышаем ставку
            else:
                cpm_dict[ad_id] = current_cpm + self.cpm_step

        return cpm_dict, stop_ads




