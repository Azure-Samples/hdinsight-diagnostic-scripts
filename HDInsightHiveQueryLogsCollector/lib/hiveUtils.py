import logging
import datetime
from utils import *

def executeHiveHql(self, hqlFile):
    params = "-n '' -p '' -f {hqlFile}".format(hqlFile)
    result = executeCommand("/usr/bin/hive", params)
    return result

def generateHiveSetV(self):
    executeCommand("/usr/bin/hive", "--outputformat=csv2 -n '' -p '' -e 'set -v' > ./results/output/setV.out") 