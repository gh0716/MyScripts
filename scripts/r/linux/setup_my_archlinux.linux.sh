set -e

prepend_line_dedup() {
    # Remove the line if it exists and then prepend it
    if [[ -f "$1" ]] && grep -qF -- "$2" "$1"; then
        repl=$(printf '%s\n' "$2" | sed -e 's/[]\/$*.^[]/\\&/g')
        sed -i "\%^$repl$%d" "$1"
    fi
    printf '%s\n%s\n' "$2" "$(cat $1)" >"$1"
}

append_line_dedup() {
    # Remove the line if it exists and then append it
    if [[ -f "$1" ]] && grep -qF -- "$2" "$1"; then
        repl=$(printf '%s\n' "$2" | sed -e 's/[]\/$*.^[]/\\&/g')
        sed -i "\%^$repl$%d" "$1"
    fi
    echo "$2" >>"$1"
}

append_line_sudo() {
    if [[ ! -f $1 ]] || ! sudo grep -qF -- "$2" $1; then
        echo "$2" | sudo tee -a $1
    fi
}

pac_install() {
    sudo pacman -S --noconfirm --needed "$@"
}

yay_install() {
    yay -S --noconfirm --needed --needed "$@"
}

# Install utilities.
# - acpi: for battery monitor
pac_install \
    alacritty \
    acpi \
    fzf \
    git \
    inetutils \
    less \
    neovim \
    openssh \
    sxhkd \
    unzip \
    wmctrl \
    xclip

# Install fonts
pac_install $(pacman -Ssq 'noto-fonts-*')

# Install yay - AUR package manager: https://github.com/Jguer/yay#binary
if [[ ! -x "$(command -v yay)" ]]; then
    (
        cd /tmp/
        sudo pacman -S --needed --noconfirm git base-devel
        git clone https://aur.archlinux.org/yay-bin.git
        cd yay-bin
        makepkg -si
        cd ..
        rm yay-bin -rf
    )
fi

yay_install visual-studio-code-bin google-chrome

# Configure HiDPI display
DPI_VALUE=144 # 96 * 1.5
if ! grep -qF -- "Xft.dpi" ~/.Xresources; then
    echo "Xft.dpi: $DPI_VALUE" >>~/.Xresources
else
    sed -i "s/Xft.dpi:.*/Xft.dpi: $DPI_VALUE/" ~/.Xresources
fi
# This should be the first line of .xinitrc, so that all other apps can get the correct DPI value.
prepend_line_dedup ~/.xinitrc "xrdb -merge ~/.Xresources"

# Network manager
pac_install network-manager-applet
append_line_dedup ~/.xinitrc "nm-applet &"

# Bluetooth
# - bluez and bluez-utils: a Linux Bluetooth stack
# - blueman: GUI tool for desktop environments
pac_install bluez bluez-utils # blueman
# append_line_dedup ~/.xinitrc "blueman-applet &"
sudo systemctl enable bluetooth.service --now
# then you can use bluetoothctl to pair in command line

# Setup audio
pac_install pulseaudio pavucontrol pulseaudio-bluetooth
pac_install alsa-utils # for amixer CLI command

# Setup input method
# https://wiki.archlinux.org/title/Fcitx5
pac_install fcitx5 fcitx5-qt fcitx5-gtk fcitx5-config-qt fcitx5-chinese-addons
append_line_dedup ~/.xinitrc "fcitx5 -d"

# Key mapping using https://github.com/rvaiya/keyd
# Map "CapsLock" to "Control + Meta" key.
yay_install keyd
sudo tee /etc/keyd/default.conf <<EOF
[ids]
*
[main]
capslock = overload(capslock, esc)

[capslock:C-M]
EOF
sudo systemctl enable keyd.service --now

# Automatically run startx without using display manager / login manager.
append_line_dedup \
    "$HOME/.bash_profile" \
    '[[ -z $DISPLAY ]] && [[ $(tty) = /dev/tty1 ]] && startx'

# Configure bash alias.
append_line_dedup "$HOME/.bashrc" 'alias v="nvim"'
append_line_dedup "$HOME/.bashrc" 'alias i="sudo pacman -S --noconfirm"'

# Automatically mount USB devices
pac_install udisks2 udiskie
append_line_dedup ~/.xinitrc "udiskie &"

# Install window manager
source "$(dirname "$0")/setup_awesomewm.sh"

# Install dev tools
yay_install yarn mongodb-bin mongodb-tools-bin
sudo systemctl enable mongodb.service --now

# ------------------------------
# Hardware specific (TODO: move)
# ------------------------------

# Install proprietary NVIDIA GPU driver.
# https://wiki.archlinux.org/title/NVIDIA#Xorg_configuration
if lspci -k | grep -q "NVIDIA Corporation"; then
    kernel_version=$(uname -r)
    if [[ $kernel_version == *lts* ]]; then
        pac_install nvidia-lts
    else
        pac_install nvidia
    fi
    pac_install nvidia-settings
fi

setup_logitech_keyboard() {
    pac_install solaar # Logitech device manager
    append_line_dedup ~/.xinitrc 'solaar --window hide &'

    sudo bash -c 'cat > /usr/bin/logitech-fn-swap << EOF
#!/bin/bash
while true; do
    solaar config K380 fn-swap off
    solaar config K600 fn-swap off
    sleep 10
done
EOF'

    sudo chmod +x /usr/bin/logitech-fn-swap

    sudo bash -c 'cat > /etc/systemd/system/logitech-fn-swap.service <<EOF
[Unit]
Description=logitech-fn-swap systemd service unit file.

[Service]
ExecStart=/usr/bin/logitech-fn-swap

[Install]
WantedBy=multi-user.target
EOF'

    sudo systemctl daemon-reload
    sudo systemctl restart logitech-fn-swap.service --now
}

setup_logitech_keyboard

# Configure Touchpad:
# https://wiki.archlinux.org/title/Touchpad_Synaptics
sudo tee /etc/X11/xorg.conf.d/70-synaptics.conf <<EOF
Section "InputClass"
    Identifier "touchpad"
    Option "tapping" "on"
    # Natural scrolling:
    Option "VertScrollDelta" "-111"
    Option "HorizScrollDelta" "-111"
EndSection
EOF

# Auto-start MyScript
append_line_dedup ~/.xinitrc 'alacritty -e "$HOME/MyScripts/myscripts" --startup &'

# Replace the current process with the awesomewm when initializing X.
append_line_dedup ~/.xinitrc "exec awesome"

# Disable sudo password
append_line_sudo /etc/sudoers "$(whoami) ALL=(ALL:ALL) NOPASSWD: ALL"

# ------------
# Install Apps
# ------------

# Screenshot
pac_install flameshot
append_line_dedup ~/.xinitrc 'flameshot &'

# Install GitHub CLI
pac_install github-cli
if [[ "$(gh auth status 2>&1)" =~ "not logged" ]]; then
    gh auth login
fi
