SCREEN_NAME=${SCREEN_NAME:-checker}
CONFIG_FILE=${CONFIG_FILE:-/etc/gringotts/gringotts.conf}
CHECKER_SERVICE_PY=${CHECKER_SERVICE_PY:-/opt/stack/gringotts/gringotts/checker/service.py}
MYSQL_HOST=${MYSQL_HOST:-localhost}
MYSQL_USER=${MYSQL_USER:-root}
MYSQL_PASS=${MYSQL_PASS:-rachel}

function screen_it {

    title=$1
    start=$2
    end=$3

    echo "starting $title"

    CMD="cd;"
    CMD="$CMD sed -i -e \"315 s/projects.*/projects[$start:$end]:/g\" $CHECKER_SERVICE_PY;"
    CMD="$CMD sed -i -e \"427 s/projects.*/projects[$start:$end]:/g\" $CHECKER_SERVICE_PY;"
    CMD="$CMD gring-checker --config-file $CONFIG_FILE"

    screen -S $SCREEN_NAME -X screen -t $title
    NL=`echo -ne '\015'`
    screen -S $SCREEN_NAME -p $title -X stuff "$CMD$NL"

    sleep 1

    sed -i -e "315 s/projects.*/projects:/g" $CHECKER_SERVICE_PY
    sed -i -e "427 s/projects.*/projects:/g" $CHECKER_SERVICE_PY
}

# Check to see if we are already running gringotts
if type -p screen >/dev/null && screen -ls | egrep -q "[0-9].$SCREEN_NAME"; then
    echo "You are already running a checker.sh session."
    echo "To rejoin this session type 'screen -x checker'."
    exit 1
fi

# get project number from db
count=`mysql -h$MYSQL_HOST -u$MYSQL_USER -p$MYSQL_PASS gringotts -e "select count(*) from project" | grep -v "count" | awk '{print $1}'`
count=`expr $count / 500 + 1`

# Create a new named screen to run processes in
screen -d -m -S $SCREEN_NAME -t shell -s /bin/bash

# Set a reasonable status bar
SCREEN_HARDSTATUS='%{= .} %-Lw%{= .}%> %n%f %t*%{= .}%+Lw%< %-=%{g}(%{d}%H/%l%{g})'
screen -r $SCREEN_NAME -X hardstatus alwayslastline "$SCREEN_HARDSTATUS"

# start
for i in `seq $count`; do
    i=`expr $i - 1`
    start=`expr $i \* 500`
    end=`expr $start + 500`
    title="${start}-${end}"
    screen_it $title $start $end
done

echo "Type 'screen -x $SCREEN_NAME' to join the session"
