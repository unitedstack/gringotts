SCREEN_NAME=${SCREEN_NAME:-gring}
USE_SCREEN=${USE_SCREEN:-True}
CONFIG_FILE=${CONFIG_FILE:-/etc/gringotts/gringotts.conf}

function screen_it {

    echo "staring $1"

    if [[ "$USE_SCREEN" = "True" ]]; then
        screen -S $SCREEN_NAME -X screen -t $1

        sleep 1.5

        NL=`echo -ne '\015'`
        screen -S $SCREEN_NAME -p $1 -X stuff "$2 || touch $1.failure$NL"
    fi
}

# Check to see if we are already running gringotts
if type -p screen >/dev/null && screen -ls | egrep -q "[0-9].$SCREEN_NAME"; then
    echo "You are already running a stack.sh session."
    echo "To rejoin this session type 'screen -x gring'."
    echo "To destroy this session, type './unstack.sh'."
    exit 1
fi

if [[ "$USE_SCREEN" == "True" ]]; then
    # Create a new named screen to run processes in
    screen -d -m -S $SCREEN_NAME -t shell -s /bin/bash
    sleep 1

    # Set a reasonable status bar
    if [ -z "$SCREEN_HARDSTATUS" ]; then
        SCREEN_HARDSTATUS='%{= .} %-Lw%{= .}%> %n%f %t*%{= .}%+Lw%< %-=%{g}(%{d}%H/%l%{g})'
    fi
    screen -r $SCREEN_NAME -X hardstatus alwayslastline "$SCREEN_HARDSTATUS"
    screen -r $SCREEN_NAME -X setenv PROMPT_COMMAND /bin/true
fi

screen_it gring-api "cd ; gring-api --config-file $CONFIG_FILE"
screen_it gring-waiter "cd ; gring-waiter --config-file $CONFIG_FILE"
screen_it gring-master "cd ; gring-master --config-file $CONFIG_FILE"

echo "Type 'screen -x $SCREEN_NAME' to join the session"
