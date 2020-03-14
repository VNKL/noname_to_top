""" Use python 3.7 """

from models.vk.backend import VkAdsBackend
from models.database import *
from models.vk.tools import get_token_and_user_id


class MusicTargetingAssistant:
    """
    Фреймворк для простой работы с классом VkAds.
    Делает всю черновую работу, но не умеет принимать решений.


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
    def __init__(self, user_id, login, password, token, artist_name, track_name, artist_group_id, cabinet_id,
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
        self.Vk = VkAdsBackend(self.login, self.password, self.token)
        self.retarget = self.Vk.get_retarget(self.cabinet_id, self.client_id)
        self.fake_group_id = self.__check_group_id(fake_group_id)
        self.cover_path = cover_path
        self.playlist_urls = []
        self.post_text = self._create_post_text(citation)
        self.dark_posts = {}
        self.campaign_budget = campaign_budget
        self.campaign_id = None
        self.ads = {}

    def __check_group_id(self, group_id):
        if group_id is None:
            return self.Vk.create_group(group_name=self.artist_name, user_id=self.user_id)
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
        self.Vk.add_audio_in_group(group_id=self.fake_group_id,
                                   track_name=f'{self.artist_name} - {self.track_name}')
        # Создание плейлистов
        self.playlist_urls = self.Vk.create_playlists(group_id=self.fake_group_id, playlist_name=self.track_name,
                                                      cover_path=self.cover_path, count=len(self.retarget))

    def start_test(self):
        """
        Запускает тест по всем доступным в кабинете базам ретаргета:

            1 - создает плейлисты, если они не были созданы ранее (если их нет в объекте)
            2 - создает дарк-посты для каждого плейлиста и добавляет их в аргумент dark_posts в виде
                {post_url: playlist_url}
            3 - создает новую кампанию в кабинете и добавляет ее айди в аргумент campaign_id в виде int
            4 - создает объявления с дарк постами и добавляет их в аргумент ads в виде
                {ad_id: playlist_url}

            Созданные объявления запускаются автоматически и после прохождения модерации крутятся
            до лимита 100 рублей каждое.

        """
        # Проверка на наличие плейлистов
        if not self.playlist_urls:
            self.create_playlists()

        # Создание дарк-постов
        self.dark_posts = self.Vk.create_dark_posts(group_id=self.artist_group_id,
                                                    playlists=self.playlist_urls,
                                                    text=self.post_text)
        # Создание новой кампании в кабинете
        self.campaign_id = self.Vk.create_campaign(cabinet_id=self.cabinet_id, client_id=self.client_id,
                                                   campaign_name=f'{self.artist_name.upper()} / {self.track_name}',
                                                   money_limit=self.campaign_budget)
        # Создание объявлений
        ads = self.Vk.create_ads(cabinet_id=self.cabinet_id, client_id=self.client_id,
                                 campaign_id=self.campaign_id,
                                 retarget=self.retarget,
                                 posts=list(self.dark_posts.keys()),
                                 music=self.music_interest_filter)
        self.ads = {ad_id: self.dark_posts[post_url] for ad_id, post_url in ads.items()}

        print('Объявления созданы и отправлены на модерацию')

    def get_ads_stat(self):
        """
        Возвращает полную необходимую стату в виде
        {ad_id: {'name': str, 'spent': float, 'reach': int, 'listens': int}}

        """
        # Проверка на наличие объявлений в объекте
        if not self.ads:
            raise RuntimeError('self.ads пуст, сперва создай объявления, запустив start_test')

        # Получение статы объявлений и прослушиваний с плейлистов
        ads_stat = self.Vk.get_ads_stat(cabinet_id=self.cabinet_id, ad_ids=list(self.ads.keys()))
        listens = self.Vk.get_listens(group_id=self.fake_group_id, playlist_name=self.track_name)

        # Объединение статы объявлений и прослушиваний плейлистов
        full_stat = {}
        for ad_id, ad_stat in ads_stat.items():
            stat = ad_stat.copy()
            playlist_url = self.ads[ad_id]
            stat['listens'] = listens[playlist_url]
            full_stat[ad_id] = stat

        return full_stat

    def delete_ads(self, ad_ids):
        """
        Удаляет обявления по их айди из кабинета и аргумента ads.

        :param ad_ids:      list of int - список айди объявлений

        """
        self.Vk.delete_ads(cabinet_id=self.cabinet_id, ad_ids=ad_ids)
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
        self.Vk.limit_ads(cabinet_id=self.cabinet_id, ad_ids=ad_ids, limit=0)
        print(f'Сняты лимиты по бюджету с {len(ad_ids)} объявлений')

    def stop_ads(self, ad_ids):
        """
        Останавливает объявления.

        :param ad_ids:      list of int - список айди объявлений

        """
        self.Vk.stop_ads(cabinet_id=self.cabinet_id, ad_ids=ad_ids)
        print(f'Остановлено {len(ad_ids)} объявлений')

    def start_ads(self, ad_ids):
        """
        Запуск объявлений

        :param ad_ids:      list of int - список айди объявлений

        """
        self.Vk.start_ads(cabinet_id=self.cabinet_id, ad_ids=ad_ids)
        print(f'Запущено {len(ad_ids)} объявлений')

    def update_cpm(self, cpm_dict):
        """
        Обновляет СРМ у объявлений

        :param cpm_dict:        dict - {ad_id: cpm}, cpm - float в рублях с копейками после точки

        """
        self.Vk.update_cpm(cabinet_id=self.cabinet_id, cpm_dict=cpm_dict)
        print(f'Обновлен СРМ у {len(cpm_dict)} объявлений')


class MusicTargetingManager:

    def __init__(self, login, password):
        self.user = self._check_account(login, password)
        self.Backend = VkAdsBackend(self.user.login, self.user.password, self.user.token)
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
                        cl_cab = ClientCabinets.create(owner=agency, client_id=cl_id, client_name=cl_name)
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


# TODO  Наделать ретурнов методам ассистента, чтобы менеджер мог ими нормально пользоваться

