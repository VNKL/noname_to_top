""" Use python 3.7 """

import getpass
from html.parser import HTMLParser
import requests


class FormParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.url = None
        self.denial_url = None
        self.params = {}
        self.method = 'GET'
        self.in_form = False
        self.in_denial = False
        self.form_parsed = False

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == 'form':
            if self.in_form:
                raise RuntimeError('Nested form tags are not supported yet')
            else:
                self.in_form = True
        if not self.in_form:
            return

        attrs = dict((name.lower(), value) for name, value in attrs)

        if tag == 'form':
            self.url = attrs['action']
            if 'method' in attrs:
                self.method = attrs['method']
        elif tag == 'input' and 'type' in attrs and 'name' in attrs:
            if attrs['type'] in ['hidden', 'text', 'password']:
                self.params[attrs['name']] = attrs['value'] if 'value' in attrs else ''
        elif tag == 'input' and 'type' in attrs:
            if attrs['type'] == 'submit':
                self.params['submit_allow_access'] = True
        elif tag == 'div' and 'class' in attrs:
            if attrs['class'] == 'near_btn':
                self.in_denial = True
        elif tag == 'a' and 'href' in attrs and self.in_denial:
            self.denial_url = attrs['href']

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == 'form':
            if not self.in_form:
                raise RuntimeError('Unexpected end of <form>')
            self.form_parsed = True
            self.in_form = False
        elif tag == 'div' and self.in_denial:
            self.in_denial = False


class VKAuth(object):

    def __init__(self, permissions, app_id, api_v, email=None, pswd=None, two_factor_auth=False, security_code=None,
                 auto_access=True):
        """
        @args:
            permissions: list of Strings with permissions to get from API
            app_id: (String) vk app id that one can get from vk.com
            api_v: (String) vk API version
        """

        self.session = requests.Session()
        self.form_parser = FormParser()
        self._user_id = None
        self._access_token = None
        self.response = None

        self.permissions = permissions
        self.api_v = api_v
        self.app_id = app_id
        self.two_factor_auth = two_factor_auth
        self.security_code = security_code
        self.email = email
        self.pswd = pswd
        self.auto_access = auto_access

        if security_code != None and two_factor_auth == False:
            raise RuntimeError('Security code provided for non-two-factor authorization')

    def auth(self):
        """
            1. Asks vk.com for app authentication for a user
            2. If user isn't logged in, asks for email and password
            3. Retreives access token and user id
        """
        api_auth_url = 'https://oauth.vk.com/authorize'
        app_id = self.app_id
        permissions = self.permissions
        redirect_uri = 'https://oauth.vk.com/blank.html'
        display = 'wap'
        api_version = self.api_v

        auth_url_template = '{0}?client_id={1}&scope={2}&redirect_uri={3}&display={4}&v={5}&response_type=token'
        auth_url = auth_url_template.format(api_auth_url, app_id, ','.join(permissions), redirect_uri, display,
                                            api_version)

        self.response = self.session.get(auth_url)

        # look for <form> element in response html and parse it
        if not self._parse_form():
            raise RuntimeError('No <form> element found. Please, check url address')
        else:
            # try to log in with email and password (stored or expected to be entered)
            while not self._log_in():
                pass;

            # handling two-factor authentication
            # expecting a security code to enter here
            if self.two_factor_auth:
                self._two_fact_auth()

            # allow vk to use this app and access self.permissions
            self._allow_access()

            # now get _access_token and _user_id
            self._get_params()

            # close current session
            self._close()

    def get_token(self):
        """
            @return value:
                None if _access_token == None
                (String) access_token that was retreived in self.auth() method
        """
        return self._access_token

    def get_user_id(self):
        """
            @return value:
                None if _user_id == None
                (String) _user_id that was retreived in self.auth() method
        """
        return self._user_id

    def _parse_form(self):

        self.form_parser = FormParser()
        parser = self.form_parser

        try:
            parser.feed(str(self.response.content))
        except:
            print('Unexpected error occured while looking for <form> element')
            return False

        return True

    def _submit_form(self, *params):

        parser = self.form_parser

        if parser.method == 'post':
            payload = parser.params
            payload.update(*params)
            try:
                self.response = self.session.post(parser.url, data=payload)
            except requests.exceptions.RequestException as err:
                print("Error: ", err)
            except requests.exceptions.HTTPError as err:
                print("Error: ", err)
            except requests.exceptions.ConnectionError as err:
                print("Error: ConnectionError\n", err)
            except requests.exceptions.Timeout as err:
                print("Error: Timeout\n", err)
            except:
                print("Unexpecred error occured")

        else:
            self.response = None

    def _log_in(self):

        if self.email == None:
            self.email = ''
            while self.email.strip() == '':
                self.email = input('Enter an email to log in: ')

        if self.pswd == None:
            self.pswd = ''
            while self.pswd.strip() == '':
                self.pswd = getpass.getpass('Enter the password: ')

        self._submit_form({'email': self.email, 'pass': self.pswd})

        if not self._parse_form():
            raise RuntimeError('No <form> element found. Please, check url address')

        # if wrong email or password
        if 'pass' in self.form_parser.params:
            raise ConnectionAbortedError('bad password')
            print('Wrong email or password')
            self.email = None
            self.pswd = None
            return
        elif 'code' in self.form_parser.params and not self.two_factor_auth:
            self.two_factor_auth = True
        else:
            return True

    def _two_fact_auth(self):

        prefix = 'https://m.vk.com'

        if prefix not in self.form_parser.url:
            self.form_parser.url = prefix + self.form_parser.url

        if self.security_code == None:
            self.security_code = input('Enter security code for two-factor authentication: ')

        self._submit_form({'code': self.security_code})

        if not self._parse_form():
            raise RuntimeError('No <form> element found. Please, check url address')

    def _allow_access(self):

        parser = self.form_parser

        if 'submit_allow_access' in parser.params and 'grant_access' in parser.url:
            if not self.auto_access:
                answer = ''
                msg = 'Application needs access to the following details in your profile:\n' + \
                      str(self.permissions) + '\n' + \
                      'Allow it to use them? (yes or no)'

                attempts = 5
                while answer not in ['yes', 'no'] and attempts > 0:
                    answer = input(msg).lower().strip()
                    attempts -= 1

                if answer == 'no' or attempts == 0:
                    self.form_parser.url = self.form_parser.denial_url
                    print('Access denied')

            self._submit_form({})

    def _get_params(self):

        try:
            params = self.response.url.split('#')[1].split('&')
            self._access_token = params[0].split('=')[1]
            self._user_id = params[2].split('=')[1]
        except IndexError as err:
            print('Coudln\'t fetch token and user id\n')
            print(err)

    def _close(self):
        self.session.close()
        self.response = None
        self.form_parser = None
        self.security_code = None
        self.email = None
        self.pswd = None


def get_token_and_user_id(login, password):
    vk = VKAuth(['ads,offline,groups'], '6121396', '5.103', email=login, pswd=password)
    vk.auth()
    token = vk.get_token()
    user_id = vk.get_user_id()
    return token, user_id


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


class CPMCalculator:

    def __init__(self, target_rate=0.04, stop_rate=0.03, target_cost=1., stop_cost=2., cpm_step=10.):
        self.target_rate = target_rate
        self.stop_rate = stop_rate
        self.target_cost = target_cost
        self.stop_cost = stop_cost
        self.cpm_step = cpm_step

    def updates_for_target_rate(self, ads_stat):
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

    def updates_for_target_cost(self, ads_stat):
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

    def updates_for_reach_speed(self, ads_stat, faster=True):
        """
        Возвращает новые CPM для объявлений, соответствуя цели ускорить/замедлить кампанию

        :param ads_stat:    dict - {ad_id: {'name': str, 'spent': float, 'reach': int, 'cpm': cpm}}
        :param faster       True - ускоряет кампанию, возвращая увеличенные CPM
                            False - замедляет кампанию, возвращая пониженные CPM

        :return:            {ad_id: new_cpm}

        """
        # Получает текущие стоимости прослушиваний
        current_costs = listens_cost(ads_stat)

        cpm_dict = {}

        if faster is True:
            for ad_id, current_cost in current_costs.items():
                current_cpm = ads_stat[ad_id]['cpm']
                cpm_delta = (self.target_cost / current_cost) * 10.
                cpm_dict[ad_id] = current_cpm + cpm_delta
                self.target_cost += cpm_delta / 40.
                self.stop_cost += cpm_delta / 40.

        elif faster is False:
            for ad_id, current_cost in current_costs.items():
                current_cpm = ads_stat[ad_id]['cpm']
                cpm_delta = (self.target_cost / current_cost) * 10.
                if current_cpm - cpm_delta > 30.:
                    cpm_dict[ad_id] = current_cpm - cpm_delta
                else:
                    cpm_dict[ad_id] = 30.
                self.target_cost -= cpm_delta / 50.
                self.stop_cost -= cpm_delta / 50.

        return cpm_dict



