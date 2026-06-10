sudo nmcli con add type ethernet ifname enp6s0 con-name local-lotusnet \
ipv4.metho manual ipv4.addresses 192.168.1.1/24 \
ipv6.method disabled \
connection.autoconnect yes

sudo nmcli con up local-lotusnet

