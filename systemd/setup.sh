#!/bin/bash
sudo cp ./systemd/lotus-capture.service  /etc/systemd/system/lotus-capture.service
sudo cp ./systemd/lotus-capture.timer /etc/systemd/system/lotus-capture.timer
sudo systemctl daemon-reload
sudo systemctl enable --now lotus-capture.timer
