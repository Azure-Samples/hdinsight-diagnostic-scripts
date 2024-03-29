import logging
from datetime import datetime
from lib.utils import *
from lib.hiveUtils import *
import pwinput

class HDInsightQueryLogsCollector:
# Globals
    scriptVersion = "0.0.1"
    verboseMode = False

    # Parameters dictionary
    params = {}
    logger = ""
    executionStartTime = ""
    executionEndTime = ""
    hiveInteractiveJDBCUrl = ""
    llapRunningStatus = "NAN"
    resultSetFoldername = ""
    outputFolder = ""
    logsFolder = ""

    def initializeLogger(self):
        """Initialize and return the logger object"""
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)

        fh = logging.FileHandler("logfile.log", "a")
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s,%(msecs)d %(name)s %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        return logger

    def createFolderStructure(self):
        #TODO: Add timestamp to results folder
        #TODO: Add Folder Paths to vars
        # currentFolder
        #   - results
        #       - logs
        #       - config
        #       - output
        self.resultSetFoldername = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        createFolder(self, "results")
        createFolder(self, self.resultSetFoldername, "./results")
        createFolder(self, "logs", f"./results/{self.resultSetFoldername}")
        createFolder(self, "output", f"./results/{self.resultSetFoldername}")
        self.outputFolder = f"./results/{self.resultSetFoldername}/output"
        self.logsFolder = f"./results/{self.resultSetFoldername}/logs"



    def main(self):
        query = ""
        self.createFolderStructure()
           # Initialize logger
        self.logger = initializeLogger(self)
        self.logger.info("------------------------------------------------------------------------------")

        # Print banner
        printAndLog(self, Fore.YELLOW + "==================================")
        printAndLog(self, Fore.YELLOW + "HDInsight Hive Query Logs Collector  v" + self.scriptVersion)
        printAndLog(self, Fore.YELLOW + "==================================")

        # Print if user used -v (verbose mode) switch
        if self.verboseMode:
            printAndLog(self, "Verbose mode: " + Fore.GREEN + "On" + Style.RESET_ALL)
        else:
            printAndLog(self, "Verbose mode: " + Fore.GREEN + "Off" + Style.RESET_ALL)

        # Select the Scenario that is failing
        # --------MAIN MENU---------------
        which_validations = ""

        #printAndLog(self, "Which Query Issue scenario you are facing? : ")
        #printAndLog(self, '1 - Query Fails and never worked before (running for the first time)')
        #which_validations = input()
        #if which_validations == "":
        #    which_validations = "1"
        username = input("What is your ssh username?")

        password1 = pwinput.pwinput("What is your ssh password?", mask='*')
        password2 = pwinput.pwinput("Repeat your ssh password?", mask='*')

        if password1 != password2:
            printAndLog(self, Fore.RED + "Passwords do not match. Exiting...")
            sys.exit(1)

        #Get etc/hosts file
        self.hn0, self.hn1 = getHeadnodesHostnames(self)
        printAndLog(self, "hn0: " + self.hn0, logLevel="DEBUG")
        printAndLog(self, "hn1: " + self.hn1, logLevel="DEBUG")

        printAndLog(self, "Enter/Paste your Query. When done type EOF to terminate the query: ")
        while True:
            try:
                line = input()
                if line == "EOF":
                    break
                query = '\n'.join([query,line])
            except EOFError:
                break
        
        saveTextToFile(self, query, f"{self.outputFolder}/input_query.hql")

        # Execute the query
        printAndLog(self, Fore.GREEN + "-------------------------------")
        printAndLog(self, Fore.GREEN + "Executing the query ...")
        printAndLog(self, Fore.GREEN + "-------------------------------")
        
        self.executionStartTime = datetime.now()
        result, appId = executeHiveHql(self, f"{self.outputFolder}/input_query.hql", f"{self.outputFolder}/query_result.out", getApplicationId=True)
        saveTextToFile(self, result, f"{self.outputFolder}/query_beelinetrace.out")
        self.executionEndTime = datetime.now()
        printAndLog(self, Fore.RED + f"Execution started at: {self.executionStartTime} and finished on: {self.executionEndTime} and it took {self.executionEndTime - self.executionStartTime}")

        printAndLog(self, "Execution Result:")
        printAndLog(self, result, logLevel="DEBUG")

        printAndLog(self, Fore.GREEN + "-------------------------------")
        printAndLog(self, Fore.GREEN + "Query execution completed.")
        printAndLog(self, Fore.GREEN + "-------------------------------")
        printAndLog(self, Fore.GREEN + "-------------------------------")
        printAndLog(self, Fore.GREEN + f"Getting Yarn Application Log for {appId} ...")
        printAndLog(self, Fore.GREEN + "-------------------------------")
        getYarnApplicationLog(self, appId)
        printAndLog(self, Fore.GREEN + "-------------------------------")
        printAndLog(self, Fore.GREEN + "Getting Yarn Application Log Completed.")
        printAndLog(self, Fore.GREEN + "-------------------------------")
        # check if LLAP is running
        isLlapRunning, llapAppId = GetLlapDetails(self)
        printAndLog(self, Fore.YELLOW + "LLAP Running: " + Fore.GREEN + str(isLlapRunning))
        if isLlapRunning:
            printAndLog(self, Fore.GREEN + f"Getting Yarn Application Log for llap ...")
            printAndLog(self, Fore.GREEN + "-------------------------------")
            getYarnApplicationLog(self, llapAppId, "llap_")
            printAndLog(self, Fore.GREEN + "-------------------------------")
            printAndLog(self, Fore.GREEN + "Getting Yarn Application Log for llap Completed.")
            printAndLog(self, Fore.GREEN + "-------------------------------")
        
        printAndLog(self, Fore.GREEN + "-------------------------------")
        printAndLog(self, Fore.GREEN + "Executing set V command ...")
        printAndLog(self, Fore.GREEN + "-------------------------------")
        generateHiveSetV(self)
        printAndLog(self, Fore.GREEN + "-------------------------------")
        printAndLog(self, Fore.GREEN + "Executing set V completed.")
        printAndLog(self, Fore.GREEN + "-------------------------------")
        printAndLog(self, Fore.GREEN + "-------------------------------")
        printAndLog(self, Fore.GREEN + "Executing Explain Query ...")
        printAndLog(self, Fore.GREEN + "-------------------------------")
        useStatement, queryWithoutUseSet, result = executeQueryExplain(self, query)
        printAndLog(self, Fore.GREEN + "-------------------------------")
        printAndLog(self, Fore.GREEN + "Executing Explain Query completed.")
        printAndLog(self, Fore.GREEN + "-------------------------------")
        printAndLog(self, Fore.GREEN + "-------------------------------")
        printAndLog(self, Fore.GREEN + "Getting Tables Definition...")
        printAndLog(self, Fore.GREEN + "-------------------------------")
        executeQueryTablesDefinition(self, useStatement, queryWithoutUseSet)
        printAndLog(self, Fore.GREEN + "-------------------------------")
        printAndLog(self, Fore.GREEN + "Getting Tables Definition completed.")
        printAndLog(self, Fore.GREEN + "-------------------------------")
        
        #Collect HiveSerevr2 logs
        #Collect HiveInteractiveServer logs
        #Collect Hive Metatsore logs
        printAndLog(self, Fore.GREEN + "-------------------------------")
        printAndLog(self, Fore.GREEN + "Getting Hive Server 2/Hive Metastore and Hive Interactive logs from both headnodes.")
        printAndLog(self, Fore.GREEN + "-------------------------------")
        
            
        getHiveLogs (self, username= username, password=password1, host=self.hn0) # close your connection to hostname
        getHiveLogs (self, username= username, password=password1, host=self.hn1) # close your connection to hostname

        #Compress results and display link to compressed file
        CompressFolder(self, f"./results/{self.resultSetFoldername}", f"./results_{self.resultSetFoldername}.zip")

        printAndLog(self, Fore.GREEN + "-------------------------------")    
        printAndLog(self, Fore.GREEN + f"Results are saved as ./results_{self.resultSetFoldername}.zip")
        printAndLog(self, Fore.GREEN + "-------------------------------")
        
hnv = HDInsightQueryLogsCollector()
if len(sys.argv) > 1:
    if sys.argv[1] == "-v":
        # verbose mode
        hnv.verboseMode = True
hnv.main()
