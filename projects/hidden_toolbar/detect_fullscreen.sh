#!/bin/bash
while true; do
    if xprop -root _NET_WM_STATE | grep -q "_NET_WM_STATE_FULLSCREEN"; then
        xdotool search --onlyvisible --name '' windowunmap
    else
        xdotool search --onlyvisible --name '' windowmap
    fi
    sleep 1
done
