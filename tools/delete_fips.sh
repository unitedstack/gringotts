#! /bin/bash

source /opt/stack/devstack/openrc "admin" "admin"

cat /tmp/fips.txt | while read line
do
    neutron floatingip-delete $line
done
