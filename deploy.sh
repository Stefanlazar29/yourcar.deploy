#!/bin/bash
cd /home/stefan/mulberry
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart mulberry
