
from gringotts import constants as gring_const


def product_instance(name, unit_price):
    product = {
        'name': name,
        'service': 'compute',
        'description': 'some desc',
        'unit_price': unit_price,
        'unit': 'hour',
    }
    return product


PRODUCT_INSTANCE_MICRO1 = product_instance('instance:micro-1', 0.0560)
PRODUCT_INSTANCE_MICRO2 = product_instance('instance:micro-2', 0.1110)
PRODUCT_INSTANCE_STANDARD1 = product_instance('instance:standard-1', 0.2220)
PRODUCT_INSTANCE_STANDARD2 = product_instance('instance:standard-2', 0.4440)
PRODUCT_INSTANCE_STANDARD4 = product_instance('instance:standard-4', 0.8890)
PRODUCT_INSTANCE_STANDARD8 = product_instance('instance:standard-8', 1.7780)
PRODUCT_INSTANCE_STANDARD12 = product_instance('instance:standard-12', 2.6670)
PRODUCT_INSTANCE_STANDARD16 = product_instance('instance:standard-16', 3.5560)
PRODUCT_INSTANCE_MEMORY1 = product_instance('instance:memory-1', 0.3610)
PRODUCT_INSTANCE_MEMORY2 = product_instance('instance:memory-2', 0.7220)
PRODUCT_INSTANCE_MEMORY4 = product_instance('instance:memory-4', 1.4440)
PRODUCT_INSTANCE_MEMORY8 = product_instance('instance:memory-8', 2.8890)
PRODUCT_INSTANCE_MEMORY12 = product_instance('instance:memory-12', 4.3330)
PRODUCT_INSTANCE_COMPUTE2 = product_instance('instance:compute-2', 0.3330)
PRODUCT_INSTANCE_COMPUTE4 = product_instance('instance:compute-4', 0.6670)
PRODUCT_INSTANCE_COMPUTE8 = product_instance('instance:compute-8', 1.3330)
PRODUCT_INSTANCE_COMPUTE12 = product_instance('instance:compute-12', 2.0000)

PRODUCT_IP_FLOATING = dict(
    name='ip.floating', service='network', description='some desc',
    unit_price=0.030, unit='hour')

PRODUCT_IP_FLOATING_CHINAMOBILE_CHINAUNICOM = dict(
    name='ip.floating.CHINAMOBILE-CHINAUNICOM', service='network',
    description='some desc', unit_price=0.050, unit='hour')

PRODUCT_SATA_VOLUME_SIZE = dict(
    name='sata.volume.size', service='block_storage',
    description='sata volume', unit_price=0.006, unit='hour')

PRODUCT_VOLUME_SIZE = dict(
    name='volume.size', service='block_storage',
    description='ssd volume', unit_price=0.02, unit='hour')

instance_products = [
    PRODUCT_INSTANCE_MICRO1,
    PRODUCT_INSTANCE_MICRO2,
    PRODUCT_INSTANCE_STANDARD1,
    PRODUCT_INSTANCE_STANDARD2,
    PRODUCT_INSTANCE_STANDARD4,
    PRODUCT_INSTANCE_STANDARD8,
    PRODUCT_INSTANCE_STANDARD12,
    PRODUCT_INSTANCE_STANDARD16,
    PRODUCT_INSTANCE_MEMORY1,
    PRODUCT_INSTANCE_MEMORY2,
    PRODUCT_INSTANCE_MEMORY4,
    PRODUCT_INSTANCE_MEMORY8,
    PRODUCT_INSTANCE_MEMORY12,
    PRODUCT_INSTANCE_COMPUTE2,
    PRODUCT_INSTANCE_COMPUTE4,
    PRODUCT_INSTANCE_COMPUTE8,
    PRODUCT_INSTANCE_COMPUTE12,
]

ip_products = [
    PRODUCT_IP_FLOATING,
    PRODUCT_IP_FLOATING_CHINAMOBILE_CHINAUNICOM,
]

volume_products = [
    PRODUCT_SATA_VOLUME_SIZE,
    PRODUCT_VOLUME_SIZE
]
