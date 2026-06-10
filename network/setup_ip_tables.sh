sudo iptables -t nat -A POSTROUTING -o enp6s0 -j MASQUERADE

sudo apt install iptables-persistent
sudo netfilter-persistent save
