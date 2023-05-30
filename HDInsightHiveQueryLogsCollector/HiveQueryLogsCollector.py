import logging
from lib.utils import *
import keyboard


class HDInsightQueryLogsCollector:
# Globals
    scriptVersion = "0.0.1"
    verboseMode = False

    # Parameters dictionary
    params = {}
    logger = ""
    
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
        query = ""
        # if self.verboseMode:
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
        
        saveTextToFile(self, query, "./results/output/query.hql")

        # Execute the query
        printAndLog(self, "-------------------------------")
        printAndLog(self, "Executing the query ...")
        printAndLog(self, "-------------------------------")
        
        result = executeCommand("usr/bin/hive", "-n '' -p '' -f ./results/output/query.hql")
        saveTextToFile(self, result, "./results/output/query_result.txt")
        printAndLog(self, "-------------------------------")
        printAndLog(self, "Query execution completed.")
        printAndLog(self, "-------------------------------")

hnv = HDInsightQueryLogsCollector()
if len(sys.argv) > 1:
    if sys.argv[1] == "-v":
        # verbose mode
        hnv.verboseMode = True
hnv.main()
