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
    #executeCommand("/usr/bin/hive", "--outputformat=csv2 -n '' -p '' -e '{query}' > ./results/output/{outputFileName}".format(query=query, outputFileName=outputFileName)) 
    executeCommand("/usr/bin/hive", "-n '' -p '' -e '{query}'".format(query=query))

def executeQueryExplain(self, query):
    # find the query without use or set;
    statements = query.split(';')
    for s in statements:
        if s.startswith('use') or s.startswith('set'):
            explainQuery = ";".join(explainQuery, s) 
            continue
        else:
            explain = "EXPLAIN {s}".format(s=s)
            explainQuery = ";".join(explainQuery, explain) 

    explainQuery = ";".join(statements) 
    # replace newline with spaces;
    explainQuery = explainQuery.replace('\n', ' ')
    printAndLog(self, "Explain Query: {explainQuery}".format(explainQuery=explainQuery))
    executeHiveQuery(self, explainQuery, "explainQuery.out")