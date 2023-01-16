#!/bin/bash
if [ "$EUID" -ne 0 ]
  then echo "Please run as root"
  exit
fi

echo MQTT Host:
read mqtthost
echo MQTT Port:
read mqttport
echo MQTT User:
read mqttuser
echo MQTT Password:
read mqttpwd

echo MYSQL Host:
read mysqlhost
echo MYSQL Database:
read mysqldb
echo MYSQL User:
read mysqluser
echo MYSQL Password:
read mysqlpwd

mkdir -p /etc/iMeshBackend/
cd /etc/iMeshBackend/

echo [MQTT] > iMeshBackend.conf
echo host=$mqtthost >> iMeshBackend.conf
echo port=$mqttport  >> iMeshBackend.conf
echo username=$mqttuser >> iMeshBackend.conf
echo password=$mqttpwd >> iMeshBackend.conf

echo [MYSQL] >> iMeshBackend.conf
echo host=$mysqlhost >> iMeshBackend.conf
echo database=$mysqldb  >> iMeshBackend.conf
echo username=$mysqluser >> iMeshBackend.conf
echo password=$mysqlpwd >> iMeshBackend.conf

sudo cp ./dist/iMeshBackend /usr/local/bin/

sudo cp ./service/iMeshBackend.service /etc/systemd/system
sudo cp ./service/iMeshDbClean.service /etc/systemd/system
sudo systemctl daemon-reload
sudo systemctl enable iMeshBackend
sudo systemctl enable iMeshDbClean
sudo systemctl daemon-reload
sudo systemctl stop iMeshBackend
sudo systemctl start iMeshBackend
sudo systemctl stop iMeshDbClean
sudo systemctl start iMeshDbClean
