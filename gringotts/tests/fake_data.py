"""Fake data for all tests"""
import datetime

DOMAIN_ID = '109248b511d745c3bafa0fa73fed7601'

DEMO_USER_ID = '2675d4da10b54c5b8f79c69dba7cfb93'
DEMO_PROJECT_ID = '26dfd7a12ec247b9a3426acc114418a8'

ADMIN_USER_ID = '2675d4da10b54c5b8f79c69dba7cfb95'
ADMIN_PROJECT_ID = '26dfd7a12ec247b9a3426acc114418a9'

CIRROS_IMAGE_ID = 'b75f1447-1f62-489f-becf-a1b26e547358'
CIRROS_IMAGE_NAME = 'cirros-0.3.1-x86_64-uec'

# instances
INSTANCE_ID_1 = 'b3725586-ae77-4001-9ecb-c0b4afb35901'
INSTANCE_ID_2 = 'b3725586-ae77-4001-9ecb-c0b4afb35902'
INSTANCE_ID_3 = 'b3725586-ae77-4001-9ecb-c0b4afb35903'
INSTANCE_ID_4 = 'b3725586-ae77-4001-9ecb-c0b4afb35904'
INSTANCE_ID_5 = 'b3725586-ae77-4001-9ecb-c0b4afb35905'

TIMESTAMP_TIME_FORMAT = '%Y-%m-%d %H:%M:%S.%f'
instance_created_time = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
instance_stopped_time = instance_created_time + datetime.timedelta(minutes=10)
instance_started_time = instance_stopped_time + datetime.timedelta(minutes=10)
instance_resized_time = instance_started_time + datetime.timedelta(minutes=10)
instance_deleted_time = instance_resized_time + datetime.timedelta(minutes=10)

INSTANCE_CREATED_TIME_STR = instance_created_time.strftime(TIMESTAMP_TIME_FORMAT)
INSTANCE_STOPPED_TIME_STR = instance_stopped_time.strftime(TIMESTAMP_TIME_FORMAT)
INSTANCE_STARTED_TIME_STR = instance_started_time.strftime(TIMESTAMP_TIME_FORMAT)
INSTANCE_RESIZED_TIME_STR = instance_resized_time.strftime(TIMESTAMP_TIME_FORMAT)
INSTANCE_DELETED_TIME_STR = instance_deleted_time.strftime(TIMESTAMP_TIME_FORMAT)

INSTANCE_1_CREATED_TIME = INSTANCE_CREATED_TIME_STR
INSTANCE_1_STOPPED_TIME = INSTANCE_STOPPED_TIME_STR
INSTANCE_1_STARTED_TIME = INSTANCE_STARTED_TIME_STR
INSTANCE_1_RESIZED_TIME = INSTANCE_RESIZED_TIME_STR
INSTANCE_1_DELETED_TIME = INSTANCE_DELETED_TIME_STR

INSTANCE_2_CREATED_TIME = INSTANCE_CREATED_TIME_STR
INSTANCE_2_STOPPED_TIME = INSTANCE_STOPPED_TIME_STR

INSTANCE_3_CREATED_TIME = INSTANCE_CREATED_TIME_STR
INSTANCE_3_STOPPED_TIME = INSTANCE_STOPPED_TIME_STR
INSTANCE_3_STARTED_TIME = INSTANCE_STARTED_TIME_STR

INSTANCE_4_CREATED_TIME = INSTANCE_CREATED_TIME_STR
INSTANCE_4_STOPPED_TIME = INSTANCE_STOPPED_TIME_STR
INSTANCE_4_STARTED_TIME = INSTANCE_STARTED_TIME_STR
INSTANCE_4_DELETED_TIME = INSTANCE_DELETED_TIME_STR

INSTANCE_5_CREATED_TIME = INSTANCE_CREATED_TIME_STR
INSTANCE_5_RESIZED_TIME = INSTANCE_RESIZED_TIME_STR

# volumes
volume_created_time = datetime.datetime.utcnow() - datetime.timedelta(days=3)
volume_stopped_time = volume_created_time + datetime.timedelta(minutes=10)
volume_started_time = volume_stopped_time + datetime.timedelta(minutes=10)
volume_resized_time = volume_started_time + datetime.timedelta(minutes=10)
volume_deleted_time = volume_resized_time + datetime.timedelta(minutes=10)

VOLUME_CREATED_TIME_STR = volume_created_time.strftime(TIMESTAMP_TIME_FORMAT)
VOLUME_STOPPED_TIME_STR = volume_stopped_time.strftime(TIMESTAMP_TIME_FORMAT)
VOLUME_STARTED_TIME_STR = volume_started_time.strftime(TIMESTAMP_TIME_FORMAT)
VOLUME_RESIZED_TIME_STR = volume_resized_time.strftime(TIMESTAMP_TIME_FORMAT)
VOLUME_DELETED_TIME_STR = volume_deleted_time.strftime(TIMESTAMP_TIME_FORMAT)

VOLUME_ID_1 = '7d0e2a0f-15dc-47f1-bb63-27513c6ab431'
VOLUME_ID_2 = '7d0e2a0f-15dc-47f1-bb63-27513c6ab432'

VOLUME_1_CREATED_TIME = VOLUME_CREATED_TIME_STR
VOLUME_1_RESIZED_TIME = VOLUME_RESIZED_TIME_STR

VOLUME_2_CREATED_TIME = VOLUME_CREATED_TIME_STR
VOLUME_2_RESIZED_TIME = VOLUME_RESIZED_TIME_STR

# routers
router_created_time = datetime.datetime.utcnow() - datetime.timedelta(days=5)
ROUTER_CREATED_TIME_STR = router_created_time.strftime(TIMESTAMP_TIME_FORMAT)

ROUTER_ID_1 = '3d659073-8a1f-4c16-a608-bc2c073af0f1'

ROUTER_1_CREATED_TIME = ROUTER_CREATED_TIME_STR


# -----------------I am style line :)-----------------

def make_instance_message(event_type=None, instance_id=None, display_name=None,
                          user_id=None, tenant_id=None, instance_type=None,
                          image_name=None, base_image_ref=None, disk_gb=None,
                          state=None, timestamp=None, old_instance_type=None):
    message = {
        'event_type': event_type,
        'payload': {
            'instance_id': instance_id,
            'display_name': display_name,
            'user_id': user_id,
            'tenant_id': tenant_id,
            'instance_type': instance_type,
            'old_instance_type': old_instance_type,
            'image_name': image_name,
            'image_meta': {
                'base_image_ref': base_image_ref
            },
            'disk_gb': disk_gb,
            'state': state
        },
        'timestamp': timestamp
    }

    return message


def make_instance_created_message(instance_id, timestamp, **kwargs):
    return make_instance_message(event_type='compute.instance.create.end',
                                 instance_id=instance_id,
                                 display_name=kwargs.get('display_name') or 'vm',
                                 user_id=DEMO_USER_ID,
                                 tenant_id=DEMO_PROJECT_ID,
                                 instance_type=kwargs.get('instance_type') or 'm1.tiny',
                                 image_name=CIRROS_IMAGE_NAME,
                                 base_image_ref=CIRROS_IMAGE_ID,
                                 disk_gb=kwargs.get('disk_gb') or 1,
                                 state='active',
                                 timestamp=timestamp)

def make_instance_stopped_message(instance_id, timestamp, **kwargs):
    return make_instance_message(event_type='compute.instance.power_off.end',
                                 instance_id=instance_id,
                                 display_name=kwargs.get('display_name') or 'vm',
                                 user_id=DEMO_USER_ID,
                                 tenant_id=DEMO_PROJECT_ID,
                                 instance_type=kwargs.get('instance_type') or 'm1.tiny',
                                 image_name=CIRROS_IMAGE_NAME,
                                 base_image_ref=CIRROS_IMAGE_ID,
                                 disk_gb=kwargs.get('disk_gb') or 1,
                                 state='stopped',
                                 timestamp=timestamp)

def make_instance_started_message(instance_id, timestamp, **kwargs):
    return make_instance_message(event_type='compute.instance.power_on.end',
                                 instance_id=instance_id,
                                 display_name=kwargs.get('display_name') or 'vm',
                                 user_id=DEMO_USER_ID,
                                 tenant_id=DEMO_PROJECT_ID,
                                 instance_type=kwargs.get('instance_type') or 'm1.tiny',
                                 image_name=CIRROS_IMAGE_NAME,
                                 base_image_ref=CIRROS_IMAGE_ID,
                                 disk_gb=kwargs.get('disk_gb') or 1,
                                 state='active',
                                 timestamp=timestamp)

def make_instance_resized_message(instance_id, timestamp, **kwargs):
    return make_instance_message(event_type='compute.instance.local_resize.end',
                                 instance_id=instance_id,
                                 display_name=kwargs.get('display_name') or 'vm',
                                 user_id=DEMO_USER_ID,
                                 tenant_id=DEMO_PROJECT_ID,
                                 instance_type=kwargs.get('instance_type') or 'm1.tiny',
                                 old_instance_type=kwargs.get('old_instance_type') or 'm1.tiny',
                                 image_name=CIRROS_IMAGE_NAME,
                                 base_image_ref=CIRROS_IMAGE_ID,
                                 disk_gb=kwargs.get('disk_gb') or 1,
                                 state='active',
                                 timestamp=timestamp)

def make_instance_deleted_message(instance_id, timestamp, **kwargs):
    return make_instance_message(event_type='compute.instance.delete.end',
                                 instance_id=instance_id,
                                 display_name=kwargs.get('display_name') or 'vm',
                                 user_id=DEMO_USER_ID,
                                 tenant_id=DEMO_PROJECT_ID,
                                 instance_type=kwargs.get('instance_type') or 'm1.tiny',
                                 image_name=CIRROS_IMAGE_NAME,
                                 base_image_ref=CIRROS_IMAGE_ID,
                                 disk_gb=kwargs.get('disk_gb') or 1,
                                 state='deleted',
                                 timestamp=timestamp)


NOTICE_INSTANCE_1_CREATED = make_instance_created_message(INSTANCE_ID_1,
                                                          INSTANCE_1_CREATED_TIME,
                                                          display_name='vm1')

NOTICE_INSTANCE_1_STOPPED = make_instance_stopped_message(INSTANCE_ID_1,
                                                          INSTANCE_1_STOPPED_TIME,
                                                          display_name='vm1')

NOTICE_INSTANCE_1_STARTED = make_instance_started_message(INSTANCE_ID_1,
                                                          INSTANCE_1_STARTED_TIME,
                                                          display_name='vm1')

NOTICE_INSTANCE_1_RESIZED = make_instance_resized_message(INSTANCE_ID_1,
                                                          INSTANCE_1_RESIZED_TIME,
                                                          display_name='vm1',
                                                          instance_type='m1.small',
                                                          old_instance_type='m1.tiny')

NOTICE_INSTANCE_1_DELETED = make_instance_deleted_message(INSTANCE_ID_1,
                                                          INSTANCE_1_DELETED_TIME,
                                                          display_name='vm1')

NOTICE_INSTANCE_2_CREATED = make_instance_created_message(INSTANCE_ID_2,
                                                          INSTANCE_2_CREATED_TIME,
                                                          display_name='vm2')

NOTICE_INSTANCE_2_STOPPED = make_instance_stopped_message(INSTANCE_ID_2,
                                                          INSTANCE_2_STOPPED_TIME,
                                                          display_name='vm2')

NOTICE_INSTANCE_3_CREATED = make_instance_created_message(INSTANCE_ID_3,
                                                          INSTANCE_3_CREATED_TIME,
                                                          display_name='vm3')

NOTICE_INSTANCE_3_STOPPED = make_instance_stopped_message(INSTANCE_ID_3,
                                                          INSTANCE_3_STOPPED_TIME,
                                                          display_name='vm3')

NOTICE_INSTANCE_3_STARTED = make_instance_started_message(INSTANCE_ID_3,
                                                          INSTANCE_3_STARTED_TIME,
                                                          display_name='vm3')

NOTICE_INSTANCE_4_CREATED = make_instance_created_message(INSTANCE_ID_4,
                                                          INSTANCE_4_CREATED_TIME,
                                                          display_name='vm4')

NOTICE_INSTANCE_4_STOPPED = make_instance_stopped_message(INSTANCE_ID_4,
                                                          INSTANCE_4_STOPPED_TIME,
                                                          display_name='vm4')

NOTICE_INSTANCE_4_STARTED = make_instance_started_message(INSTANCE_ID_4,
                                                          INSTANCE_4_STARTED_TIME,
                                                          display_name='vm4')

NOTICE_INSTANCE_4_DELETED = make_instance_deleted_message(INSTANCE_ID_4,
                                                          INSTANCE_4_DELETED_TIME,
                                                          display_name='vm4')

NOTICE_INSTANCE_5_CREATED = make_instance_created_message(INSTANCE_ID_5,
                                                          INSTANCE_5_CREATED_TIME,
                                                          display_name='vm5')

NOTICE_INSTANCE_5_RESIZED = make_instance_resized_message(INSTANCE_ID_5,
                                                          INSTANCE_5_RESIZED_TIME,
                                                          display_name='vm5',
                                                          instance_type='m1.small',
                                                          old_instance_type='m1.tiny')


# -------------------I am style line :)----------------------------------

def make_volume_message(event_type=None, volume_id=None, display_name=None,
                        user_id=None, tenant_id=None, status=None,
                        size=None, timestamp=None, volume_type=None):
    message = {
        'event_type': event_type,
        'payload': {
            'volume_id': volume_id,
            'display_name': display_name,
            'user_id': user_id,
            'tenant_id': tenant_id,
            'size': size,
            'volume_type': volume_type,
            'status': status,
        },
        'timestamp': timestamp
    }

    return message


def make_volume_created_message(volume_id, timestamp, **kwargs):
    return make_volume_message(event_type='volume.create.end',
                               volume_id=volume_id,
                               display_name=kwargs.get('display_name') or 'vol',
                               user_id=DEMO_USER_ID,
                               tenant_id=DEMO_PROJECT_ID,
                               status='available',
                               volume_type=kwargs.get('volume_type') or 'ssd',
                               size=kwargs.get('size') or 2,
                               timestamp=timestamp)

def make_volume_resized_message(volume_id, timestamp, **kwargs):
    return make_volume_message(event_type='volume.resize.end',
                               volume_id=volume_id,
                               display_name=kwargs.get('display_name') or 'vol',
                               user_id=DEMO_USER_ID,
                               tenant_id=DEMO_PROJECT_ID,
                               status='extending',
                               volume_type=kwargs.get('volume_type') or 'ssd',
                               size=kwargs.get('size') or 4,
                               timestamp=timestamp)

def make_volume_deleted_message(volume_id, timestamp, **kwargs):
    return make_volume_message(event_type='volume.delete.end',
                               volume_id=volume_id,
                               display_name=kwargs.get('display_name') or 'vol',
                               user_id=DEMO_USER_ID,
                               tenant_id=DEMO_PROJECT_ID,
                               status='deleted',
                               volume_type=kwargs.get('volume_type') or 'ssd',
                               size=kwargs.get('size') or 2,
                               timestamp=timestamp)


NOTICE_VOLUME_1_CREATED = make_volume_created_message(VOLUME_ID_1,
                                                      VOLUME_1_CREATED_TIME,
                                                      display_name='vol-1')

NOTICE_VOLUME_2_CREATED = make_volume_created_message(VOLUME_ID_2,
                                                      VOLUME_2_CREATED_TIME,
                                                      display_name='vol-2')

NOTICE_VOLUME_2_RESIZED = make_volume_created_message(VOLUME_ID_2,
                                                      VOLUME_2_RESIZED_TIME,
                                                      display_name='vol-2')


# --------------------Haha, I am style line again:)--------------------------

def make_router_message(event_type=None, router_id=None, router_name=None,
                        user_id=None, tenant_id=None, timestamp=None):
    message = {
        'event_type': event_type,
        'payload': {
            'router':{
                'id': router_id,
                'name': router_name,
                'user_id': user_id,
                'tenant_id': tenant_id,
            },
            'router_id': router_id,
        },
        'timestamp': timestamp
    }

    return message


def make_router_created_message(router_id, timestamp, **kwargs):
    return make_router_message(event_type='router.create.end',
                               router_id=router_id,
                               router_name=kwargs.get('router_name') or 'router',
                               user_id=DEMO_USER_ID,
                               tenant_id=DEMO_PROJECT_ID,
                               timestamp=timestamp)

def make_router_deleted_message(router_id, timestamp, **kwargs):
    return make_router_message(event_type='router.deleted.end',
                               router_id=router_id,
                               router_name=kwargs.get('router_name') or 'router',
                               user_id=DEMO_USER_ID,
                               tenant_id=DEMO_PROJECT_ID,
                               timestamp=timestamp)


NOTICE_ROUTER_1_CREATED = make_router_created_message(ROUTER_ID_1,
                                                      ROUTER_1_CREATED_TIME,
                                                      router_name='router-1')


# -------------------------H.e.l.l.o...---------------------------------

# products
PRODUCT_FLAVOR_TINY = {
    "product_id": "ccd5f8cd-4a5e-4016-a7ce-3ce3c59071eb",
    "region_id": "RegionOne",
    "service": "compute",
    "description": "some decs",
    "unit_price": "0.0600",
    "name": "instance:m1.tiny",
    "type": "regular",
    "unit": "hour",
    "quantity": 0,
    "deleted": False
}

PRODUCT_FLAVOR_SMALL = {
    "product_id": "ccd5f8cd-4a5e-4016-a7ce-3ce3c59071ea",
    "region_id": "RegionOne",
    "service": "compute",
    "description": "some decs",
    "unit_price": "0.1110",
    "name": "instance:m1.small",
    "type": "regular",
    "unit": "hour",
    "quantity": 0,
    "deleted": False
}

PRODUCT_VOLUME_SIZE = {
    "region_id": "RegionOne",
    "service": "block_storage",
    "description": "some decs",
    "unit_price": "0.0020",
    "name": "volume.size",
    "type": "regular",
    "unit": "hour",
    "product_id": "98f2ce8b-8ad3-42db-b82e-dd022381d1bc",
    "quantity": 0,
    "deleted": False
}

PRODUCT_ROUTER_SIZE = {
    "region_id": "RegionOne",
    "service": "network",
    "description": "some decs",
    "unit_price": "0.0500",
    "name": "router",
    "type": "regular",
    "unit": "hour",
    "product_id": "4038d1b8-e08f-4824-9f4e-f277d15c5bfe",
    "quantity": 0,
    "deleted": False
}

PRODUCT_SNAPSHOT_SIZE = {
    "region_id": "RegionOne",
    "service": "block_storage",
    "description": "some decs",
    "unit_price": "0.0002",
    "name": "snapshot.size",
    "type": "regular",
    "unit": "hour",
    "product_id": "e1cd002a-bef5-4306-b60e-8e6f54b80548",
    "quantity": 0,
    "deleted": False
}

PRODUCT_IMAGE_LICENSE = {
    "product_id": "43b6909b-0ff8-4dd6-8365-cffedb9e646c",
    "service": "compute",
    "unit_price": "0.03",
    "name": "%s:%s" % (CIRROS_IMAGE_NAME, CIRROS_IMAGE_ID),
    "region_id": "RegionOne",
    "type": "regular",
    "unit": "hour",
    "description": "some decs",
    "quantity": 0,
    "deleted": False
}

# account
FAKE_ACCOUNT_DEMO = {
    "user_id": DEMO_USER_ID,
    "project_id": DEMO_PROJECT_ID,
    "domain_id": DOMAIN_ID,
    "balance": 100,
    "consumption": 0,
    "level": 3
}

FAKE_ACCOUNT_ADMIN = {
    "user_id": ADMIN_USER_ID,
    "project_id": ADMIN_PROJECT_ID,
    "domain_id": DOMAIN_ID,
    "balance": 8975,
    "consumption": 9527,
    "level": 3
}

# project
FAKE_PROJECT_DEMO = {
    "user_id": ADMIN_USER_ID,
    "project_id": DEMO_PROJECT_ID,
    "domain_id": DOMAIN_ID,
    "consumption": 9000
}

FAKE_PROJECT_ADMIN = {
    "user_id": ADMIN_USER_ID,
    "project_id": ADMIN_PROJECT_ID,
    "domain_id": DOMAIN_ID,
    "consumption": 527
}

# user projects
USER_PROJECTS = [
    {
      "description": None,
      "name": "admin",
      "domain_id": DOMAIN_ID,
      "id": ADMIN_PROJECT_ID,
      "created_at": "2014-11-16 00:00:00",
      "users": {
        "billing_owner": {
            "id": ADMIN_USER_ID,
            "name": "admin",
        },
        "project_owner": {
            "id": ADMIN_USER_ID,
            "name": "admin",
        },
        "project_creator": {
            "id": ADMIN_USER_ID,
            "name": "admin",
        }
      }
    },
    {
      "description": None,
      "name": "demo",
      "domain_id": DOMAIN_ID,
      "id": DEMO_PROJECT_ID,
      "created_at": "2014-11-16 00:00:00",
      "users": {
        "billing_owner": {
          "name": "admin",
          "id": ADMIN_USER_ID,
        },
        "project_owner": {
          "name": "demo",
          "id": DEMO_USER_ID,
        },
        "project_creator": {
          "name": "admin",
          "id": ADMIN_USER_ID,
        },
      }
    }
]
