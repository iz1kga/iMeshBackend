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
import re

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

hwModels = { 0:"UNSET",
             1:"TLORA_V2",
             2:"TLORA_V1",
             3:"TLORA_V2_1_1P6",
             4:"TBEAM",
             5:"HELTEC_V2_0",
             6:"TBEAM_V0P7",
             7:"T_ECHO",
             8:"TLORA_V1_1P3",
             9:"RAK4631",
             10:"HELTEC_V2_1",
             11:"HELTEC_V1",
             12:"LILYGO_TBEAM_S3_CORE",
             13:"RAK11200",
             14:"NANO_G1",
             15:"TLORA_V2_1_1P8",
             16:"TLORA_T3_S3",
             17:"NANO_G1_EXPLORER",
             25:"STATION_G1",
             32:"LORA_RELAY_V1",
             33:"NRF52840DK",
             34:"PPR",
             35:"GENIEBLOCKS",
             36:"NRF52_UNKNOWN",
             37:"PORTDUINO",
             39:"DIY_V1",
             40:"NRF52840_PCA10059",
             41:"DR_DEV",
             42:"M5STACK",
             43:"HELTEC_V3",
             44:"HELTEC_WSL_V3",
             45:"BETAFPV_2400_TX",
             46:"BETAFPV_900_NANO_TX",
             255:"PRIVATE_HW"
           }



("UNSET", "TLORA_V2", "TLORA_V1", "TLORA_V2_1_1P6",
            "TBEAM", "HELTEC_V2_0", "TBEAM_V0P7", "T_ECHO",
            "TLORA_V1_1P3", "RAK4631", "HELTEC_V2_1", "HELTEC_V1",
            "LILYGO_TBEAM_S3_CORE", "RAK11200", "NANO_G1", "TLORA_V2_1_1P8", 
            "STATION_G1", "LORA_RELAY_V1", "NRF52840DK", "PPR", "GENIEBLOCKS", 
            "NRF52_UNKNOWN", "PORTDUINO", "ANDROID_SIM", "DIY_V1", "NRF52840_PCA10059", 
            "DR_DEV", "M5STACK", "PRIVATE_HW")

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
        if type(value) == str:
            value = "'"+value+"'"
        query = ("UPDATE %s SET %s=%s WHERE id=\"%s\""
                 % (table, field, value, id))
        c.execute(query)
        db.commit()
    except Exception as e:
        logger.error("%s ERROR: %s" % (datetime.now(), e, ))

def getNodeName(db, c, id):
    query = ("SELECT longName FROM meshNodes where id=\"%s\"" % (id, ))
    c.execute(query)
    data = c.fetchall()
    return str(data[0]['longName'])

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
#    client.subscribe("msh/2/json/LongFast/#")
#    client.subscribe("msh/2/json/MediumFast/#")
    client.subscribe("msh/decoded/data")

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    rxTime = int(time.time())
    try:
        payload = json.loads(msg.payload.decode("utf-8"))

        nodeID = payload['from']
        channel = payload['channel']

        db=MySQLdb.connect(config['MYSQL']['host'], config['MYSQL']['username'], config['MYSQL']['password'], config['MYSQL']['database'])
        c=db.cursor(MySQLdb.cursors.DictCursor)

        query = ("SELECT * FROM meshNodes where id=\"%s\"" % (nodeID, ))
        c.execute(query)
        data = c.fetchall()

        query = ("SELECT * FROM packetRates where id=\"%s\"" % (nodeID, ))
        c.execute(query)
        dataPR = c.fetchall()
        if len(data) > 0:
            if not (packetIsValid(db, c, nodeID, payload["id"], payload["rxTime"], payload["sender"])):
                discardLogger.debug("%s - Node %s(%s):\n%s" % (datetime.now(), nodeID, data[0]["shortName"], payload))
                return
            msgDT = datetime.fromtimestamp(payload["rxTime"])
            if payload["type"] == "text":
                pubPayload="{\"timestamp\":\"%s\", \"message\":\"%s (%s) - %s\", \"type\":\"text\", \"id\":\"%s\", \"reporter\":\"%s\"}" % (msgDT, data[0]["longName"], nodeID, payload["payload"]["text"], payload["id"], payload["sender"])
            else:
                pubPayload="{\"timestamp\":\"%s\", \"message\":\"Received %s frame from %s (%s)\", \"type\":\"info\", \"id\":\"%s\", \"reporter\":\"%s (%s)\"}" % (msgDT, payload["type"], data[0]["longName"], nodeID, payload["id"], payload["sender"], getNodeName(db, c, payload["sender"]))
            logger.info("%s - Node %s(%s): processing %s packet %s received from %s" 
                     % (datetime.now(), nodeID, data[0]["shortName"], payload["type"], payload["id"], payload["sender"]))
            logger.info("%s - Node %s(%s): packet DateTime %s" 
                     % (datetime.now(), nodeID, data[0]["shortName"], datetime.fromtimestamp(payload["rxTime"])))
            client.publish("msh/2/stat/updates", payload=pubPayload, qos=0, retain=False)
            mqttLogger.debug("%s - Node %s(%s):\n%s" % (datetime.now(), nodeID, data[0]["shortName"], payload))
            if payload["type"] == "position":
                try:
                    if "latitudeI" in payload["payload"]:
                        auxLat = payload["payload"]["latitudeI"]/10000000
                    else:
                        logger.info("%s - Node %s(%s): Latitude not available" % (datetime.now(), nodeID, data[0]["shortName"]))
                        auxLat = 0

                    if "longitudeI" in payload["payload"]:
                        auxLon = payload["payload"]["longitudeI"]/10000000
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

                    updateQuery(db, c, "meshNodes", "positionTimestamp", payload["rxTime"], nodeID)
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
                              % (nodeID, auxLat, auxLon, payload["rxTime"],))
                        c.execute(query)
                        db.commit()
                    else:
                        logger.info("%s - Node %s(%s): Position history update discarded, distance < 0.25km (%s km)"
                                 % (datetime.now(), nodeID, data[0]["shortName"], dist, ))
                except Exception as e:
                    logger.error("%s ERROR: %s" % (datetime.now(), e, ))
            if payload["type"] == "nodeinfo":
               nodeName = payload["payload"]["longName"].replace("_", " ")
               logger.info("%s - Node %s(%s): received node name -> %s"
                           % (datetime.now(), nodeID, data[0]["shortName"], nodeName, ))
               matches = re.search("([A-Za-z0-9-\\\/]+\s?)(GW\s)?(433\s?|868\s?)?([A-Fa-f0-9]{4})?", nodeName)
               logger.debug("%s - Node %s(%s): matches -> %s"
                            % (datetime.now(), nodeID, data[0]["shortName"], matches, ))
               try:
                   longName = matches[1].strip(" ")
                   logger.debug("%s - Node %s(%s): matched name -> %s"
                                % (datetime.now(), nodeID, data[0]["shortName"], longName, ))
               except Exception as e:
                   longName = nodeName
                   logger.error("%s ERROR: can't match %s -> %s" % (datetime.now(), nodeName, e, ))
               if matches[4] != None:
                   longName = longName + "_" + matches[4].strip(" ")
               try:
                   if matches[2].strip(" ") == "GW":
                       logger.info("%s - Node %s(%s): set as Router" % (datetime.now(), nodeID, data[0]["shortName"]))
                       updateQuery(db, c, "meshNodes", "isRouter", 2, nodeID)
               except Exception as e:
                   logger.error("%s ERROR GW Match: %s" % (datetime.now(), e, ))
               try:
                   if matches[3].strip(" ") != None:
                       logger.info("%s - Node %s(%s): set qrg %s" % (datetime.now(), nodeID, data[0]["shortName"], matches[3].strip(" ")))
                       updateQuery(db, c, "meshNodes", "qrg", matches[3].strip(" "), nodeID)
               except Exception as e:
                   logger.error("%s ERROR QRG match: %s" % (datetime.now(), e, ))
               try:
                    updateQuery(db, c, "meshNodes", "longName", longName, nodeID)
                    updateQuery(db, c, "meshNodes", "shortname", payload["payload"]["shortName"], nodeID)
                    updateQuery(db, c, "meshNodes", "hardware", payload["payload"]["hwModel"].replace("_", " "), nodeID)
                    #updateQuery(db, c, "meshNodes", "timestamp", payload["rxTime"], nodeID)
               except Exception as e:
                    logger.error("%s ERROR Update DB nodeinfo: %s" % (datetime.now(), e, ))

            if payload["type"] == "telemetry" and False:
                deviceMetrics = payload["payload"]["deviceMetrics"]
                environmentMetrics = payload["payload"]["environmentMetrics"]

                for deviceMetricKey, deviceMetricValue in deviceMetrics.items():
                    try:
                        updateQuery(db, c, "meshNodes", deviceMetricKey, deviceMetricValue, nodeID)
                    except Excetpion as e:
                        logger.error("%s ERROR updating telemetry: %s" % (datetime.now(), e, ))

                for environmentMetricKey, environmentMetricValue in environmentMetrics.items():
                    try:
                        updateQuery(db, c, "meshNodes", environmentMetricKey, environmentMetricValue, nodeID)
                    except Excetpion as e:
                        logger.error("%s ERROR updating telemetry: %s" % (datetime.now(), e, ))

            #update Timestamp, SNR and RSSI
            updateQuery(db, c, "meshNodes", "timestamp", payload["rxTime"], nodeID)
            updateQuery(db, c, "meshNodes", "rxSnr", payload["rxSnr"], nodeID)
            updateQuery(db, c, "meshNodes", "rxRssi", payload["rxRssi"], nodeID)

            #update gwID and Sender (maybe always the same?)
            updateQuery(db, c, "meshNodes", "gwID", payload["gwID"], nodeID)
            updateQuery(db, c, "meshNodes", "sender", payload["sender"], nodeID)

            #Compute PacketRate
            PR = computePacketRate(db, c, nodeID, int(time.time()))
            logger.info("%s - Node %s(%s): Packet Rate %s(s) / %s(p/h)"
                     % (datetime.now(), nodeID, data[0]["shortName"], PR[0], PR[1]))
            updateQuery(db, c, "meshNodes", "channel", "\""+channel+"\"", nodeID)

        else:
            try:
                logger.info("###########################################################")
                logger.info("%s - Node %s: Insert into DB" % (datetime.now(), nodeID,))
                logger.info("###########################################################")
                query = ("INSERT INTO meshNodes (id, positionTimestamp,timestamp) VALUES (\"%s\", \"%s\", \"%s\")" % (nodeID, 0, payload["rxTime"],))
                c.execute(query)
                db.commit()
                query = ("INSERT INTO packetRates (id, packetRateTS) VALUES (\"%s\", \"{\\\"ts\\\":[]}\")" % (nodeID, ))
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
