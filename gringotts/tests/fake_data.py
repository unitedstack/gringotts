"""Fake data for all tests"""

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

INSTANCE_1_CREATED_TIME = '2014-01-08 03:38:36.129955'
INSTANCE_1_STOPPED_TIME = '2014-01-08 03:48:36.958285'
INSTANCE_1_STARTED_TIME = '2014-01-08 03:58:36.234075'
INSTANCE_1_DELETED_TIME = '2014-01-08 04:08:36.102935'

INSTANCE_2_CREATED_TIME = '2014-02-08 03:38:36.129955'
INSTANCE_2_STOPPED_TIME = '2014-02-08 03:48:36.958285'
INSTANCE_2_STARTED_TIME = '2014-02-08 03:58:36.234075'
INSTANCE_2_DELETED_TIME = '2014-02-08 04:08:36.102935'

INSTANCE_3_CREATED_TIME = '2014-03-08 03:38:36.129955'
INSTANCE_3_STOPPED_TIME = '2014-03-08 03:48:36.958285'
INSTANCE_3_STARTED_TIME = '2014-03-08 03:58:36.234075'
INSTANCE_3_DELETED_TIME = '2014-03-08 04:08:36.102935'

INSTANCE_4_CREATED_TIME = '2014-04-08 03:38:36.129955'
INSTANCE_4_STOPPED_TIME = '2014-04-08 03:48:36.958285'
INSTANCE_4_STARTED_TIME = '2014-04-08 03:58:36.234075'
INSTANCE_4_DELETED_TIME = '2014-04-08 04:08:36.102935'

# volumes
VOLUME_ID_1 = '7d0e2a0f-15dc-47f1-bb63-27513c6ab431'
VOLUME_ID_2 = '7d0e2a0f-15dc-47f1-bb63-27513c6ab432'

VOLUME_1_CREATED_TIME = '2014-01-08 05:18:36.612835'
VOLUME_1_RESIZED_TIME = '2014-01-08 05:28:36.237170'
VOLUME_1_DELETED_TIME = '2014-01-08 05:38:36.237170'

VOLUME_2_CREATED_TIME = '2014-02-08 05:18:36.612835'
VOLUME_2_RESIZED_TIME = '2014-02-08 05:28:36.237170'
VOLUME_2_DELETED_TIME = '2014-02-08 05:38:36.237170'

# routers
ROUTER_ID_1 = '3d659073-8a1f-4c16-a608-bc2c073af0f1'
ROUTER_ID_2 = '3d659073-8a1f-4c16-a608-bc2c073af0f2'

ROUTER_1_CREATED_TIME = '2014-01-08 06:08:36.237170'
ROUTER_1_DELETED_TIME = '2014-01-08 06:18:36.237170'


VOLUME_CREATED_TIME = '2014-01-08 03:18:36.612835'
VOLUME_RESIZED_TIME = '2014-01-08 03:28:36.237170'

INSTANCE_CREATED_TIME = '2014-01-08 03:38:36.129954'
INSTANCE_STOPPED_TIME = '2014-01-08 03:48:36.958286'
INSTANCE_STARTED_TIME = '2014-01-08 03:58:36.234079'
INSTANCE_DELETED_TIME = '2014-01-08 04:08:36.102937'


# -----------------I am style line :)-----------------

def make_instance_message(event_type=None, instance_id=None, display_name=None,
                          user_id=None, tenant_id=None, instance_type=None,
                          image_name=None, base_image_ref=None, disk_gb=None,
                          state=None, timestamp=None):
    message = {
        'event_type': event_type,
        'payload': {
            'instance_id': instance_id,
            'display_name': display_name,
            'user_id': user_id,
            'tenant_id': tenant_id,
            'instance_type': instance_type,
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

NOTICE_INSTANCE_2_CREATED = make_instance_created_message(INSTANCE_ID_2,
                                                          INSTANCE_2_CREATED_TIME,
                                                          display_name='vm2')

NOTICE_INSTANCE_3_CREATED = make_instance_created_message(INSTANCE_ID_3,
                                                          INSTANCE_3_CREATED_TIME,
                                                          display_name='vm3')

NOTICE_INSTANCE_4_CREATED = make_instance_created_message(INSTANCE_ID_4,
                                                          INSTANCE_4_CREATED_TIME,
                                                          display_name='vm4')

NOTICE_INSTANCE_1_STOPPED = make_instance_stopped_message(INSTANCE_ID_1,
                                                          INSTANCE_1_STOPPED_TIME,
                                                          display_name='vm1')

NOTICE_INSTANCE_2_STOPPED = make_instance_stopped_message(INSTANCE_ID_2,
                                                          INSTANCE_2_STOPPED_TIME,
                                                          display_name='vm2')

NOTICE_INSTANCE_3_STOPPED = make_instance_stopped_message(INSTANCE_ID_3,
                                                          INSTANCE_3_STOPPED_TIME,
                                                          display_name='vm3')

NOTICE_INSTANCE_4_STOPPED = make_instance_stopped_message(INSTANCE_ID_4,
                                                          INSTANCE_4_STOPPED_TIME,
                                                          display_name='vm4')

NOTICE_INSTANCE_1_STARTED = make_instance_started_message(INSTANCE_ID_1,
                                                          INSTANCE_1_STARTED_TIME,
                                                          display_name='vm1')

NOTICE_INSTANCE_2_STARTED = make_instance_started_message(INSTANCE_ID_2,
                                                          INSTANCE_2_STARTED_TIME,
                                                          display_name='vm2')

NOTICE_INSTANCE_3_STARTED = make_instance_started_message(INSTANCE_ID_3,
                                                          INSTANCE_3_STARTED_TIME,
                                                          display_name='vm3')

NOTICE_INSTANCE_4_STARTED = make_instance_started_message(INSTANCE_ID_4,
                                                          INSTANCE_4_STARTED_TIME,
                                                          display_name='vm4')

NOTICE_INSTANCE_1_DELETED = make_instance_deleted_message(INSTANCE_ID_1,
                                                          INSTANCE_1_DELETED_TIME,
                                                          display_name='vm1')

NOTICE_INSTANCE_2_DELETED = make_instance_deleted_message(INSTANCE_ID_2,
                                                          INSTANCE_2_DELETED_TIME,
                                                          display_name='vm2')

NOTICE_INSTANCE_3_DELETED = make_instance_deleted_message(INSTANCE_ID_3,
                                                          INSTANCE_3_DELETED_TIME,
                                                          display_name='vm3')

NOTICE_INSTANCE_4_DELETED = make_instance_deleted_message(INSTANCE_ID_4,
                                                          INSTANCE_4_DELETED_TIME,
                                                          display_name='vm4')

# -------------------I am style line :)----------------------------------

def make_volume_message(event_type=None, volume_id=None, display_name=None,
                        user_id=None, tenant_id=None, status=None,
                        size=None, timestamp=None):
    message = {
        'event_type': event_type,
        'payload': {
            'volume_id': volume_id,
            'display_name': display_name,
            'user_id': user_id,
            'tenant_id': tenant_id,
            'size': size,
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
                               size=kwargs.get('size') or 2,
                               timestamp=timestamp)

def make_volume_resized_message(volume_id, timestamp, **kwargs):
    return make_volume_message(event_type='volume.resize.end',
                               volume_id=volume_id,
                               display_name=kwargs.get('display_name') or 'vol',
                               user_id=DEMO_USER_ID,
                               tenant_id=DEMO_PROJECT_ID,
                               status='extending',
                               size=kwargs.get('size') or 4,
                               timestamp=timestamp)

def make_volume_deleted_message(volume_id, timestamp, **kwargs):
    return make_volume_message(event_type='volume.delete.end',
                               volume_id=volume_id,
                               display_name=kwargs.get('display_name') or 'vol',
                               user_id=DEMO_USER_ID,
                               tenant_id=DEMO_PROJECT_ID,
                               status='deleted',
                               size=kwargs.get('size') or 2,
                               timestamp=timestamp)


NOTICE_VOLUME_1_CREATED = make_volume_created_message(VOLUME_ID_1,
                                                      VOLUME_1_CREATED_TIME,
                                                      display_name='vol-1')

NOTICE_VOLUME_2_CREATED = make_volume_created_message(VOLUME_ID_2,
                                                      VOLUME_2_CREATED_TIME,
                                                      display_name='vol-2')

NOTICE_VOLUME_1_RESIZED = make_volume_resized_message(VOLUME_ID_1,
                                                      VOLUME_1_RESIZED_TIME,
                                                      display_name='vol-1')

NOTICE_VOLUME_2_RESIZED = make_volume_created_message(VOLUME_ID_2,
                                                      VOLUME_2_RESIZED_TIME,
                                                      display_name='vol-2')

NOTICE_VOLUME_1_DELETED = make_volume_deleted_message(VOLUME_ID_1,
                                                      VOLUME_1_DELETED_TIME,
                                                      display_name='vol-1')

NOTICE_VOLUME_2_DELETED = make_volume_deleted_message(VOLUME_ID_2,
                                                      VOLUME_2_DELETED_TIME,
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

NOTICE_ROUTER_1_DELETED = make_router_deleted_message(ROUTER_ID_1,
                                                      ROUTER_1_DELETED_TIME,
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
    "total_price": 0,
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
    "total_price": 0,
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
    "total_price": 0,
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
    "total_price": 0,
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
    "total_price": 0,
    "deleted": False
}

# account
FAKE_ACCOUNT_DEMO = {
    "user_id": DEMO_USER_ID,
    "project_id": DEMO_PROJECT_ID,
    "balance": 100,
    "consumption": 0,
    "currency": "CNY",
    "level": 3
}

FAKE_ACCOUNT_ADMIN = {
    "user_id": ADMIN_USER_ID,
    "project_id": ADMIN_PROJECT_ID,
    "balance": 8975,
    "consumption": 9527,
    "currency": "CNY",
    "level": 3
}
