import sys
import paho.mqtt.client as mqtt
import MySQLdb
import json
import time
from geopy import distance
from datetime import datetime
import configparser
import os.path
import logging
import logging.handlers
import numpy as np

configFile = '/etc/iMeshBackend/iMeshBackend.conf'
logfile = '/var/log/iMeshBackend.log'
mqttLogfile = '/var/log/iMeshBackend.mqtt.log'
mqttDiscardLogfile = '/var/log/iMeshBackend.mqtt.discard.log'


#logging.basicConfig(filename=logfile, encoding='utf-8', level=logger.DEBUG)

try:
    if sys.argv[1] == "INFO":
        level = logging.INFO
    elif sys.argv[1] =="DEBUG":
        level = logging.DEBUG
    elif sys.argv[1] =="WARNING":
        level = logging.WARNING
    else:
        raise Exception("DefArg")
except:
    level = logging.ERROR


logger = logging.getLogger('iMeshBackEnd')
logger.setLevel(level)
#handler = logging.FileHandler(logfile, 'w', 'utf-8')
logHandler = logging.handlers.TimedRotatingFileHandler(logfile, when="D", interval=1, backupCount=7)
logger.addHandler(logHandler)

mqttLogger = logging.getLogger('iMeshBackendMqtt')
mqttLogger.setLevel(logging.DEBUG)
mqttLogHandler = logging.handlers.TimedRotatingFileHandler(mqttLogfile, when="D", interval=1, backupCount=7)
mqttLogger.addHandler(mqttLogHandler)

discardLogger = logging.getLogger('iMeshBackendMqttDiscard')
discardLogger.setLevel(logging.DEBUG)
discardLogHandler = logging.handlers.TimedRotatingFileHandler(mqttDiscardLogfile, when="D", interval=1, backupCount=7)
discardLogger.addHandler(discardLogHandler)


if not os.path.isfile(configFile):
    logger.error("%s - Config file not found (/etc/iMeshBackend/iMeshBackend.conf)" % datetime.now())
    exit()

config = configparser.ConfigParser()
config.read(configFile)

hwModels = ("UNSET", "TLORA_V2", "TLORA_V1", "TLORA_V2_1_1P6", "TBEAM", "HELTEC_V2_0", "TBEAM_V0P7", "T_ECHO", "TLORA_V1_1P3", "RAK4631", "HELTEC_V2_1", "HELTEC_V1", "LILYGO_TBEAM_S3_CORE", "RAK11200", "NANO_G1", "TLORA_V2_1_1P8", "STATION_G1", "LORA_RELAY_V1", "NRF52840DK", "PPR", "GENIEBLOCKS", "NRF52_UNKNOWN", "PORTDUINO", "ANDROID_SIM", "DIY_V1", "NRF52840_PCA10059", "DR_DEV", "M5STACK", "PRIVATE_HW")

def tohex(val, nbits):
  return hex((val + (1 << nbits)) % (1 << nbits))

def computePacketRate(db, c, nodeID, ts):
    logger.info("%s - Node %s: processing packetRate" % (datetime.now(), nodeID, ))
    bufferLength = 20
    query = ("SELECT * FROM packetRates WHERE id=\"%s\"" % (nodeID, ))
    c.execute(query)
    data = c.fetchall()
    logger.debug("%s - Node %s: packetRatesData %s" % (datetime.now(), nodeID, data ))
    if len(data)<=0:
        logger.warning("%s - Node %s WARNING: packet rate not available, adding to DB" % (datetime.now(), nodeID, ))
        query = ("INSERT INTO packetRates (id, packetRateTS) VALUES (\"%s\", \"{\\\"ts\\\":[]}\")" % (nodeID,  ))
        c.execute(query)
        db.commit()
        return 0, 0
    logger.debug("%s - Node %s: loading json %s" % (datetime.now(), nodeID, data[0]["packetRateTS"] ))
    pTS = json.loads(data[0]["packetRateTS"])
    logger.debug("%s - Node %s: len->%s pTS->%s" % (datetime.now(), nodeID, len(pTS["ts"]), pTS))
    logger.debug("%s - Node %s: adding TS->%s" % (datetime.now(), nodeID, ts))
    pTS["ts"].append(ts)
    if len(pTS["ts"]) > bufferLength:
        popped = pTS["ts"].pop(0)
        logger.debug("%s - Node %s: removing TS->%s" % (datetime.now(), nodeID, popped))
    elif len(pTS["ts"])==0:
        logger.warning("%s - %s WARNING: packet rate timestamps empty" % (datetime.now(), nodeID, ))
        return 0, 0
    a = np.array(pTS["ts"])
    adiff = np.diff(a)
    logger.debug("%s - Node %s: timeDiffs %s" % (datetime.now(), nodeID, adiff ))
    packetRate = np.average(adiff)
    if np.isnan(packetRate):
        packetRate = 0
    packetRate = int(packetRate)
    query = ("UPDATE packetRates SET packetRateTS='%s', packetRate=%s WHERE id=\"%s\"" % (json.dumps(pTS), packetRate, nodeID, ))
    c.execute(query)
    db.commit()
    return packetRate, int(3600/packetRate)

def updateQuery(db, c, table, field, value, id):
    try:
        query = ("UPDATE %s SET %s=%s WHERE id=\"%s\""
                 % (table, field, value, id))
        c.execute(query)
        db.commit()
    except Exception as e:
        logger.error("%s ERROR: %s" % (datetime.now(), e, ))

def packetIsValid(db, c, nodeID, packetID, timestamp, sender):
    historyLimit = 1800
    try:
        query = ("DELETE FROM packetIdHistory WHERE timestamp<%s" % (int(time.time()) - historyLimit))
        c.execute(query)
        db.commit()
    except Exception as e:
        logger.error("%s ERROR: %s" % (datetime.now(), e, ))
    try:
        query = ("SELECT * FROM packetIdHistory WHERE nodeID=\"%s\" AND packetID=%s" % (nodeID, packetID))
        c.execute(query)
        data = c.fetchall()
        if len(data)>0:
            logger.debug("%s - Node %s: Packet %s reported by %s allready processed" % (datetime.now(), nodeID, packetID, sender))
            return False
        else:
            query = ("INSERT INTO packetIdHistory (nodeID, packetID, timestamp) VALUES (\"%s\", %s, %s)"
                     % (nodeID, packetID, timestamp))
            c.execute(query)
            db.commit()
            return True
    except Exception as e:
        logger.error("ERROR checking %s for Node %s: %s" % (packetID, nodeID, e, ))
        return False

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    logger.info("%s - Connected with result code %s" % (datetime.now(), str(rc), ))
    client.subscribe("msh/2/json/LongFast/#")

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    rxTime = int(time.time())
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        db=MySQLdb.connect(config['MYSQL']['host'], config['MYSQL']['username'], config['MYSQL']['password'], config['MYSQL']['database'])
        c=db.cursor(MySQLdb.cursors.DictCursor)

        nodeID=str(tohex(payload["from"], 32))
        nodeID=nodeID[2:len(nodeID)]
        for i in range(0, 8-len(nodeID)):
            nodeID = "0"+nodeID
        nodeID="!"+nodeID

        query = ("SELECT * FROM meshNodes where id=\"%s\"" % (nodeID, ))
        c.execute(query)
        data = c.fetchall()

        query = ("SELECT * FROM packetRates where id=\"%s\"" % (nodeID, ))
        c.execute(query)
        dataPR = c.fetchall()
        if len(data) > 0:
            if not (packetIsValid(db, c, nodeID, payload["id"], payload["timestamp"], payload["sender"])):
                discardLogger.debug("%s - Node %s(%s):\n%s" % (datetime.now(), nodeID, data[0]["shortName"], payload))
                return
            msgDT = datetime.fromtimestamp(payload["timestamp"])
            if payload["type"] == "text":
                pubPayload="{\"timestamp\":\"%s\", \"message\":\"%s (%s) - %s\", \"type\":\"text\", \"id\":\"%s\", \"reporter\":\"%s\"}" % (msgDT, data[0]["longName"], nodeID, payload["payload"]["text"], payload["id"], payload["sender"])
            else:
                pubPayload="{\"timestamp\":\"%s\", \"message\":\"Received %s frame from %s (%s)\", \"type\":\"info\", \"id\":\"%s\", \"reporter\":\"%s\"}" % (msgDT, payload["type"], data[0]["longName"], nodeID, payload["id"], payload["sender"])
            logger.info("%s - Node %s(%s): processing %s packet %s received from %s" 
                     % (datetime.now(), nodeID, data[0]["shortName"], payload["type"], payload["id"], payload["sender"]))
            logger.info("%s - Node %s(%s): packet DateTime %s" 
                     % (datetime.now(), nodeID, data[0]["shortName"], datetime.fromtimestamp(payload["timestamp"])))
            client.publish("msh/2/stat/updates", payload=pubPayload, qos=0, retain=False)
            mqttLogger.debug("%s - Node %s(%s):\n%s" % (datetime.now(), nodeID, data[0]["shortName"], payload))
            if payload["type"] == "position":
                try:
                    if "latitude_i" in payload["payload"]:
                        auxLat = payload["payload"]["latitude_i"]/10000000
                    else:
                        logger.info("%s - Node %s(%s): Latitude not available" % (datetime.now(), nodeID, data[0]["shortName"]))
                        auxLat = 0

                    if "longitude_i" in payload["payload"]:
                        auxLon = payload["payload"]["longitude_i"]/10000000
                    else:
                        logger.info("%s - Node %s(%s): Longitude not available" % (datetime.now(), nodeID, data[0]["shortName"]))
                        auxLon = 0

                    if auxLat != 0:
                        updateQuery(db, c, "meshNodes", "latitude", auxLat, nodeID)

                    if auxLon != 0:
                        updateQuery(db, c, "meshNodes", "longitude", auxLon, nodeID)

                    if "altitude" in payload["payload"]:
                        if payload["payload"]["altitude"] != 0:
                            updateQuery(db, c, "meshNodes", "altitude", payload["payload"]["altitude"], nodeID)
                        else:
                            logger.warning("%s - Node %s(%s): Altitude not available" % (datetime.now(), nodeID, data[0]["shortName"]))

                    updateQuery(db, c, "meshNodes", "positionTimestamp", payload["timestamp"], nodeID)
                    updateQuery(db, c, "meshNodes", "timestamp", payload["timestamp"], nodeID)
                    query = ("SELECT * from  nodesPositionHistory WHERE nodeID=\"%s\" ORDER BY timestamp DESC LIMIT 1"
                          % (nodeID,))
                    c.execute(query)
                    posData = c.fetchall()
                    dist = 100
                    if len(posData) > 0:
                        dist = distance.distance((posData[0]["latitude"], posData[0]["longitude"]),
                               (auxLat, auxLon)).km
                        if (auxLat == 0 or auxLon == 0):
                            logger.warning("%s - Node %s(%s): Position history update discarded, invalid position data lat:%s lon:%s" 
                                     % (datetime.now(), nodeID, data[0]["shortName"], auxLat, auxLon, ))
                            return
                    if dist > 0.25:
                        logger.info("%s - Node %s(%s): Position history updated lat: %s lon: %s" % (datetime.now(), nodeID, data[0]["shortName"], auxLat, auxLon))
                        query = ("INSERT INTO nodesPositionHistory (nodeID, latitude, longitude, timestamp) VALUES (\"%s\", %s, %s, %s)"
                              % (nodeID, auxLat, auxLon, payload["timestamp"],))
                        c.execute(query)
                        db.commit()
                    else:
                        logger.info("%s - Node %s(%s): Position history update discarded, distance < 0.25km (%s km)"
                                 % (datetime.now(), nodeID, data[0]["shortName"], dist, ))
                except Exception as e:
                    logger.error("%s ERROR: %s" % (datetime.now(), e, ))
            if payload["type"] == "nodeinfo":
                try:
                    query = ("UPDATE meshNodes SET longname=\"%s\", shortname=\"%s\", hardware=\"%s\" WHERE id=\"%s\"" 
                          % (payload["payload"]["longname"], payload["payload"]["shortname"], hwModels[payload["payload"]["hardware"]], nodeID))
                    c.execute(query)
                    db.commit()
                    updateQuery(db, c, "meshNodes", "timestamp", payload["timestamp"], nodeID)
                except Exception as e:
                    logger.error("%s ERROR: %s" % (datetime.now(), e, ))

            if payload["type"] == "telemetry":
                if "temperature" in payload["payload"]:
                    updateQuery(db, c, "meshNodes", "temperature", payload["payload"]["temperature"], nodeID)
                if "barometric_pressure" in payload["payload"]:
                    updateQuery(db, c, "meshNodes", "pressure", payload["payload"]["barometric_pressure"], nodeID)
                if "relative_humidity" in payload["payload"]:
                    updateQuery(db, c, "meshNodes", "humidity", payload["payload"]["relative_humidity"], nodeID)
                if "battery_level" in payload["payload"] and payload["payload"]["battery_level"] != 0:
                    updateQuery(db, c, "meshNodes", "batteryLevel", payload["payload"]["battery_level"], nodeID)
                if "voltage" in payload["payload"] and "air_util_tx" in payload["payload"]:
                    updateQuery(db, c, "meshNodes", "batteryVoltage", payload["payload"]["voltage"], nodeID)
                if "air_util_tx" in payload["payload"]:
                    updateQuery(db, c, "meshNodes", "airUtil", payload["payload"]["air_util_tx"], nodeID)
                if "channel_utilization" in payload["payload"]:
                    updateQuery(db, c, "meshNodes", "chUtil", payload["payload"]["channel_utilization"], nodeID)
                if "voltage" in payload["payload"] and not "air_util_tx" in payload["payload"]:
                    updateQuery(db, c, "meshNodes", "envVoltage", payload["payload"]["voltage"], nodeID)
                if "current" in payload["payload"]:
                    updateQuery(db, c, "meshNodes", "envCurrent", payload["payload"]["current"], nodeID)
                updateQuery(db, c, "meshNodes", "timestamp", payload["timestamp"], nodeID)


#            if dataPR[0]["packetRateTS"] != 0:
#                auxPR = rxTime - dataPR[0]["packetRateTS"] + dataPR[0]["packetRate"]
#                PR = auxPR/2 if dataPR[0]["packetRate"]!=0 else auxPR
#                updateQuery(db, c, "packetRates", "packetRate", PR, nodeID)
#                logger.info("%s - Node %s(%s): Packet Rate %ss"
#                         % (datetime.now(), nodeID, data[0]["shortName"], PR, ))
#            updateQuery(db, c, "packetRates", "packetRateTS", rxTime, nodeID)
            PR = computePacketRate(db, c, nodeID, int(time.time()))
            logger.info("%s - Node %s(%s): Packet Rate %s(s) / %s(p/h)"
                     % (datetime.now(), nodeID, data[0]["shortName"], PR[0], PR[1]))

        else:
            try:
                logger.info("###########################################################")
                logger.info("%s - Node %s: Insert into DB" % (datetime.now(), nodeID,))
                logger.info("###########################################################")
                query = ("INSERT INTO meshNodes (id, positionTimestamp,timestamp) VALUES (\"%s\", \"%s\", \"%s\")" % (nodeID, 0, payload["timestamp"],))
                c.execute(query)
                db.commit()
                query = ("INSERT INTO packetRates (nodeID) VALUES (\"%s\")" % (nodeID, ))
                c.execute(query)
                db.commit()
            except Exception as e:
                logger.error("%s ERROR: %s" % (datetime.now(), e, ))
        db.close()
    except Exception as e:
        logger.error("%s ERROR: %s" % (datetime.now(), e, ))

def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.username_pw_set(config['MQTT']['username'], config['MQTT']['password'])
    client.connect(config['MQTT']['host'], int(config['MQTT']['port']), 60)
    client.loop_forever()


if __name__ == '__main__':
    main()
