import schedule
import time
import MySQLdb
import configparser
import os.path


configFile = '/etc/iMeshBackend/iMeshBackend.conf'

if not os.path.isfile(configFile):
    print("Config file not found (/etc/iMeshBackend/iMeshBackend.conf)")
    exit()

config = configparser.ConfigParser()
config.read(configFile)


def dbClean():
    db=MySQLdb.connect(config['MYSQL']['host'], config['MYSQL']['username'], config['MYSQL']['password'], config['MYSQL']['database'])
    c=db.cursor(MySQLdb.cursors.DictCursor)
    ts=int(time.time())-86400
    query = ("DELETE FROM meshNodes where timestamp<%s" % (ts, ))
    print(query)
    c.execute(query)

schedule.every(1).hours.do(dbClean)
dbClean()
while True:
    schedule.run_pending()
    time.sleep(1)

