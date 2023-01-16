# iMeshBackend

This piece of bad written SW is intended to provide a backend to process  JSON messages sent by Meshtastic nodes to an MQTT Broker and save useful data to a MYSQL database in order to draw map and do stuff.

# Requirements

MYSQL server shall be installed a dedicated database shall be created, in db folder there is **meshtastic.sql** that contains tables structure description.

MQTT broker shall be installed and properly configured TBD

# Installation
```
git clone https://github.com/iz1kga/iMeshBackend.git
cd iMeshBackend
sudo ./install.sh
```
Set all requested information, at the end of the installation two new services should be running. Check that everything worked the right way:
```
sudo service iMeshBackend status
sudo service iMeshDbClean status
```
