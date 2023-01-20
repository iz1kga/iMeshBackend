#!/bin/bash
#IZ1KGA 2023
if [ "$EUID" -ne 0 ]
  then echo "Please run as root"
  exit
fi

mkdir -p /etc/iMeshBackend/


read -r -p "Do you want to set configuration? [y/N] " response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]
then
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

    echo [MQTT] > /etc/iMeshBackend/iMeshBackend.conf
    echo host=$mqtthost >> /etc/iMeshBackend/iMeshBackend.conf
    echo port=$mqttport  >> /etc/iMeshBackend/iMeshBackend.conf
    echo username=$mqttuser >> /etc/iMeshBackend/iMeshBackend.conf
    echo password=$mqttpwd >> /etc/iMeshBackend/iMeshBackend.conf

    echo [MYSQL] >> /etc/iMeshBackend/iMeshBackend.conf
    echo host=$mysqlhost >> /etc/iMeshBackend/iMeshBackend.conf
    echo database=$mysqldb  >> /etc/iMeshBackend/iMeshBackend.conf
    echo username=$mysqluser >> /etc/iMeshBackend/iMeshBackend.conf
    echo password=$mysqlpwd >> /etc/iMeshBackend/iMeshBackend.conf
fi


read -r -p "Do you want to Build Binaries? [y/N] " response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]
then
    python3 -m venv ./.buildVenv
    source .buildVenv/bin/activate
    pip install -r requirements.txt
    ./build.sh
    deactivate
    rm -r .buildVenv
fi


read -r -p "Do you want to update binary files? [y/N] " response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]
then
    echo "Stopping Services"
    systemctl stop iMeshBackend
    systemctl stop iMeshDbClean

    echo "Installing binary files"
    cp ./dist/* /usr/local/bin/

    echo "Starting Services"
    systemctl start iMeshBackend
    systemctl start iMeshDbClean

fi

read -r -p "Do you want to install as service? [y/N] " response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]
then
    cp ./service/iMeshBackend.service /etc/systemd/system
    cp ./service/iMeshDbClean.service /etc/systemd/system
    systemctl daemon-reload
    systemctl enable iMeshBackend
    systemctl enable iMeshDbClean
    systemctl daemon-reload
    systemctl stop iMeshBackend
    systemctl start iMeshBackend
    systemctl stop iMeshDbClean
    systemctl start iMeshDbClean
fi

