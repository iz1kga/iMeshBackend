import paho.mqtt.client as mqtt
import MySQLdb
import json
import time
from geopy import distance
from datetime import datetime
import configparser
import os.path

configFile = '/etc/iMeshBackend/iMeshBackend.conf'

if not os.path.isfile(configFile):
    print("Config file not found (/etc/iMeshBackend/iMeshBackend.conf)")
    exit()

config = configparser.ConfigParser()
config.read(configFile)

hwModels = ("UNSET", "TLORA_V2", "TLORA_V1", "TLORA_V2_1_1P6", "TBEAM", "HELTEC_V2_0", "TBEAM_V0P7", "T_ECHO", "TLORA_V1_1P3", "RAK4631", "HELTEC_V2_1", "HELTEC_V1", "LILYGO_TBEAM_S3_CORE", "RAK11200", "NANO_G1", "TLORA_V2_1_1P8", "STATION_G1", "LORA_RELAY_V1", "NRF52840DK", "PPR", "GENIEBLOCKS", "NRF52_UNKNOWN", "PORTDUINO", "ANDROID_SIM", "DIY_V1", "NRF52840_PCA10059", "DR_DEV", "M5STACK", "PRIVATE_HW")

def tohex(val, nbits):
  return hex((val + (1 << nbits)) % (1 << nbits))

def updateQuery(db, c, table, field, value, id):
    try:
        query = ("UPDATE %s SET %s=%s WHERE id=\"%s\"" 
                 % (table, field, value, id))
        print(query)
        c.execute(query)
        db.commit()
    except Exception as e:
        print(e)


# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("msh/2/json/LongFast/#")

# The callback for when a PUBLISH message is received from the server.

def on_message(client, userdata, msg):
    print("received MQTT message: %s - %s" % (msg.topic, msg.payload))
    payload = json.loads(msg.payload.decode("utf-8"))
    db=MySQLdb.connect(config['MYSQL']['host'], config['MYSQL']['username'], config['MYSQL']['password'], config['MYSQL']['database'])
    c=db.cursor(MySQLdb.cursors.DictCursor)

    nodeID=str(tohex(payload["from"], 32))
    nodeID=nodeID[2:len(nodeID)]
    for i in range(0, 8-len(nodeID)):
        nodeID = "0"+nodeID
    nodeID="!"+nodeID

#   print("HEXID: " + str(tohex(payload["from"], 32)))
    query = ("SELECT * FROM meshNodes where id=\"%s\"" % (nodeID, ))
    print(query)
    c.execute(query)
    data = c.fetchall()
#    print(data)
    if len(data) > 0:
        if (payload["id"] == data[0]["lastPacketID"]):
            print("Node %s: discarded packet allready received" % (nodeID,))
            return
        msgDT = datetime.fromtimestamp(payload["timestamp"])
        if payload["type"] == "text":
            pubPayload="{\"timestamp\":\"%s\", \"message\":\"%s (%s) - %s\", \"type\":\"text\"}" % (msgDT, data[0]["longName"], nodeID, payload["payload"]["text"])
        else:
            pubPayload="{\"timestamp\":\"%s\", \"message\":\"Received %s frame from %s (%s)\", \"type\":\"info\"}" % (msgDT, payload["type"], data[0]["longName"], nodeID, )
        client.publish("msh/2/stat/updates", payload=pubPayload, qos=0, retain=False)
#        print("found")
        if payload["type"] == "position":
            try:
                if payload["payload"]["latitude_i"] != 0 and payload["payload"]["longitude_i"] !=0 and payload["payload"]["altitude"] < 5000: 
                    query = ("UPDATE meshNodes SET latitude=%s, longitude=%s, altitude=%s, positionTimestamp=%s, timestamp=%s WHERE id=\"%s\"" 
                             % (payload["payload"]["latitude_i"]/10000000,
                                payload["payload"]["longitude_i"]/10000000,
                                payload["payload"]["altitude"],
                                payload["timestamp"],
                                payload["timestamp"],
                                nodeID))
                    print(query)
                    c.execute(query)
                    db.commit()

                    query = ("SELECT * from  nodesPositionHistory WHERE nodeID=\"%s\" ORDER BY timestamp DESC LIMIT 1"
                          % (nodeID,))
                    print(query)
                    c.execute(query)
                    posData = c.fetchall()
                    dist = 100
                    if len(posData) > 0:
                        dist = distance.distance((posData[0]["latitude"], posData[0]["longitude"]),
                               (payload["payload"]["latitude_i"]/10000000, payload["payload"]["longitude_i"]/10000000)).km
                        print("DISTANCE %s" % (dist, ))
                    if dist > 0.25:
                        query = ("INSERT INTO nodesPositionHistory (nodeID, latitude, longitude, timestamp) VALUES (\"%s\", %s, %s, %s)"
                              % (nodeID, payload["payload"]["latitude_i"]/10000000, payload["payload"]["longitude_i"]/10000000, payload["timestamp"],))
                        print(query)
                        c.execute(query)
                        db.commit()

            except Exception as e:
                print(e)

        if payload["type"] == "nodeinfo":
            try:
                query = ("UPDATE meshNodes SET longname=\"%s\", shortname=\"%s\", hardware=\"%s\" WHERE id=\"%s\"" 
                         % (payload["payload"]["longname"], payload["payload"]["shortname"], hwModels[payload["payload"]["hardware"]], nodeID))
                print(query)
                c.execute(query)
                db.commit()
            except Exception as e:
                print(e)

        if payload["type"] == "telemetry":
            if "temperature" in payload["payload"]:
                updateQuery(db, c, "meshNodes", "temperature", payload["payload"]["temperature"], nodeID)
            if "barometric_pressure" in payload["payload"]:
                updateQuery(db, c, "meshNodes", "pressure", payload["payload"]["barometric_pressure"], nodeID)
            if "relative_humidity" in payload["payload"]:
                updateQuery(db, c, "meshNodes", "humidity", payload["payload"]["relative_humidity"], nodeID)
            if "battery_level" in payload["payload"]:
                updateQuery(db, c, "meshNodes", "batteryLevel", payload["payload"]["battery_level"], nodeID)
            if "voltage" in payload["payload"]:
                updateQuery(db, c, "meshNodes", "batteryVoltage", payload["payload"]["voltage"], nodeID)
            if "air_util_tx" in payload["payload"]:
                updateQuery(db, c, "meshNodes", "airUtil", payload["payload"]["air_util_tx"], nodeID)
            if "channel_utilization" in payload["payload"]:
                updateQuery(db, c, "meshNodes", "chUtil", payload["payload"]["channel_utilization"], nodeID)

        updateQuery(db, c, "meshNodes", "lastPacketID", payload["id"], nodeID)
    else:
        try:
            print("###########################################################")
            print("Node %s: Insert into DB" % (nodeID,))
            query = ("INSERT INTO meshNodes (id, positionTimestamp,timestamp) VALUES (\"%s\", \"%s\", \"%s\")" % (nodeID, 0, payload["timestamp"],))
            print(query)
            print("###########################################################")
            c.execute(query)
            db.commit()
        except Exception as e:
            print(e)
    db.close()

def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.username_pw_set(config['MQTT']['username'], config['MQTT']['password'])
    client.connect(config['MQTT']['host'], int(config['MQTT']['port']), 60)
    client.loop_forever()


if __name__ == '__main__':
    main()
