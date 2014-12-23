#!/usr/bin/env bash

source ~/devstack/openrc admin admin

function help {
    echo "./quota.sh help"
    echo "./quota.sh show <tenant-id>"
    echo "./quota.sh update <tenant-id>"
    echo "                  [--instances <instances>] [--cores <cores>] [--ram <ram>]"
    echo "                  [--volume-type <volume_type_name> --volumes <volumes> --gigabytes <gigabytes> --snapshots <snapshots>]"
    echo "                  [--floatingip <floatingips>] [--loadbalancer <loadbalancers>] [--listener <listeners>]"
}

function show {
    # nova
    read -a nova_quota <<< `nova quota-show --tenant $PROJECT_ID | sed -n '4,6p' | tr -d " "`

    # cinder
    read -a cinder_quota <<< `cinder quota-show $PROJECT_ID | sed -n '4,12p' | tr -d " "`

    # neutron
    raw_neutron_quota=`neutron quota-show --tenant-id $PROJECT_ID`
    read -a neutron_quota <<< `echo "$raw_neutron_quota" | sed -n '4p' | tr -d " "`
    neutron_quota=(${neutron_quota[@]} `echo "$raw_neutron_quota" | sed -n '9,10p' | tr -d " "`)

    quotas=(${quotas[@]} ${nova_quota[@]})
    quotas=(${quotas[@]} ${cinder_quota[@]})
    quotas=(${quotas[@]} ${neutron_quota[@]})
    printf "+-----------------------------+----------+\n"
    printf "| Quota                       | Limit    |\n"
    printf "+-----------------------------+----------+\n"
    for quota in ${quotas[@]}
    do
        field=`echo $quota | awk -F '|' '{print $2}'`
        value=`echo $quota | awk -F '|' '{print $3}'`
        l_field=`expr 28 - ${#field}`
        l_value=`expr 9 - ${#value}`
        printf "| %s" $field
        for i in `seq $l_field`; do printf " "; done
        printf "| %s" $value
        for i in `seq $l_value`; do printf " "; done
        printf "|\n"
    done
    printf "+-----------------------------+----------+\n"

}

function nova_quota_update {
    # paramters:
    # * instances|x
    # * cores|y
    # * ram|z

    instances=`echo $1 | awk -F '|' '{print $2}'`
    cores=`echo $2 | awk -F '|' '{print $2}'`
    ram=`echo $3 | awk -F '|' '{print $2}'`

    cmd="nova quota-update"
    flag="0"

    if [[ $instances != '-' ]]; then
        cmd="$cmd --instances $instances"
        flag="1"
    fi
    if [[ $cores != '-' ]]; then
        cmd="$cmd --cores $cores"
        flag="1"
    fi
    if [[ $ram != '-' ]]; then
        cmd="$cmd --ram $ram"
        flag="1"
    fi

    cmd="$cmd $PROJECT_ID"

    if [[ $flag == "1" ]]; then
        echo $cmd
        eval $cmd 1>/dev/null
    fi
}

function cinder_quota_update {
    # paramters:
    # * volume_type|-
    # * volumes|-
    # * gigabytes|-
    # * snapshots|-

    volume_type=`echo $1 | awk -F '|' '{print $2}'`
    volumes=`echo $2 | awk -F '|' '{print $2}'`
    gigabytes=`echo $3 | awk -F '|' '{print $2}'`
    snapshots=`echo $4 | awk -F '|' '{print $2}'`

    cmd="cinder quota-update"
    flag="0"

    if [[ $volumes != '-' ]]; then
        cmd="$cmd --volumes $volumes"
        flag="1"
    fi

    if [[ $gigabytes != '-' ]]; then
        cmd="$cmd --gigabytes $gigabytes"
        flag="1"
    fi

    if [[ $snapshots != '-' ]]; then
        cmd="$cmd --snapshots $snapshots"
        flag="1"
    fi

    if [[ $volume_type != '-' ]]; then
        cmd="$cmd --volume-type $volume_type"
        cmd="$cmd $PROJECT_ID"

        if [[ $flag == "1" ]]; then
            echo $cmd
            eval $cmd 1>/dev/null

            read -a cinder_quota <<< `cinder quota-show $PROJECT_ID | sed -n '4,12p' | awk -F '|' '{print $3}' | tr -d " "`
            gigabytes=`expr ${cinder_quota[1]} + ${cinder_quota[2]}`
            snapshots=`expr ${cinder_quota[4]} + ${cinder_quota[5]}`
            volumes=`expr ${cinder_quota[7]} + ${cinder_quota[8]}`
            cmd="cinder quota-update --volumes $volumes --gigabytes $gigabytes --snapshots $snapshots $PROJECT_ID"
            echo $cmd
            eval $cmd 1>/dev/null
        fi
    else
        cmd="$cmd $PROJECT_ID"
        if [[ $flag == "1" ]]; then
            echo $cmd
            eval $cmd 1>/dev/null
        fi
    fi
}

function neutron_quota_update {
    # paramters:
    # * floatingip|-
    # * loadbalancer|-
    # * listener|-

    floatingip=`echo $1 | awk -F '|' '{print $2}'`
    loadbalancer=`echo $2 | awk -F '|' '{print $2}'`
    listener=`echo $3 | awk -F '|' '{print $2}'`

    cmd="neutron quota-update"
    flag="0"

    if [[ $floatingip != '-' ]];then
        cmd="$cmd --floatingip $floatingip"
        flag="1"
    fi

    if [[ $loadbalancer != '-' ]]; then
        cmd="$cmd --loadbalancer $loadbalancer"
        flag="1"
    fi

    if [[ $listener != '-' ]]; then
        cmd="$cmd --listener $listener"
        flag="1"
    fi

    if [[ $flag == "1" ]]; then
        cmd="$cmd --tenant-id $PROJECT_ID"
        echo $cmd
        eval $cmd 1>/dev/null
    fi
}

function check_field {
    if [[ $1 == "instances" || $1 == "cores" || $1 == "ram" ||
          $1 == "volumetype" || $1 == "volumes" || $1 == "gigabytes" || $1 == "snapshots" ||
          $1 == "floatingip" || $1 == "loadbalancer" || $1 == "listener" ||
          ! -n $1 ]]; then
        return
    else
        help
        exit
    fi
}


ACTION=$1
PROJECT_ID=$2

if [[ $ACTION == 'show' && -n $PROJECT_ID ]]; then
    show
elif [[ $ACTION == 'update' && -n $PROJECT_ID ]]; then

    instances="instances|-"
    cores="cores|-"
    ram="ram|-"
    volume_type="volume_type|-"
    volumes="volumes|-"
    gigabytes="gigabytes|-"
    snapshots="snapshots|-"
    floatingip="floatingip|-"
    loadbalancer="loadbalancer|-"
    listener="listener|-"

    read -a params <<< "$@"
    for i in 2 4 6 8 10 12 14 16 18 20
    do
        j=`expr $i + 1`
        field=`echo ${params[$i]} | tr -d "-"`
        value=`echo ${params[$j]}`

        check_field $field

        if [[ $field == "instances" ]]; then
            instances="instances|${value:--}"
        elif [[ $field == "cores" ]]; then
            cores="cores|${value:--}"
        elif [[ $field == "ram" ]]; then
            ram="ram|${value:--}"
        elif [[ $field == "volumetype" ]]; then
            volume_type="volume_type|${value:--}"
        elif [[ $field == "volumes" ]]; then
            volumes="volumes|${value:--}"
        elif [[ $field == "gigabytes" ]]; then
            gigabytes="gigabytes|${value:--}"
        elif [[ $field == "snapshots" ]]; then
            snapshots="snapshots|${value:--}"
        elif [[ $field == "floatingip" ]]; then
            floatingip="floatingip|${value:--}"
        elif [[ $field == "loadbalancer" ]]; then
            loadbalancer="loadbalancer|${value:--}"
        elif [[ $field == "listener" ]]; then
            listener="listener|${value:--}"
        fi
    done

    nova_quota_update $instances $cores $ram
    cinder_quota_update $volume_type $volumes $gigabytes $snapshots
    neutron_quota_update $floatingip $loadbalancer $listener

else
    help
fi
