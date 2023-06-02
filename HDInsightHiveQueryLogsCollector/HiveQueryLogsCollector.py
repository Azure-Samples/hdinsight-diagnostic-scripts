import logging
import datetime
from lib.utils import *
from lib.hiveUtils import *



class HDInsightQueryLogsCollector:
# Globals
    scriptVersion = "0.0.1"
    verboseMode = False

    # Parameters dictionary
    params = {}
    logger = ""
    executionStartTime = ""
    executionEndTime = ""
    
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
        # currentFolder
        #   - results
        #       - logs
        #       - config
        #       - output
        createFolder(self, "results")
        createFolder(self, "logs", "./results")
        createFolder(self, "config", "./results")
        createFolder(self, "output", "./results")



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

        printAndLog(self, "Which Query Issue scenario you are facing? : ")
        printAndLog(self, '1 - Query Fails and never worked before (running for the first time)')
        which_validations = input()
        if which_validations == "":
            which_validations = "1"
        
        printAndLog(self, "Enter/Paste your Query. When done type EOF to terminate the query: ")
        while True:
            try:
                line = input()
                if line == "EOF":
                    break
                query = '\n'.join([query,line])
            except EOFError:
                break
        
        saveTextToFile(self, query, "./results/output/input_query.hql")

        # Execute the query
        printAndLog(self, "-------------------------------")
        printAndLog(self, "Executing the query ...")
        printAndLog(self, "-------------------------------")
        
        self.executionStartTime = datetime.datetime.now()
        result, appId = executeHiveHql(self, "./results/output/input_query.hql", "./results/output/query_result.out")
        saveTextToFile(self, result, "./results/output/query_beelinetrace.out")
        self.executionEndTime = datetime.datetime.now()

        printAndLog(self, "Execution Result:")
        printAndLog(self, result, logLevel="DEBUG")

        printAndLog(self, "-------------------------------")
        printAndLog(self, "Query execution completed.")
        printAndLog(self, "-------------------------------")
        printAndLog(self, "-------------------------------")
        printAndLog(self, "Getting Yarn Application Log ...")
        printAndLog(self, "-------------------------------")
        getYarnApplicationLog(self, appId)
        printAndLog(self, "-------------------------------")
        printAndLog(self, "Getting Yarn Application Log Completed.")
        printAndLog(self, "-------------------------------")
        printAndLog(self, "-------------------------------")
        printAndLog(self, "Executing set V command ...")
        printAndLog(self, "-------------------------------")
        generateHiveSetV(self)
        printAndLog(self, "-------------------------------")
        printAndLog(self, "Executing set V completed.")
        printAndLog(self, "-------------------------------")
        printAndLog(self, "-------------------------------")
        printAndLog(self, "Executing Explain Query ...")
        printAndLog(self, "-------------------------------")
        useStatement, queryWithoutUseSet, result = executeQueryExplain(self, query)
        printAndLog(self, "-------------------------------")
        printAndLog(self, "Executing Explain Query completed.")
        printAndLog(self, "-------------------------------")
        printAndLog(self, "-------------------------------")
        printAndLog(self, "Getting Tables Definition...")
        printAndLog(self, "-------------------------------")
        executeQueryTablesDefinition(self, useStatement, queryWithoutUseSet)
        printAndLog(self, "-------------------------------")
        printAndLog(self, "Getting Tables Definition completed.")
        printAndLog(self, "-------------------------------")

        
hnv = HDInsightQueryLogsCollector()
if len(sys.argv) > 1:
    if sys.argv[1] == "-v":
        # verbose mode
        hnv.verboseMode = True
hnv.main()
