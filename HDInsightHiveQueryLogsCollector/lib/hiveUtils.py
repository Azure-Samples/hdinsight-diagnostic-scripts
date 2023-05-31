import logging
import datetime
from lib.utils import *

def executeHiveHql(self, hqlFile):
    params = "-n '' -p '' -f {hqlFile}".format(hqlFile = hqlFile)
    result = executeCommand("/usr/bin/hive", params)
    return result

def generateHiveSetV(self):
    executeHiveQuery(self, 'set -v', "setV.out") 

def executeHiveQuery(self, query, outputFileName):
    executeCommand("/usr/bin/hive", "--outputformat=csv2 -n '' -p '' -e '{query}' > ./results/output/{outputFileName}".format(query=query, outputFileName=outputFileName)) 

def executeQueryExplain(self, query):
    # find the query without use or set;
    statements = query.split(';')
    for s in statements:
        if s.startswith('use') or s.startswith('set'):
            continue
        else:
            s = "EXPLAIN {s}".format(s=s)
    
    explainQuery = ";".join(statements) 
    # replace newline with spaces;
    explainQuery = explainQuery.replace('\n', ' ')
    executeHiveQuery(self, explainQuery, "explainQuery.out")


    executeHiveQuery(self, '{query}' , "explainQuery.out") 