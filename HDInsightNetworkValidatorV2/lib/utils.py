import os
from os import path
import sys
import logging
import logging.handlers
import time
import glob
import string
import random
import json
import subprocess
from netaddr import *

from progress.spinner import Spinner
from halo import Halo
from colorama import *

from xml.etree.ElementTree import *

from azure.identity import DefaultAzureCredential  # ,DeviceCodeCredential
from azure.mgmt.hdinsight.models import *


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


def getSqlServerNameFromJDBCUrl(jdbcURL):
    """Returns the Azure SQL Server name from given Hive, Oozie or Ranger JDBC URL"""
    return jdbcURL[17:].split(";")[0]


def getFQDNFromHTTPURL(httpURL):
    """Returns the FQDN from an HTTP URL for a storage account"""
    return httpURL.split("//")[1].split("/")[0]


def getIPsfromCIDR(CIDR):
    """Returns all the IPs for the given CIDR"""
    tmpIpList = []
    if CIDR.endswith("/32"):
        # NO need to convert
        tmpIpList.append(CIDR[0:-3])  # strip "/32"
    else:
        ip_cidr = IPNetwork(CIDR)  # netaddr
        ip_list = list(ip_cidr)
        for ip in ip_list:
            tmpIpList.append(ip)
    return tmpIpList


# Gets the HDIME IPs for the required tags
def getHDInsightManagementEndpointIPsForRequiredServiceTags(self):
    """Returns the HDIME IPs for required HDInsight Service Tags"""

    HDIME_IPs = {}

    # We assume that self.requiredServiceTags already pre-populated before
    for serviceTag in self.requiredServiceTags:
        for region in self.azurePublicCloudRegionNames:
            if self.azurePublicCloudRegionNames[region] == "HDInsight." + serviceTag.replace(" ", ""):
                HDIME_IPs[serviceTag] = getHDInsightManagementEndpointIPs(self)
    return HDIME_IPs


def getAzurePublicCloudRegionNamesFromServiceTagsJSONFile(self):
    """Gets the Azure Public Cloud 'short' region names (e.g. 'EastUS') from ServiceTagsJSONFile"""

    azurePublicCloudRegionNames = {}

    # Because getHDInsightManagementEndpointIPs() method already called and got a ServiceTags_Public*.json file, we will use it
    serviceTagsJSONFilename = ""
    for file in glob.glob("config/ServiceTags_Public*.json"):
        serviceTagsJSONFilename = file

    # Parse JSON
    jsonContent = ""
    f = open(serviceTagsJSONFilename, "r")
    allJSONvalues = (json.load(f))["values"]
    f.close()

    regionDisplayName = ""
    regionName = ""
    for azureService in allJSONvalues:
        if str(azureService["name"]).startswith("HDInsight."):
            regionDisplayName = azureService["name"]
            regionName = azureService["properties"]["region"]
            azurePublicCloudRegionNames[regionName] = regionDisplayName

    return azurePublicCloudRegionNames


def getHDInsightManagementEndpointIPs(self):
    """Gets the HDIME IPs for the current 'self.regionName' region"""

    # Parse JSON
    jsonContent = ""
    f = open(self.serviceTagsJSONFileName, "r")
    allJSONvalues = (json.load(f))["values"]
    f.close()

    currentRegionLongName = ""  # For ex: 'East US'
    currentRegionShortName = ""  # For ex: 'eastus'
    for azureService in allJSONvalues:
        if str(azureService["name"]).startswith("HDInsight."):

            currentRegionLongName = azureService["name"]
            currentRegionShortName = azureService["properties"]["region"]
            if currentRegionShortName == self.regionName:
                # Below list will contain the IP addresses for the current region
                regionIPList = []
                # Push the IP addresses into regionIPList list
                for addressPrefix in azureService["properties"]["addressPrefixes"]:
                    # ignore IPv6 ones
                    if not (addressPrefix.find(":") > 0):
                        # printAndLog(self,'Hede : ' + addressPrefix)
                        regionIPList.extend(getIPsfromCIDR(str(addressPrefix)))
    return regionIPList


def getRegionalHDIMEIPsByRegionName(self, regionName):
    """Returns the HDIME IPs for given regionName"""
    for regionDisplayName in self.params["ALL_REGIONAL_HDIME_IPS"]:
        # printAndLog(self,convertRegionDisplayNameToRegionNameWithoutDot(regionDisplayName))
        if convertRegionDisplayNameToRegionNameWithoutDot(regionDisplayName) == regionName:
            return self.params["ALL_REGIONAL_HDIME_IPS"][regionDisplayName]


def convertRegionDisplayNameToRegionName(regionDisplayName):
    """Converts given region display name to region name. For ex; 'HDInsight.EastUS' to 'eastus'"""
    return str(regionDisplayName.split(".")[1]).lower()


def convertRegionDisplayNameToRegionNameWithoutDot(regionDisplayName):
    """Converts given region display name to region name without dot. For ex; 'East US' to 'eastus'"""
    return str(regionDisplayName).lower().replace(" ", "")


def getRequiredServiceTagsForCurrentRegion(self):
    """Gets the required HDInsight service tags for current region"""
    requiredServiceTags = {}

    # Check if Single Region service tag is enough
    lookupDict = self.params["SINGLE_REGIONAL_SERVICE_TAGS_SHORT"]

    if self.regionName in lookupDict:
        requiredServiceTags[self.regionName] = lookupDict[self.regionName]
        return requiredServiceTags

    # Group 2, 3 and 4 region names
    group2and3and4RegionNames = ["chinanorth", "chinaeast", "usgoviowa", "usgovvirginia", "germanycentral", "germanynortheast"]

    # Group1 : https://docs.microsoft.com/en-us/azure/hdinsight/hdinsight-service-tags#group-1
    if self.regionName not in group2and3and4RegionNames:
        lookupDict = self.params["MULTIPLE_REGIONAL_SERVICE_TAGS_FOR_GROUP1_SHORT"]
        # Add the region service tag
        if self.regionName in lookupDict:
            requiredServiceTags[self.regionName] = lookupDict[self.regionName]

        # EastUS and WestUS is "must" for Group1. But if the region name is east us or west us already, don't add them twice
        if "eastus" not in requiredServiceTags:
            requiredServiceTags["eastus"] = "HDInsight.EastUS"
        if "westus" not in requiredServiceTags:
            requiredServiceTags["westus"] = "HDInsight.WestUS"

    elif self.regionName == "chinanorth" or self.regionName == "chinaeast":
        # Group2 : https://docs.microsoft.com/en-us/azure/hdinsight/hdinsight-service-tags#group-2
        requiredServiceTags["China North"] = "HDInsight.ChinaNorth"
        requiredServiceTags["China East"] = "HDInsight.ChinaEast"

    elif self.regionName == "usgoviowa" or self.regionName == "usgovvirginia":
        # Group3 : https://docs.microsoft.com/en-us/azure/hdinsight/hdinsight-service-tags#group-3
        printAndLog(self, "")
        requiredServiceTags["US Gov Iowa"] = "HDInsight.USGovIowa"
        requiredServiceTags["US Gov Virginia"] = "HDInsight.USGovVirginia"

    elif self.regionName == "germanycentral" or self.regionName == "germanynortheast":
        # Group4 : https://docs.microsoft.com/en-us/azure/hdinsight/hdinsight-service-tags#group-4
        printAndLog(self, "")
        requiredServiceTags["Germany Central"] = "HDInsight.GermanyCentral"
        requiredServiceTags["Germany Northeast"] = "HDInsight.GermanyNortheast"

    self.requiredServiceTags = requiredServiceTags
    return requiredServiceTags


def getDefaultCredential(self):

    if not ("SP_JSON_FILE" in self.params) or self.params["SP_JSON_FILE"] == "":
        SP_JSON_CONTENT = ""
        printAndLog(self, "Please copy/paste the service principal JSON content, hit Enter and press Ctrl-D after")
        json_console_input = sys.stdin.readlines()

        for line in json_console_input:
            SP_JSON_CONTENT = SP_JSON_CONTENT + line
        spnJSON = json.loads(SP_JSON_CONTENT)
    else:
        # Read the SP details from JSON file
        try:
            with open(self.params["SP_JSON_FILE"]) as f:
                spnJSON = json.load(f)
        except:
            printAndLog(self, 'Error reading service principal JSON details from "' + self.params["SP_JSON_FILE"] + '" file.\n' + "Exception : " + str(sys.exc_info()[0]) + "\n" + "Exception message : " + str(sys.exc_info()[1]) + "\n")
            printAndLog(self, "Exiting.")
            sys.exit()

    # https://docs.microsoft.com/en-us/azure/developer/python/azure-sdk-authenticate#when-does-authentication-and-authorization-occur

    # Below environmental variables needs to be set for DefaultAzureCredential to work
    os.environ["AZURE_CLIENT_ID"] = spnJSON["clientId"]
    os.environ["AZURE_CLIENT_SECRET"] = spnJSON["clientSecret"]
    os.environ["AZURE_TENANT_ID"] = spnJSON["tenantId"]
    os.environ["SUBSCRIPTION_ID"] = spnJSON["subscriptionId"]
    # logging.info("Service Principal details registered in environmental variables")

    credential = DefaultAzureCredential()
    return credential


def getHostName():
    """Get current VM's hostname by executing hostname command"""
    hostname = executeCommand("hostname", "", False)
    return hostname.strip()


def generateCharacters(charCount):
    """Generates ASCII lowercase random characters"""
    # https://www.educative.io/edpresso/how-to-generate-a-random-string-in-python
    letters = string.ascii_lowercase
    result = "".join(random.choice(letters) for i in range(charCount))
    return result


def showTextWithIcon(self, theText, theSpinner="line", iconType="info", iconPlacement="left"):
    spinner = Halo(text=theText, spinner="line", placement=iconPlacement)
    spinner.start()
    if iconType == "info":
        # spinner.info()  #.info() generates "i" icon in "Blue". To be able to change the color, using .stop_and_persist()
        spinner.stop_and_persist(symbol=Fore.GREEN + "ℹ" + Fore.RESET, text=theText)
        self.logger.info(theText)
    elif iconType == "warn":
        spinner.warn()
        self.logger.warn(theText)
    elif iconType == "succeed":
        spinner.succeed()
        self.logger.info(theText)
    elif iconType == "fail":
        spinner.fail()
        self.logger.warn(theText)
    elif iconType == "result_success":
        # spinner.stop_and_persist(symbol='🦄'.encode('utf-8'))
        spinner.stop_and_persist(symbol="\U0001f44D".encode("utf-8"))  # Thumbs up sign
        self.logger.info(theText)
    elif iconType == "result_fail":
        spinner.stop_and_persist(symbol="\U0001f44E".encode("utf-8"))  # Thumbs down sign
        self.logger.info(theText)

    if self.verboseMode:
        print("")


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


class HDIMEIPNSGCheckResult:
    def __init__(self, isOk, HDIMEIP, Port, Scope):
        self.isOk = isOk
        self.HDIMEIP = HDIMEIP
        self.Port = Port
        self.Scope = Scope


class AzureFirewallRuleCheckResult:
    def __init__(self, direction, name, source_addresses, protocols, target_fqdns, fqdn_tags, destination_addresses, destination_ports, destination_fqdns, ruleNameinDocs, isOK):

        # ARC
        # Check Application Rule Collections ...
        # {'additional_properties': {'direction': 'Inbound', 'actions': [], 'priority': 0},
        # 'name': 'rule-2', 'description': None, 'source_addresses': ['*'],
        # 'protocols': [<azure.mgmt.network.v2020_11_01.models._models_py3.AzureFirewallApplicationRuleProtocol object at 0x7eff5af62c18>],
        # 'target_fqdns': ['login.windows.net'], 'fqdn_tags': [], 'source_ip_groups': []}
        self.direction = direction
        # self.actions = actions
        # self.priority = priority
        self.name = name
        self.source_addresses = source_addresses
        self.protocols = protocols
        self.target_fqdns = target_fqdns
        self.fqdn_tags = fqdn_tags

        # NRC
        # {'additional_properties': {},
        # 'name': 'sqldeny!!!', 'description': None, 'protocols': ['Any'], 'source_addresses': ['*'], 'destination_addresses': ['Sql'], 'destination_ports': ['1433', '11000-11999'], 'destination_fqdns': [], 'source_ip_groups': [], 'destination_ip_groups': []}
        self.destination_addresses = destination_addresses
        self.destination_ports = destination_ports
        self.destination_fqdns = destination_fqdns

        self.ruleNameinDocs = ruleNameinDocs
        self.isOK = isOK
