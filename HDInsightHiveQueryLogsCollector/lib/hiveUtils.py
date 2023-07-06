from sql_metadata import Parser
from lib.utils import *
import re
import pysftp


def executeHiveHql(self, hqlFile, outputfileName, getApplicationId = False):
    if (self.llapRunningStatus == "NAN"):
        self.hiveInteractiveJDBCUrl = getHiveInteractiveJDBCUrl(self)

    if self.hiveInteractiveJDBCUrl == "":
        command = "/usr/bin/hive"
        params = f"-n '' -p '' -f {hqlFile} > {outputfileName}"
    else:
        command = "/usr/bin/beeline"
        params = f"-u '{self.hiveInteractiveJDBCUrl}' -n '' -p '' -f {hqlFile} > {outputfileName}"

    applicationId = ""
    result = executeCommand(command, params)

    if getApplicationId:
        applicationId = re.search("application_[0-9]{13}_[0-9]{4}", result)
        if applicationId is None:
            printAndLog(self, "Application Id not found in the result.", logLevel="ERROR")
            return result, ""

        return result, applicationId.group()
    else:
        return result, ""
    
def generateHiveSetV(self):
    executeHiveQuery(self, 'set -v', "setV.out") 

def executeHiveQuery(self, query, outputFileName):
    if (self.llapRunningStatus == "NAN"):
        self.hiveInteractiveJDBCUrl = getHiveInteractiveJDBCUrl(self)
    

    if self.hiveInteractiveJDBCUrl == "":
        printAndLog(self, "Hive Interactive JDBC URL not found, using default jdbc url", logLevel="DEBUG")
        command = "/usr/bin/hive"
        params = f"--outputformat=csv2 -n '' -p '' -e '{query}' > {self.outputFolder}/{outputFileName}"
    else:
        printAndLog(self, "Hive Interactive JDBC URL found, using it to connect to LLAP", "DEBUG")
        command = "/usr/bin/beeline"
        params = f"-u '{self.hiveInteractiveJDBCUrl}' --outputformat=csv2 -n '' -p '' -e '{query}' > {self.outputFolder}/{outputFileName}"

    executeCommand(command, params) 

def executeQueryExplain(self, query):
    queryWithoutUseSet = ""
    explainQuery = ""
    useStatement = ""
    # find the query without use or set;
    query = query.replace('\n', ' ')

    statements = query.split(';')
    for s in statements:
        if s.lower().strip().startswith('use'):
            useStatement = s.strip()
            explainQuery = ";".join([explainQuery, s.strip()]) 
            continue
        elif s.lower().strip().startswith('set'):
            explainQuery = ";".join([explainQuery, s.strip()]) 
            continue
        elif s.strip() =="":
            continue
        else:
            queryWithoutUseSet = s.strip()
            explain = f"EXPLAIN {queryWithoutUseSet}"
            explainQuery = ";".join([explainQuery, explain])
            explainQuery = f"{explainQuery};"

    # replace newline with spaces;
    saveTextToFile(self, explainQuery, f"{self.outputFolder}/explain_query.hql")
    result, appId = executeHiveHql(self, f"{self.outputFolder}/explain_query.hql", f"{self.outputFolder}/explain_query_result.out")
    saveTextToFile(self, result, f"{self.outputFolder}/explain_query_beelinetrace.out")

    return useStatement, queryWithoutUseSet, result

def executeQueryTablesDefinition(self, useStatement, queryWithoutUseSet):
    tables = Parser(queryWithoutUseSet).tables
    for table in tables:
        if table == "":
            continue
        table = table.replace("`", "")
        query = f"DESCRIBE FORMATTED {table}"
        if useStatement != "":
            query = f"{useStatement};{query}"
        
        saveTextToFile(self, query, f"{self.outputFolder}/{table}_definition.hql")
        result, appId = executeHiveHql(self, f"{self.outputFolder}/{table}_definition.hql",f"{self.outputFolder}/{table}_dfinition.out")
        saveTextToFile(self, result, f"{self.outputFolder}/{table}_definition_beelinetrace.out")


def getYarnApplicationLog(self, appId, prefix=""):
    executeCommand("/usr/bin/yarn", f"logs -applicationId {appId} > {self.logsFolder}/{prefix}{appId}.log")

def getHiveLogs(self, username, password, host):
    createFolder(self, f"{self.logsFolder}/{host}")
    cnopts = pysftp.CnOpts()
    cnopts.hostkeys = None
    sftp = pysftp.Connection(self.hn0, username=username, password=password, cnopts= cnopts)
    if sftp.isfile('/var/log/hive/hiveserver2.log'):
        printAndLog(self, f"Getting file: /var/log/hive/hiveserver2.log from {host}")
        sftp.get('/var/log/hive/hiveserver2.log', f'{self.logsFolder}/{host}/hiveserver2.log')

    if sftp.isfile('/var/log/hive/hivemetastore.log'):
        printAndLog(self, f"Getting file: /var/log/hive/hivemetastore.log from {host}")
        sftp.get('/var/log/hive/hivemetastore.log', f'{self.logsFolder}/{host}/hivemetastore.log')

    if sftp.isfile('/var/log/hive/hiveserver2Interactive.log'):
        printAndLog(self, f"Getting file: /var/log/hive/hiveserver2Interactive.log from {host}")
        sftp.get('/var/log/hive/hiveserver2Interactive.log', f'{self.logsFolder}/{host}/hiveserver2Interactive.log')

    sftp.close()   


def GetLlapDetails(self):

    yarnApplicationList_out = f"{self.outputFolder}/yarnApplicationList.out"
    result = executeCommand("/usr/bin/yarn", f"application -list -appTypes yarn-service -appStates RUNNING > {yarnApplicationList_out}")

    f = open(yarnApplicationList_out,'r')
    file_content = f.read()
    f.close()

    printAndLog(self, f"content of file  {yarnApplicationList_out}: " + file_content , logLevel="DEBUG")
    if "llap0" in file_content:
        return True, GetLlapAppId(self,file_content)
    else:
        return False, ""


def GetLlapAppId(self, result):
    appId = ""
    for line in result.splitlines():
        printAndLog(self, "line: " + line, logLevel="DEBUG")
        if "llap0" in line:

            appId = line.split()[0]
            break
    return appId