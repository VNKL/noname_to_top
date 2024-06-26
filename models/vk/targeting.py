""" Use python 3.7 """

from models.vk.backend import VkAdsBackend
from models.database import *
from models.vk.tools import get_token_and_user_id
from models.vk.tools import CPMCalculator
import time
import datetime


class TargetingAssistant:
    """
    Класс для простой работы с VkAdsBackend.
    Упрощает черновую работу c VK API и созданием плейлистов.


    Параметры:

        user_id - int, айди аккаунта, с которого будут совершаться все действия,
                  у этого аккаунты должны быть админские права на группу артиста
                  и рекламный кабинет, которые передаются в объект

        login - str or int, логин аккаунта, речь о котором шла выше

        password - str, пароль аккаунта

        token - str, токен аккаунта, нужны доступы: ads, groups, offline

        artist_name - str, имя артиста, будет использовано для создания фейк-паблика,
                      поиска трека и названия рекламной кампании

        track_name - str, название трека, будет использовано для поиска трека,
                     названия плейлистов и рекламной кампании

        artist_group_id - int, айди официального паблика артиста, будет использован
                          для создания дарк-постов

        cabinet_id - int, айди рекалмного кабинета (личного или агентского), в котором
                     будет создана рекламная кампания

        client_id - int, айди клиента агентства, в кабинете которого будет создана
                    рекламная кампания (передается, только если в cabinet_id передан
                    айди кабинета агентства), по умолчанию None

        fake_group_id - int, айди фейкового паблика, в котором будут созданы плейлисты,
                        паблик должен носить имя артиста (если не передавать - будет
                        создан новый паблик с именем артиста)

        cover_path - str, путь к изображению, которое будет использовано как обложка плейлистов
                     (если не передавать, подтянется официальная обложка трека)

        citation - str, цитата из трека, будет использована в тексте дарк-постов
                   (если не передавать, будет сгенерирован стандартный текст без цитаты)

        campaign_budget - int, лимит по бюджету создаваемой рекламной кампании в рублях
                          (если не передавать, кампания не будет иметь такого ограничения)

        music_interest_filter - если True, в объявлениях будет ограничение по интересу "музыка",
                                если False, то этого ограничения в объявлениях не будет
                                (по умолчанию - False)

    """
    def __init__(self, user_id, login, password, token, artist_name, track_name, artist_group_id=None, cabinet_id=None,
                 client_id=None, fake_group_id=None, cover_path=None, citation=None, campaign_budget=0,
                 music_interest_filter=False):

        self.user_id = user_id
        self.artist_name = artist_name
        self.track_name = track_name
        self.artist_group_id = artist_group_id
        self.cabinet_id = cabinet_id
        self.client_id = client_id
        self.music_interest_filter = music_interest_filter
        self.login = login
        self.password = password
        self.token = token
        self.Backend = VkAdsBackend(self.login, self.password, self.token)
        self.retarget = self.Backend.get_retarget(self.cabinet_id, self.client_id)
        self.fake_group_id = self.__check_group_id(fake_group_id)
        self.cover_path = cover_path
        self.playlist_urls = []
        self.post_text = self._create_post_text(citation)
        self.dark_posts = {}
        self.campaign_budget = campaign_budget
        self.campaign_id = None
        self.ads = {}
        self.ad_names = {}

    def __check_group_id(self, group_id):
        if group_id is None:
            return self.Backend.create_group(group_name=self.artist_name, user_id=self.user_id)
        else:
            return group_id

    def _create_post_text(self, citation):

        if isinstance(self.artist_group_id, int):
            group = f'public{self.artist_group_id}'
        elif isinstance(self.artist_group_id, str):
            group = self.artist_group_id
        else:
            raise TypeError('artist_group_id must be int (group id) or str (group short address)')

        if citation is None:
            text = f'ПРЕМЬЕРА\n' \
                   f' \n' \
                   f'@{group} ({self.artist_name.upper()} - {self.track_name})\n' \
                   f' \n' \
                   f'Слушай в ВК👇🏻'
            return text
        else:
            text = f'ПРЕМЬЕРА\n' \
                   f' \n' \
                   f'@{group} ({self.artist_name.upper()} - {self.track_name})\n' \
                   f' \n' \
                   f'{citation}\n' \
                   f' \n' \
                   f'Слушай в ВК👇🏻'
            return text

    def create_playlists(self):
        """
        Добавлет трек в аудиозаписи паблика, потом создает плейлисты в количестве,
        равном доступным в кабинете базам ретаргета.
        Список ссылок на созданные плейлисты добавлет в аргумент playlist_urls.

        """
        # Добавление трека в аудиозаписи группы
        self.Backend.add_audio_in_group(group_id=self.fake_group_id,
                                        track_name=f'{self.artist_name} - {self.track_name}')
        # Создание плейлистов
        self.playlist_urls = self.Backend.create_playlists(group_id=self.fake_group_id, playlist_name=self.track_name,
                                                           cover_path=self.cover_path, count=len(self.retarget))

    def start_test(self):
        """
        Запускает тест по всем доступным в кабинете базам ретаргета:

            1 - создает плейлисты, если они не были созданы ранее (если их нет в объекте)
            2 - создает дарк-посты для каждого плейлиста и добавляет их в аргумент dark_posts в виде
                {post_url: playlist_url}
            3 - создает новую кампанию в кабинете и добавляет ее айди в аргумент campaign_id в виде int
            4 - создает объявления с дарк постами и добавляет их в аргумент ads в виде
                {ad_id: playlist_url} и его же возвращает

            Созданные объявления запускаются автоматически и после прохождения модерации крутятся
            до лимита 100 рублей каждое.

        """
        # Проверка на наличие плейлистов
        if not self.playlist_urls:
            self.create_playlists()

        # Создание дарк-постов
        self.dark_posts = self.Backend.create_dark_posts(group_id=self.artist_group_id,
                                                         playlists=self.playlist_urls,
                                                         text=self.post_text)
        # Создание новой кампании в кабинете
        self.campaign_id = self.Backend.create_campaign(cabinet_id=self.cabinet_id, client_id=self.client_id,
                                                        campaign_name=f'{self.artist_name.upper()} / {self.track_name}',
                                                        money_limit=self.campaign_budget)
        # Создание объявлений
        ads = self.Backend.create_ads(cabinet_id=self.cabinet_id, client_id=self.client_id,
                                      campaign_id=self.campaign_id,
                                      retarget=self.retarget,
                                      posts=list(self.dark_posts.keys()),
                                      music=self.music_interest_filter)
        self.ads = {ad_id: self.dark_posts[post_url] for ad_id, post_url in ads.items()}
        self.ad_names = self.Backend.ad_names

        print('Объявления созданы и отправлены на модерацию')

    def get_ads_stat(self):
        """
        Возвращает полную необходимую стату в виде
        dict - {ad_id: {'name': str, 'spent': float, 'reach': int, 'cpm': cpm}}

        """
        # Проверка на наличие объявлений в объекте
        if not self.ads:
            raise RuntimeError('self.ads пуст, сперва создай объявления, запустив start_test')

        # Получение статы объявлений и прослушиваний с плейлистов
        ads_stat = self.Backend.get_ads_stat(cabinet_id=self.cabinet_id, ad_ids=list(self.ads.keys()),
                                             ad_names=self.ad_names, campaign_id=self.campaign_id,
                                             client_id=self.client_id)
        listens = self.Backend.get_listens(group_id=self.fake_group_id, playlist_name=self.track_name)

        # Объединение статы объявлений и прослушиваний плейлистов
        full_stat = {}
        for ad_id, ad_stat in ads_stat.items():
            stat = ad_stat.copy()
            playlist_url = self.ads[ad_id]
            stat['listens'] = listens[playlist_url]
            full_stat[ad_id] = stat

        return full_stat

    def get_campaign_stat(self):
        """
        Возвращает стату по кампании

        :return:                dict - {campaign_id: {'spent': spent, 'reach': reach}}

        """
        return self.Backend.get_campaign_stat(cabinet_id=self.cabinet_id, campaign_id=self.campaign_id)

    def stop_ads(self, ad_ids):
        """
        Останавливает объявления.

        :param ad_ids:      list of int - список айди объявлений

        """
        self.Backend.stop_ads(cabinet_id=self.cabinet_id, ad_ids=ad_ids)
        print(f'Остановлено {len(ad_ids)} объявлений')

    def start_ads(self, ad_ids):
        """
        Запуск объявлений

        :param ad_ids:      list of int - список айди объявлений

        """
        self.Backend.start_ads(cabinet_id=self.cabinet_id, ad_ids=ad_ids)
        print(f'Запущено {len(ad_ids)} объявлений')

    def delete_ads(self, ad_ids):
        """
        Удаляет обявления по их айди из кабинета и аргумента ads.

        :param ad_ids:      list of int - список айди объявлений

        """
        self.Backend.delete_ads(cabinet_id=self.cabinet_id, ad_ids=ad_ids)
        alive_ads = {}
        for ad_id, playlist_url in self.ads.items():
            if ad_id not in ad_ids:
                alive_ads[ad_id] = playlist_url
        self.ads = alive_ads
        print(f'Удалено {len(ad_ids)} объявлений')

    def unlimit_ads(self, ad_ids):
        """
        Убирает лимиты с объявлений после теста.
        Лучше снимать лимиты только с объявлений, прошедших тест.

        :param ad_ids:      list of int - список айди объявлений

        """
        self.Backend.limit_ads(cabinet_id=self.cabinet_id, ad_ids=ad_ids, limit=0)
        print(f'Сняты лимиты по бюджету с {len(ad_ids)} объявлений')

    def update_cpm(self, cpm_dict):
        """
        Обновляет СРМ у объявлений

        :param cpm_dict:        dict - {ad_id: cpm}, cpm - float в рублях с копейками после точки

        """
        self.Backend.update_cpm(cabinet_id=self.cabinet_id, cpm_dict=cpm_dict)
        print(f'Обновлен СРМ у {len(cpm_dict)} объявлений')


class TargetingManager:
    """
    Высокоуровневый фреймворк для работы с VK API и созданием плейлистов.
    Работает с базой данных, архивируя в нее все необходимое для продолжения кампаний
    после различных факапов


    Параметры при инициализации класса:

        login - str или int, логин от ВК аккаунта, у аккаунта должен быть доступ к админке
                паблика артиста, из которого будет запускаться кампания

        password - str, пароль от ВК аккаунта


    Параметры основных методов:

        artist_name - str, имя артиста, будет использовано для создания фейк-паблика,
                      поиска трека и названия рекламной кампании

        track_name - str, название трека, будет использовано для поиска трека,
                     названия плейлистов и рекламной кампании

        artist_group_id - int, айди официального паблика артиста, будет использован
                          для создания дарк-постов

        cover_path - str, путь к изображению, которое будет использовано как обложка плейлистов
                     (если не передавать, подтянется официальная обложка трека)

        citation - str, цитата из трека, будет использована в тексте дарк-постов
                   (если не передавать, будет сгенерирован стандартный текст без цитаты)

        campaign_budget - int, лимит по бюджету создаваемой рекламной кампании в рублях
                          (если не передавать, кампания не будет иметь такого ограничения)

        music_interest_filter - если True, в объявлениях будет ограничение по интересу "музыка",
                                если False, то этого ограничения в объявлениях не будет
                                (по умолчанию - False)

        user_cabinet_name - str, название пользовательского кабинета, в котором будет запускаться кампания

        agency_cabinet_name - str, название агентского кабинета, в клиенте которого будет запускаться кампания
                              (при этом необходимо указать в соседнем параметре название клиентского кабинета)

        client_cabinet_name - str, название клиентского кабинета, в котором будет запускаться кампания
                              (необходимо также указать в соседнем параметре название агентского кабинета)

        cabinet_type - str, 'user' или 'client'

        ad_ids - list of int, список айди объявлений, над которыми будет произведено действие

        cpm_dict - {ad_id: cpm}, cpm - float в рублях с копейками после точки


    """
    def __init__(self, login, password):
        self.user = self._check_account(login, password)
        self.Backend = VkAdsBackend(self.user.login, self.user.password, self.user.token)
        self.Calculator = None
        self.Assistant = None
        self.user_cabinets = self._check_user_cabinets()
        self.agency_cabinets = self._check_agency_cabinets()
        self.client_cabinets = self._check_client_cabinets()
        self.user_campaigns = self._check_user_campaigns()
        self.client_campaigns = self._check_client_campaigns()
        self.user_campaign_details = self._check_user_campaign_details() if self.user_campaigns else None
        self.client_campaigns_details = self._check_client_campaign_details() if self.client_campaigns else None

    def _check_account(self, login, password):
        """
        Проверка на наличие аккаунта в базе данных

        """
        # Запрос в базу данных по логину
        user = Users.get_or_none(Users.login == login)

        # Если такого логина нет в базе данных, создается новый аккаунт и вносится в БД
        if not user:
            token, user_id = get_token_and_user_id(login, password)
            user = Users.create(login=login, password=password, token=token, user_id=user_id)
            return user
        # Если логин есть, но не совпадают пароли, добывается новый токен и обновляется в БД вместе с паролем
        elif user.password != password:
            token, user_id = get_token_and_user_id(login, password)
            user.password = password
            user.save()
            user.token = token
            user.save()
            return user
        # Если логин есть и пароли совпадают, возвращается аккаунт из БД
        else:
            return user

    def _check_user_cabinets(self):
        """
        Проверка на наличие пользовательских кабинетов в базе данных

        :return:    list - список объектов UserCabinets

        """
        # Запрос в БД и к API Vk
        user_cabinets_db = [x for x in UserCabinets.select().where(UserCabinets.owner == self.user)]
        cabinets_vk = self.Backend.get_cabinets()
        user_cabinets_vk = {}
        for cab_id, cab_info in cabinets_vk.items():
            if cab_info[1] == 'general':
                user_cabinets_vk[cab_id] = cab_info

        # Если кабинетов из ВК больше, в БД добавляются недостающие
        if len(user_cabinets_vk) > len(user_cabinets_db):
            cabinets = []
            for cab_id, cab_info in user_cabinets_vk.items():
                if cab_id not in [x.cabinet_id for x in user_cabinets_db] or len(user_cabinets_db) == 0:
                    cab = UserCabinets.create(owner=self.user, cabinet_id=cab_id, cabinet_name=cab_info[0])
                    cabinets.append(cab)
            return cabinets
        # А если не больше, то возвращается список кабинетов из БД
        else:
            return user_cabinets_db

    def _check_agency_cabinets(self):
        """
        Проверка на наличие пользовательских кабинетов в базе данных

        :return:    list - список обьектов AgencyCabinets

        """
        # Запрос в БД и к API Vk
        agency_cabinets_db = [x for x in AgencyCabinets.select().where(AgencyCabinets.owner == self.user)]
        cabinets_vk = self.Backend.get_cabinets()
        agency_cabinets_vk = {}
        for cab_id, cab_info in cabinets_vk.items():
            if cab_info[1] == 'agency':
                agency_cabinets_vk[cab_id] = cab_info

        # Если кабинетов из ВК больше, в БД добавляются недостающие
        if len(agency_cabinets_vk) > len(agency_cabinets_db):
            cabinets = []
            for cab_id, cab_info in agency_cabinets_vk.items():
                if cab_id not in [x.cabinet_id for x in agency_cabinets_db] or len(agency_cabinets_db) == 0:
                    cab = AgencyCabinets.create(owner=self.user, cabinet_id=cab_id, cabinet_name=cab_info[0])
                    cabinets.append(cab)
            return cabinets
        # А если не больше, то возвращается список кабинетов из БД
        else:
            return agency_cabinets_db

    def _check_client_cabinets(self):
        """
        Проверка на наличие клиентских кабинетов в базе данных

        :return:    dict - {agency_cabinet_object: [client_cabinet_object_1, client_cabinet_object_2...]}

        """
        # Проход циклом по всем агентским кабинетам объекта
        agency_clients = {}
        for agency in self.agency_cabinets:
            client_cabinets_db = [x for x in ClientCabinets.select().where(ClientCabinets.owner == agency)]
            client_cabinets_vk = self.Backend.get_clients(agency.cabinet_id)
            # Если кабинетов из ВК больше, то в БД добавляются недостающие
            if len(client_cabinets_vk) > len(client_cabinets_db):
                clients_list = []
                for cl_name, cl_id in client_cabinets_vk.items():
                    if cl_id not in [x.cabinet_id for x in client_cabinets_db] or len(client_cabinets_db) == 0:
                        cl_cab = ClientCabinets.create(owner=agency, cabinet_id=cl_id, cabinet_name=cl_name)
                        clients_list.append(cl_cab)
                agency_clients[agency] = clients_list
            # А если нет, то берутся кабинеты из БД
            else:
                agency_clients[agency.cabinet_id] = client_cabinets_db

        return agency_clients

    def _check_user_campaigns(self):
        """
        Проверка на наличие кампаний  в пользовательских кабинетах базы данных.
        Из ВК кампании не подгружаются, потому что для использования в этом ПО
            подойдут только кампании, созданные с помощью этого ПО, а они есть
            в базе данных

        :return:    dict - {user_cabinet_object: [campaign_object_1, campaign_object_2...]}

        """
        user_campaigns = {}
        for cabinet in self.user_cabinets:
            cabinet_campaigns = [x for x in UserCampaigns.select().where(UserCampaigns.owner == cabinet)]
            user_campaigns[cabinet] = cabinet_campaigns
        return user_campaigns

    def _check_client_campaigns(self):
        """
        Проверка на наличие кампаний в клиентских кабинетах базы данных.
        Из ВК кампании не подгружаются, потому что для использования в этом ПО
            подойдут только кампании, созданные с помощью этого ПО, а они есть
            в базе данных

        :return:    dict - {client_cabinet_object: [campaign_object_1, campaign_object_2...]}

        """
        client_campaigns = {}
        for cabinet in self.client_cabinets:
            cabinet_campaigns = [x for x in ClientCampaigns.select().where(ClientCampaigns.owner == cabinet)]
            client_campaigns[cabinet] = cabinet_campaigns
        return client_campaigns

    def _check_user_campaign_details(self):
        """
        Проверка на наличие деталей кампаний в пользовательских кабинетах базы данных.
        Из ВК ничего не подгружаются, потому что для использования в этом ПО
            подойдут только кампании, созданные с помощью этого ПО, а они есть
            в базе данных

        :return:    dict - {user_campaign_object: [user_campaign_detail_object_1, ...]}

        """
        campaign_details = {}
        for campaign in self.user_campaigns:
            details = [x for x in UserCampaignDetails.select().where(UserCampaignDetails.owner == campaign)]
            campaign_details[campaign] = details
        return campaign_details

    def _check_client_campaign_details(self):
        """
        Проверка на наличие деталей кампаний в клиентских кабинетах базы данных.
        Из ВК ничего не подгружаются, потому что для использования в этом ПО
            подойдут только кампании, созданные с помощью этого ПО, а они есть
            в базе данных

        :return:    dict - {user_campaign_object: [user_campaign_detail_object_1, ...]}

        """
        campaign_details = {}
        for campaign in self.client_campaigns:
            details = [x for x in ClientCampaignDetails.select().where(ClientCampaignDetails.owner == campaign)]
            campaign_details[campaign] = details
        return campaign_details

    def _wait_moderation(self):
        moderation = True
        while moderation:
            stat = self.get_ads_stat()
            spents = [x['spent'] for x in stat.values()]
            if all(spents) >= 100:
                moderation = False
            else:
                time.sleep(1200)

    def _clean_after_test(self):
        # Удаление объявлений, не прошедших тест, снятие лимитов с объявлений, прошедших тест
        ads_stat = self.get_ads_stat()
        all_ads = ads_stat.keys()
        fail_ads = self.Calculator.failed_ads(ads_stat)
        good_ads = list(set(all_ads) - set(fail_ads))
        time.sleep(1)
        self.delete_ads(fail_ads)
        time.sleep(1)
        self.unlimit_ads(good_ads)
        # Обновление словаря объявлений в ассистенте
        ads = self.Assistant.ads
        new_ads = {}
        for ad in good_ads:
            new_ads[ad] = ads[ad]
        self.Assistant.ads = new_ads
        return good_ads

    def _updating_cpm(self, cpm_update_interval, end_time):
        time_now = datetime.datetime.now()
        while time_now < end_time:
            time.sleep(cpm_update_interval)
            ads_stat = self.get_ads_stat()
            cpm_dict, stop_ads = self.Calculator.updates_for_target_cost(ads_stat)
            self.update_cpm(cpm_dict)
            self.stop_ads(stop_ads)

    def _wait_campaign_start(self, start_time):
        time_now = datetime.datetime.now()
        while time_now < start_time:
            time.sleep(300)
            time_now = datetime.datetime.now()

    def _ads_from_db_for_continue_campaign(self, cabinet_type, campaign_name, tested):

        if tested is True:
            tstd = 1
        else:
            tstd = 0

        # Достаем объявления из базы данных, если кампания находится в пользовательском кабинете
        if cabinet_type == 'user':
            campaign = UserCampaigns.select().where(UserCampaigns.campaign_name == campaign_name)
            ads = {x.ad_id: x.playlist_url for x in
                   UserCampaignDetails.select().where(UserCampaignDetails.owner == campaign and
                                                      UserCampaignDetails.tested == tstd)}
            ad_names = {x.ad_id: x.ad_name for x in
                        UserCampaignDetails.select().where(UserCampaignDetails.owner == campaign and
                                                           UserCampaignDetails.tested == tstd)}
            return ads, ad_names

        # Достаем объявления из базы данных, если кампания находится в клиентском кабинете
        elif cabinet_type == 'client':
            campaign = ClientCampaigns.select().where(ClientCampaigns.campaign_name == campaign_name)
            ads = {x.ad_id: x.playlist_url for x in
                   ClientCampaignDetails.select().where(ClientCampaignDetails.owner == campaign and
                                                        ClientCampaignDetails.tested == tstd)}
            ad_names = {x.ad_id: x.ad_name for x in
                        ClientCampaignDetails.select().where(ClientCampaignDetails.owner == campaign and
                                                             ClientCampaignDetails == tstd)}
            return ads, ad_names
        else:
            raise ValueError("cabinet_type может быть только 'user' или 'client'")

    def _cabinet_id_for_continue_campaign(self, cabinet_type, campaign_name):

        # Достаем кабинет и кампанию из БД, если речь о личном кабинете
        if cabinet_type == 'user':
            campaign = [x for x in UserCampaigns.select().where(UserCampaigns.campaign_name == campaign_name)][0]
            cabinet = UserCabinets.get_by_id(campaign.owner)
            return cabinet, campaign, None

        # Если речь о клиентском кабинете
        elif cabinet_type == 'client':
            campaign = [x for x in ClientCampaigns.select().where(ClientCampaigns.campaign_name == campaign_name)][0]
            client_cabinet = ClientCabinets.get_by_id(campaign.owner)
            cabinet = AgencyCabinets.get_by_id(client_cabinet.owner)
            return cabinet, campaign, client_cabinet

    def _new_user_campaign(self, artist_group_id, fake_group_id, artist_name, cabinet, campaign_budget, citation,
                           cover_path, music_interest_filter, track_name):
        # Инициализирует ассистента для работы с личным кабинетом
        self.Assistant = TargetingAssistant(user_id=self.user.user_id,
                                            login=self.user.login,
                                            password=self.user.password,
                                            token=self.user.token,
                                            artist_name=artist_name,
                                            track_name=track_name,
                                            artist_group_id=artist_group_id,
                                            fake_group_id=fake_group_id,
                                            cabinet_id=cabinet.cabinet_id,
                                            cover_path=cover_path,
                                            citation=citation,
                                            campaign_budget=campaign_budget,
                                            music_interest_filter=music_interest_filter)
        # Запускает тест, получает айди объявлений и новой кампании
        self.Assistant.start_test()
        ads = self.Assistant.ads
        ad_names = self.Assistant.ad_names
        campaign_id = self.Assistant.campaign_id
        campaign_name = f'{artist_name.upper()} / {track_name}'

        # Создает новую кампанию в базе данных
        new_campaign = UserCampaigns.create(owner=cabinet, campaign_id=campaign_id, campaign_name=campaign_name,
                                            artist_group=artist_group_id, fake_group=self.Assistant.fake_group_id)
        self.user_campaigns[cabinet].append(new_campaign)

        # Создает детализацию новой кампании в базе данных
        ads_insert = [{'owner': new_campaign, 'ad_id': ad_id, 'ad_name': ad_names[ad_id], 'playlist_url': playlist_url,
                       'tested': 0}
                      for ad_id, playlist_url in ads.items()]
        UserCampaignDetails.insert_many(ads_insert).on_conflict_replace().execute()

        # Ожидание прохождения тестов и запись объявлений в базу данных
        self._wait_moderation()
        good_ads = self._clean_after_test()
        ads_tested = {ad_id: playlist_url for ad_id, playlist_url in ads.items() if ad_id in good_ads}
        ads_insert = [{'owner': new_campaign, 'ad_id': ad_id, 'ad_name': ad_names[ad_id], 'playlist_url': playlist_url,
                       'tested': 1} for ad_id, playlist_url in ads_tested.items()]
        UserCampaignDetails.insert_many(ads_insert).on_conflict_replace().execute()

        print(f'Успешно прошли тест {len(good_ads)} объявлений:')
        ads_stat = self.get_ads_stat()
        for k, v in ads_stat.items():
            print(k, v)

        self.automate_campaign(tested=True)

    def _new_client_campaign(self, agency_cabinet, artist_group_id, fake_group_id, artist_name, campaign_budget,
                             citation, client_cabinet, cover_path, music_interest_filter, track_name):
        # Инициализирует ассистента для работы с клиентским кабинетом
        self.Assistant = TargetingAssistant(user_id=self.user.user_id,
                                            login=self.user.login,
                                            password=self.user.password,
                                            token=self.user.token,
                                            artist_name=artist_name,
                                            track_name=track_name,
                                            artist_group_id=artist_group_id,
                                            fake_group_id=fake_group_id,
                                            cabinet_id=agency_cabinet.cabinet_id,
                                            client_id=client_cabinet.cabinet_id,
                                            cover_path=cover_path,
                                            citation=citation,
                                            campaign_budget=campaign_budget,
                                            music_interest_filter=music_interest_filter)
        # Запускает тест, получает айди объявлений и новой кампании
        self.Assistant.start_test()
        ads = self.Assistant.ads
        ad_names = self.Assistant.ad_names
        campaign_id = self.Assistant.campaign_id
        campaign_name = f'{artist_name.upper()} / {track_name}'

        # Создает новую кампанию в базе данных
        new_campaign = ClientCampaigns.create(owner=client_cabinet, campaign_id=campaign_id,
                                              campaign_name=campaign_name, artist_group=artist_group_id,
                                              fake_group=self.Assistant.fake_group_id)
        self.client_campaigns[client_cabinet].append(new_campaign)

        # Создает детализацию новой кампании в базе данных
        ads_insert = [{'owner': new_campaign, 'ad_id': ad_id, 'ad_name': ad_names[ad_id], 'playlist_url': playlist_url,
                       'tested': 0} for ad_id, playlist_url in ads.items()]
        ClientCampaignDetails.insert_many(ads_insert).on_conflict_replace().execute()

        # Ожидание прохождения тестов и запись объявлений в базу данных
        self._wait_moderation()
        good_ads = self._clean_after_test()
        ads_tested = {ad_id: playlist_url for ad_id, playlist_url in ads.items() if ad_id in good_ads}
        ads_insert = [{'owner': new_campaign, 'ad_id': ad_id, 'ad_name': ad_names[ad_id], 'playlist_url': playlist_url,
                       'tested': 1} for ad_id, playlist_url in ads_tested.items()]
        ClientCampaignDetails.insert_many(ads_insert).on_conflict_replace().execute()

        print(f'Успешно прошли тест {len(good_ads)} объявлений:')
        ads_stat = self.get_ads_stat()
        for k, v in ads_stat.items():
            print(k, v)

        self.automate_campaign(tested=True)

    def start_new_campaign(self, artist_name, track_name, artist_group_id, cover_path=None, citation=None,
                           user_cabinet_name=None, agency_cabinet_name=None, client_cabinet_name=None,
                           music_interest_filter=False, campaign_budget=0, fake_group_id=None):

        # Достает личный кабинет, если передано название личного кабинета
        if user_cabinet_name:
            for x in self.user_cabinets:
                if x.cabinet_name == user_cabinet_name:
                    cabinet = x
                    # Запускает новую кампанию в личном кабинете
                    self._new_user_campaign(artist_group_id=artist_group_id,
                                            fake_group_id=fake_group_id,
                                            artist_name=artist_name,
                                            track_name=track_name,
                                            cabinet=cabinet,
                                            campaign_budget=campaign_budget,
                                            citation=citation,
                                            cover_path=cover_path,
                                            music_interest_filter=music_interest_filter)
                else:
                    raise ValueError(f'У этого пользователя нет кабинета с названием {user_cabinet_name}')


        # Достает агентский и клиентский кабинеты
        elif agency_cabinet_name and client_cabinet_name:
            for x in self.agency_cabinets:
                if x.cabinet_name == agency_cabinet_name:
                    agency_cabinet = x
                    for y in self.client_cabinets[agency_cabinet.cabinet_id]:
                        if y.cabinet_name == client_cabinet_name:
                            client_cabinet = y
                            # Запускает новую кампанию в агентском кабинете
                            self._new_client_campaign(agency_cabinet=agency_cabinet,
                                                      artist_group_id=artist_group_id,
                                                      fake_group_id=fake_group_id,
                                                      artist_name=artist_name,
                                                      track_name=track_name,
                                                      campaign_budget=campaign_budget,
                                                      citation=citation,
                                                      client_cabinet=client_cabinet,
                                                      cover_path=cover_path,
                                                      music_interest_filter=music_interest_filter)
                        else:
                            raise ValueError(f'У агентсва {agency_cabinet_name} нет клиента {client_cabinet_name}')
                else:
                    raise ValueError(f'У этого пользователя нет агентского кабинета {agency_cabinet_name}')


    def continue_campaign(self, artist_name, track_name, cabinet_type='user', tested=True):

        # Получение объявлений и кабинета из базы данных для продолжения кампании
        campaign_name = f'{artist_name.upper()} / {track_name}'
        ads, ad_names = self._ads_from_db_for_continue_campaign(cabinet_type, campaign_name, tested)
        cabinet, campaign, client_cabinet = self._cabinet_id_for_continue_campaign(cabinet_type, campaign_name)

        # Инициализация ассистента
        self.Assistant = TargetingAssistant(user_id=self.user.user_id,
                                            login=self.user.login,
                                            password=self.user.password,
                                            token=self.user.token,
                                            artist_name=artist_name,
                                            track_name=track_name,
                                            cabinet_id=cabinet.cabinet_id,
                                            client_id=client_cabinet.cabinet_id,
                                            artist_group_id=campaign.artist_group,
                                            fake_group_id=campaign.fake_group)
        self.Assistant.ads = ads
        self.Assistant.ad_names = ad_names
        self.Assistant.campaign_id = campaign.campaign_id

    def get_ads_stat(self):
        """
        Возвращает стату по объявлениям в виде
        dict - {ad_id: {'name': str, 'spent': float, 'reach': int, 'cpm': cpm}}

        """
        return self.Assistant.get_ads_stat()

    def get_campaign_stat(self):
        """
        Возвращает стату по кампании

        :return:                dict - {campaign_id: {'spent': spent, 'reach': reach}}

        """
        return self.Assistant.get_campaign_stat()

    def start_ads(self, ad_ids):
        """
        Запуск объявлений

        :param ad_ids:      list of int - список айди объявлений

        """
        self.Assistant.start_ads(ad_ids)

    def stop_ads(self, ad_ids):
        """
        Запуск объявлений

        :param ad_ids:      list of int - список айди объявлений

        """
        self.Assistant.stop_ads(ad_ids)

    def delete_ads(self, ad_ids):
        """
        Удаляет обявления по их айди из кабинета и аргумента ads.

        :param ad_ids:      list of int - список айди объявлений

        """
        self.Assistant.delete_ads(ad_ids)

    def unlimit_ads(self, ad_ids):
        """
        Убирает лимиты с объявлений после теста.
        Лучше снимать лимиты только с объявлений, прошедших тест.

        :param ad_ids:      list of int - список айди объявлений

        """
        self.Assistant.unlimit_ads(ad_ids)

    def update_cpm(self, cpm_dict):
        """
        Обновляет СРМ у объявлений

        :param cpm_dict:        dict - {ad_id: cpm}, cpm - float в рублях с копейками после точки

        """
        self.Assistant.update_cpm(cpm_dict)

    def automate_campaign(self, target_rate=0.04, stop_rate=0.03, target_cost=1., stop_cost=1.5, cpm_step=10.,
                          cpm_update_interval=1200, tested=True):
        """
        Метод для полной автоматизации кампании после запуска теста

        :param target_rate:             float - целевая конверсия из охвата в прослушивания
        :param stop_rate:               float - минимальная коверсия, ниже которой объявление останавливается
        :param target_cost:             float - целевая стоимость одного прослушивания в рублях
        :param stop_cost:               float - максимальная стоимость, выше которой объявление останавливается
        :param cpm_step:                float - шаг изменения CPM в рублях
        :param cpm_update_interval:     int - интервал обновления CPM в секундах
        :param tested:                  True - автоматизируем кампанию, которая прошла тест в таргете
                                        False - автоматизируем кампанию, которая еще не прошла тест в таргете

        :return:                        dict - итоговая стата по всем объявлениям через час после остановки кампании

        """
        # Инициализация калькулятора
        self.Calculator = CPMCalculator(target_rate=target_rate, stop_rate=stop_rate,
                                        target_cost=target_cost, stop_cost=stop_cost, cpm_step=cpm_step)
        if tested:
            # Ожидание прохождения тестов
            self._wait_moderation()
            good_ads = self._clean_after_test()
        else:
            good_ads = list(self.Assistant.ads.keys())

        # Установка параметров времени запуска и остановки основной части кампании
        today = datetime.datetime.combine(datetime.date.today(), datetime.datetime.min.time())
        if tested:
            end_time = today + datetime.timedelta(days=1)
        else:
            start_time = today + datetime.timedelta(days=1, hours=7)
            end_time = today + datetime.timedelta(days=2)
            # Ожидание наступления времени запуска основной части кампании и ее запуск
            self._wait_campaign_start(start_time)
            self.start_ads(good_ads)

        # Обновление ставок СРМ каждые 20 минут, пока не подойдет время завершения кампании
        self._updating_cpm(cpm_update_interval, end_time)

        # Остановка активных объявлений
        ads_stat = self.get_ads_stat()
        self.stop_ads(list(ads_stat.keys()))

        # Срез итоговой статы через час после остановки
        time.sleep(3600)
        return self.get_ads_stat()

