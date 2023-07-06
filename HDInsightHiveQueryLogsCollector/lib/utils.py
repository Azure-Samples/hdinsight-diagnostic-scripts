import os
from os import path
import re
import sys
import logging
import logging.handlers
import subprocess
if sys.version_info >= (3, 7):
    import zipfile
else:
    import zipfile37 as zipfile

from progress.spinner import Spinner
from colorama import *
from halo import Halo

from xml.etree.ElementTree import *
import xml.etree.ElementTree as ET


def initializeLogger(self):
    """Initialize and return the logger object"""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    fh = logging.FileHandler("./results/logs/logfile.log", "a")
    fh.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s,%(msecs)d %(name)s %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    return logger

def getParamsFromConf(self):
    """Get the config details from params.conf file and returns it as a dictionary"""
    if not (path.exists("config/params.conf")):
        printAndLog(self, "ERROR: Cannot find  'params.conf' in the current folder", "WARN")
        sys.exit()

    ##Dictionary to store params
    params = {}
    f = open("config/params.conf", "r")
    for line in f:
        # Skip commented or empty lines
        if line.startswith("#") or line == "" or line == "\n":
            next
        else:
            tmpArr = line.split("=")
            tmpKey = tmpArr[0].strip()
            tmpValue = (tmpArr[1]).strip()

            # Remove \n if line ends with \n
            if tmpValue.endswith("\n"):
                tmpValue = tmpValue[0:-1]

            # strip the double quotes
            tmpValue = tmpValue[1:-1]

            params[tmpKey] = tmpValue
    f.close()
    return params

def executeCommand(cmdName, params="", showSpinner=True):
    """Executes the given cmdName command and returns its output"""
    myProc = subprocess.Popen(cmdName + " " + params, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    stdout, stderr = myProc.communicate()
    if len(str(stdout)) > len(str(stderr)):
        return stdout.decode()
    else:
        return stderr.decode()

def getHostName():
    """Get current VM's hostname by executing hostname command"""
    hostname = executeCommand("hostname", "", False)
    return hostname.strip()

def getHeadnodesHostnames(self):
    hosts_file = open("/etc/hosts", "r")
    hosts_content = hosts_file.read()
    hosts_file.close()
    #regex 
    hn_matches = re.findall("\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3}\s*(hn[02|01]-\w*)", hosts_content)
    if hn_matches is None:
        printAndLog(self,  "ERROR: Cannot find headnodes' hostnames in /etc/hosts file", "ERROR")
        return "", ""
    else:
        hn0 = hn_matches[0]
        hn1 = hn_matches[1]
    return hn0, hn1

def getHiveInteractiveJDBCUrl(self):
    """Get the Hive Interactive JDBC URL"""
    # Parse the XML file
    tree = ET.parse('/etc/hive/conf/beeline-site.xml')
    root = tree.getroot()

    # Find the property with name 'beeline.hs2.jdbc.url.llap'
    property_element = root.find(".//property[name='beeline.hs2.jdbc.url.llap']")

    # Get the value of the property
    if (property_element is None):
        return ""
    
    value = property_element.find('value').text
    if value is None:
        return ""
    
    printAndLog(self, f"Hive Interactive JDBC URL: {value}", "DEBUG")  

    return value


def printAndLog(self, msg, logLevel="INFO", end="x"):
    if msg != "\n":
        if end == " ":
            print(msg, end=" ")
        else:
            print(msg)

    # Clean the "colors" and "styles" from the text before logging
    msg = str(msg).replace("\x1b[36m", "").replace("\x1b[32m", "").replace("\x1b[33m", "").replace("\x1b[0m", "")

    if logLevel == "INFO":
        self.logger.info(msg)
    elif logLevel == "WARN":
        self.logger.warn(msg)
    elif logLevel == "DEBUG":
        self.logger.debug(msg)

def createFolder(self, folderName, path="./"):
    folder_path = '/'.join([path, folderName])
    try:
        if not os.path.exists(folder_path):
            os.mkdir(folder_path)
        else:
            print(f"The folder '{folder_path}' already exists.")
    except OSError as e:
            print(f"An error occurred while creating the folder: {e}")

def saveTextToFile(self, text, file_path):
    with open(file_path, 'w') as file:
        file.write(text)  # Write the text to the file

def CompressFolder(self, folderPath, zipFilePath):
    """Compress the given folder into a zip file"""
    try:
        zipf = zipfile.ZipFile(zipFilePath, 'w', zipfile.ZIP_DEFLATED)
        for root, dirs, files in os.walk(folderPath):
            for file in files:
                zipf.write(os.path.join(root, file))
        zipf.close()
    except Exception as e:
        printAndLog(self, f"ERROR: An error occurred while compressing the folder: {e}", "ERROR")
        sys.exit()
