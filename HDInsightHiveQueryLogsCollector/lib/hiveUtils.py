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
    
    logFilename = "hiveserver2Interactive"
    command = f"find /var/log/hive//{logFilename}.log* -newermt '{self.executionStartTime}' -type f"
    printAndLog(self, f"Executing command: {command} on {host}")
    result = sftp.execute(command)
    printAndLog(self, f"Result: {result}")
    error_messages = [line.decode().rstrip() for line in result if line.startswith(b'find:')]
    if error_messages:
        printAndLog(self, "Error occurred while running the find command:")
        for error in error_messages:
            printAndLog(self,error)
    else:
        # copy the list of file names
        for file_path_bytes in result:
            file_path = file_path_bytes.decode().rstrip()
            if sftp.isfile(file_path):
                printAndLog(self, f"Getting file: {file_path} from {host}")
                file_name = os.path.basename(file_path)
                sftp.get(file_path, f'{self.logsFolder}/{host}/{file_name}')
    
    logFilename = "hivemetastore"
    command = f"find /var/log/hive//{logFilename}.log* -newermt '{self.executionStartTime}' -type f"
    printAndLog(self, f"Executing command: {command} on {host}")
    result = sftp.execute(command)
    printAndLog(self, f"Result: {result}")

    error_messages = [line.decode().rstrip() for line in result if line.startswith(b'find:')]
    if error_messages:
        printAndLog(self, "Error occurred while running the find command:")
        for error in error_messages:
            printAndLog(self,error)
    else:
        # copy the list of file names
        for file_path_bytes in result:
            file_path = file_path_bytes.decode().rstrip()
            if sftp.isfile(file_path):
                printAndLog(self, f"Getting file: {file_path} from {host}")
                file_name = os.path.basename(file_path)
                sftp.get(file_path, f'{self.logsFolder}/{host}/{file_name}')

    
    logFilename = "hiveserver2"
    command = f"find /var/log/hive//{logFilename}.log* -newermt '{self.executionStartTime}' -type f"
    printAndLog(self, f"Executing command: {command} on {host}")
    result = sftp.execute(command)
    printAndLog(self, f"Result: {result}")
    error_messages = [line.decode().rstrip() for line in result if line.startswith(b'find:')]
    if error_messages:
        printAndLog(self, "Error occurred while running the find command:")
        for error in error_messages:
            printAndLog(self,error)
    else:
        # copy the list of file names
        for file_path_bytes in result:
            file_path = file_path_bytes.decode().rstrip()
            if sftp.isfile(file_path):
                printAndLog(self, f"Getting file: {file_path} from {host}")
                file_name = os.path.basename(file_path)
                sftp.get(file_path, f'{self.logsFolder}/{host}/{file_name}')et(file_path, f'{self.logsFolder}/{host}/{file_name}')

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