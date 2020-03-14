from peewee import *
from settings import DB


class User(Model):
    user_id = IntegerField(unique=True)
    login = CharField()
    password = CharField()
    token = CharField()

    class Meta:
        database = DB


class UserCabinet(Model):
    owner = ForeignKeyField(User, related_name='user_cabinets')
    campaign_name = CharField()
    campaign_id = IntegerField()

    class Meta:
        database = DB


class AgencyCabinet(Model):
    owner = ForeignKeyField(User, related_name='agency_cabinets')
    clients_name = CharField()
    clients_id = IntegerField()

    class Meta:
        database = DB


class ClientCabinet(Model):
    owner = ForeignKeyField(AgencyCabinet, related_name='client_cabinets')
    campaign_name = CharField()
    campaign_id = IntegerField()

    class Meta:
        database = DB


class UserCampaign(Model):
    owner = ForeignKeyField(UserCabinet, related_name='user_campaigns')
    ad_id = IntegerField()
    ad_name = CharField()
    post_url = CharField()
    playlist_url = CharField()
    fake_group_id = IntegerField()

    class Meta:
        database = DB


class ClientCampaign(Model):
    owner = ForeignKeyField(ClientCabinet, related_name='client_campaigns')
    ad_id = IntegerField()
    ad_name = CharField()
    post_url = CharField()
    playlist_url = CharField()
    fake_group_id = IntegerField()

    class Meta:
        database = DB


User.create_table()
UserCabinet.create_table()
AgencyCabinet.create_table()
ClientCabinet.create_table()
UserCampaign.create_table()
ClientCampaign.create_table()
