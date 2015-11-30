#!/bin/bash
repair_bill_id=9713464
mysql gringotts -e "select order_id, project_id, sum(total_price) from bill where id > $repair_bill_id group by order_id;" | grep -v order_id > orders.txt

line=`cat orders.txt | wc -l | tr -d " "`

for i in `seq $line`
do
    order_id=`awk '{print $1}' orders.txt | sed -n "${i}p"`
    project_id=`awk '{print $2}' orders.txt | sed -n "${i}p"`
    total_price=`awk '{print $3}' orders.txt | sed -n "${i}p"`

    echo $order_id

    # get billing owner
    user_id=`mysql gringotts -e "select user_id from project where project_id='$project_id'" | grep -v user_id`
    if [[ -z $user_id ]];then
        echo "$project_id has no billing owner"
        continue
    fi

    # update order
    mysql gringotts -e "update gringotts.order set total_price=total_price-$total_price where order_id='$order_id'";

    # update account
    mysql gringotts -e "update account set balance=balance+$total_price, consumption=consumption-$total_price where user_id='$user_id'";

    # update project
    mysql gringotts -e "update project set consumption=consumption-$total_price where user_id='$user_id'";

    # update user_project
    mysql gringotts -e "update user_project set consumption=consumption-$total_price where user_id='$user_id' and project_id='$project_id'";

    # delete bills
    mysql gringotts -e "delete from bill where order_id='$order_id' and id > $repair_bill_id";

    # get latest bill
    cron_time=`mysql gringotts -e "select end_time from bill where order_id='$order_id' order by id desc limit 1" | grep -v end_time`
    if [[ -n $cron_time ]]; then
        mysql gringotts -e "update gringotts.order set cron_time='$cron_time' where order_id='$order_id'";
    fi
done
