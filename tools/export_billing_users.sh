#!/bin/bash

# get user_id, balance from gringotts database
mysql -e "select user_id, balance from gringotts.account" | awk '{print $1" "$2}' | grep -v "user_id" | sort -u > user_ids.txt

# get user email address from keystone database
echo -n > users.txt
line=`cat user_ids.txt | wc -l | tr -d " "`

for i in `seq $line`
do
    user_id=`awk '{print $1}' user_ids.txt | sed -n "${i}p"`
    balance=`awk '{print $2}' user_ids.txt | sed -n "${i}p"`
    email=`mysql -e "select extra from keystone.user where id='$user_id'" | grep email | python -c 'import json, sys; info=sys.stdin.read(); finfo=json.loads(info) if info else {"email": "unknown"}; print finfo["email"]'`
    echo "$user_id $balance $email" >> users.txt
done
