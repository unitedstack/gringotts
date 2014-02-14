SCREEN_NAME=${SCREEN_NAME:-gring}

function stop_gringotts() {
    for serv in gring-api gring-waiter gring-master; do
        echo "stopping $serv"
        screen -S $SCREEN_NAME -p $serv -X kill
        sleep 1
    done
}

stop_gringotts

SCREEN=$(which screen)
if [[ -n "$SCREEN" ]]; then
    SESSION=$(screen -ls | awk '/[0-9].'$SCREEN_NAME'/ { print $1 }')
    if [[ -n "$SESSION" ]]; then
        screen -X -S $SESSION quit
    fi
fi
