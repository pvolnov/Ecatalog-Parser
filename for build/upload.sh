sudo docker build -t neafiol/wilb:latest .
sudo docker push neafiol/wilb
ssh root@185.69.152.163 'cd /home/ && bash restart.sh'
