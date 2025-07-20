#!/bin/bash

# class_name=.realvnc-vncviewer
class_name=org.remmina.Remmina

# Find window ID by window class
window_id=$(wmctrl -lx | awk "/$class_name/ {print \$1}")

if [[ -n "$window_id" ]]; then
    active_window_id=$(xprop -root _NET_ACTIVE_WINDOW | awk '{print $5}')
    if (($active_window_id == $window_id)); then
        # Window is active, minimize it
        wmctrl -i -r "$window_id" -b add,hidden
    else
        # Window is not active, activate it
        wmctrl -i -a "$window_id"
    fi
else
    if [[ "$class_name" == "org.remmina.Remmina" ]]; then
        run_script r/vncviewer_remmina.sh
    else
        run_script r/vncviewer_realvnc.sh
    fi
fi
