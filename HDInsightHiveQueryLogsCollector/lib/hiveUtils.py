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
    explainQuery = ""
    # find the query without use or set;
    query = query.replace('\n', ' ')
    print(f"query: {query}")

    statements = query.split(';')
    for s in statements:
        print(f"Statement: {s}")
        if s.lower().startswith('use') or s.lower().startswith('set'):
            explainQuery = ";".join(explainQuery, s) 
            print(f"explainQuery: {explainQuery}")
            continue
        else:
            explain = f"EXPLAIN {s}"
            print(f"explain: {explain}")
            explainQuery = ";".join([explainQuery, explain])
            print(f"explainQuery final after join: {explainQuery}") 

    # replace newline with spaces;
    printAndLog(self, "Explain Query: {explainQuery}".format(explainQuery=explainQuery))
    executeHiveQuery(self, explainQuery, "explainQuery.out")