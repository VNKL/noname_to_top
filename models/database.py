from peewee import *
from settings import DB


class Users(Model):
    login = CharField(unique=True)
    password = CharField()
    token = CharField()
    user_id = IntegerField(unique=True)

    class Meta:
        database = DB


class UserCabinets(Model):
    owner = ForeignKeyField(Users, related_name='user_cabinets')
    cabinet_id = IntegerField()
    cabinet_name = CharField()

    class Meta:
        database = DB


class AgencyCabinets(Model):
    owner = ForeignKeyField(Users, related_name='agency_cabinets')
    cabinet_id = IntegerField()
    cabinet_name = CharField()

    class Meta:
        database = DB


class ClientCabinets(Model):
    owner = ForeignKeyField(AgencyCabinets, related_name='agency_clients')
    cabinet_id = IntegerField()
    cabinet_name = CharField()

    class Meta:
        database = DB


class UserCampaigns(Model):
    owner = ForeignKeyField(UserCabinets, related_name='cabinet_campaigns')
    campaign_id = IntegerField(unique=True)
    campaign_name = CharField()
    artist_group = CharField()
    fake_group = CharField()

    class Meta:
        database = DB


class ClientCampaigns(Model):
    owner = ForeignKeyField(ClientCabinets, related_name='client_campaigns')
    campaign_id = IntegerField(unique=True)
    campaign_name = CharField()
    artist_group = CharField()
    fake_group = CharField()

    class Meta:
        database = DB


class UserCampaignDetails(Model):
    owner = ForeignKeyField(UserCampaigns, related_name='user_campaigns')
    ad_id = IntegerField(unique=True)
    ad_name = CharField()
    playlist_url = CharField()
    tested = IntegerField()

    class Meta:
        database = DB


class ClientCampaignDetails(Model):
    owner = ForeignKeyField(ClientCampaigns, related_name='client_campaign')
    ad_id = IntegerField(unique=True)
    ad_name = CharField()
    playlist_url = CharField()
    tested = IntegerField()

    class Meta:
        database = DB


Users.create_table()
UserCabinets.create_table()
UserCampaigns.create_table()
UserCampaignDetails.create_table()
AgencyCabinets.create_table()
ClientCabinets.create_table()
ClientCampaigns.create_table()
ClientCampaignDetails.create_table()
