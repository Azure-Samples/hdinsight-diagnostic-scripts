from lib.utils import *
import os
from datetime import datetime
import time
import glob
from bs4 import BeautifulSoup
import requests
from netaddr import *

from xml.etree.ElementTree import *


def getServiceTagsJSONFileName(self):
    """Looks for a "ServiceTags_Public*.json" file in the current directory. If couldn't find any, goes ahead and downloads the latest"""

    # Ref: https://docs.microsoft.com/en-us/azure/virtual-network/service-tags-overview#discover-service-tags-by-using-downloadable-json-files
    SERVICE_TAGS_DOWNLOAD_URL = "https://www.microsoft.com/en-us/download/confirmation.aspx?id=56519"  # Azure Public
    # SERVICE_TAGS_DOWNLOAD_URL = 'https://www.microsoft.com/en-us/download/confirmation.aspx?id=57063' #Azure US Gov
    # SERVICE_TAGS_DOWNLOAD_URL = 'https://www.microsoft.com/en-us/download/confirmation.aspx?id=57062' #Azure China
    # SERVICE_TAGS_DOWNLOAD_URL = 'https://www.microsoft.com/en-us/download/confirmation.aspx?id=57064' #Azure Germany

    # Check if there is a JSON filen with a name starting with "ServiceTags_Public_" and ending with ".json" in the current directory
    serviceTagsJSONFilename = ""
    downloadLatestJSONFile = "n"
    latestServiceTagsJSONFilename = ""

    for file in glob.glob("config/ServiceTags_Public*.json"):
        serviceTagsJSONFilename = file

    if serviceTagsJSONFilename != "":
        serviceTagsJSONFilenameYYYYMMDD = serviceTagsJSONFilename[26:34]
        serviceTagsJSONFileDateTime = datetime.strptime(serviceTagsJSONFilenameYYYYMMDD, "%Y%m%d")
        # printAndLog(self,serviceTagsJSONFileDateTime)

        if self.verboseMode:
            showTextWithIcon(self, 'Service Tag JSON file "' + Fore.GREEN + serviceTagsJSONFilename + Style.RESET_ALL + '" is found in current folder. File date is : ' + Fore.GREEN + serviceTagsJSONFilenameYYYYMMDD + Style.RESET_ALL + ", which is " + Fore.GREEN + str((datetime.now() - serviceTagsJSONFileDateTime).days) + Style.RESET_ALL + " days old")

        if int(str((datetime.now() - serviceTagsJSONFileDateTime).days)) > 15:
            if not (self.verboseMode):
                printAndLog(self, ' + Service Tag JSON file "' + Fore.GREEN + serviceTagsJSONFilename + Style.RESET_ALL + '" is found in current folder. File date is : ' + Fore.GREEN + serviceTagsJSONFilenameYYYYMMDD + Style.RESET_ALL + ", which is " + Fore.RED + str((datetime.now() - serviceTagsJSONFileDateTime).days) + Style.RESET_ALL + " days old")
            downloadLatestJSONFile = input("     Would you like to download the latest Service Tags JSON file from Microsoft Download Center ? (y)/n ")
            if downloadLatestJSONFile == "":
                downloadLatestJSONFile = "y"

    # Couldn't find any. We will need to download it from Microsoft Download Center
    if serviceTagsJSONFilename == "" or downloadLatestJSONFile == "y":
        if serviceTagsJSONFilename == "":
            printAndLog(self, "Couldn't find ServiceTags_Public*.json file in the current directory. Downloading JSON file from Download Center...")

        if downloadLatestJSONFile == "y":
            printAndLog(self, "     Downloading latest Service Tags JSON file from Microsoft Download Center...")

        # Get the actual download URL from the download page
        result = []
        response = requests.get(SERVICE_TAGS_DOWNLOAD_URL)
        soup = BeautifulSoup(response.text, "html.parser")
        for link in soup.findAll("a"):
            if ".json" in link.get("href") and not (link.get("href") in result):
                result.append(link.get("href"))
        printAndLog(self, "     " + str(result[0]))

        latestServiceTagsJSONFilename = result[0].split("/")[-1]

        # Download the JSON file
        r = requests.get(result[0], allow_redirects=True)
        open("config/" + latestServiceTagsJSONFilename, "wb").write(r.content)

        if downloadLatestJSONFile == "y":
            # backup the old JSON file with ".bak" suffix
            os.rename(serviceTagsJSONFilename, serviceTagsJSONFilename + ".bak")
            return "config/" + latestServiceTagsJSONFilename

    if serviceTagsJSONFilename == "":
        return "config/" + latestServiceTagsJSONFilename
    else:
        return serviceTagsJSONFilename


def getHDInsightManagementEndpointIPsFromDocs(self):
    """Get 4 Global HDIME IPs and All Regional HDIME IPs from https://docs.microsoft.com/en-us/azure/hdinsight/hdinsight-management-ip-addresses"""

    fourGlobalIPlist = []
    regionalIPdict = {}
    docURL = "https://docs.microsoft.com/en-us/azure/hdinsight/hdinsight-management-ip-addresses"

    deltaDays = 999
    if self.params["HDIME_IPS_CHECK_DATETIME"] != "":
        checkDateTime = datetime.fromtimestamp(int(str(self.params["HDIME_IPS_CHECK_DATETIME"]).split(".")[0]))
        deltaDays = (datetime.now() - checkDateTime).days

    if deltaDays > 7:
        printAndLog(self, "HDInsight Management Endpoint IPs are " + str(deltaDays) + " days old. Trying to update ...")

        try:
            webpage = requests.get(docURL)
            soup = BeautifulSoup(webpage.content, "lxml")

            # First HTML table is the 4 Global HDIME IPs
            first_table = soup.find("tbody")
            for tr in first_table.find_all("tr"):
                for td in tr.find("td"):
                    fourGlobalIPlist.append(td)

            # Second HTML table is the 2 regional HDIME IPs table
            second_table = soup.findAll("tbody")[1]
            for tr in second_table.find_all("tr"):

                # 2nd TD contains the "Region"
                row_region = str(tr.findAll("td")[1])[4:][:-5]
                # 3rd TD contains the IPs
                row_regional_ips = str(tr.findAll("td")[2])[4:][:-5].split("<br/>")

                regionalIPdict[row_region] = row_regional_ips

            # printAndLog(self,regionalIPdict)
            # sys.exit()
            self.params["ALL_REGIONAL_HDIME_IPS"] = regionalIPdict

            # write the results to params.conf file
            f = open("config/params.conf", "r")
            lines = f.readlines()
            line_index = -1
            for line in lines:
                line_index = line_index + 1
                if line.startswith("FOUR_GLOBAL_HDIME_IPS"):
                    lines[line_index] = 'FOUR_GLOBAL_HDIME_IPS="' + str(fourGlobalIPlist) + '"\n'
                if line.startswith("HDIME_IPS_CHECK_DATETIME"):
                    lines[line_index] = 'HDIME_IPS_CHECK_DATETIME="' + str(time.time()) + '"\n'
                if line.startswith("ALL_REGIONAL_HDIME_IPS"):
                    lines[line_index] = 'ALL_REGIONAL_HDIME_IPS="' + str(regionalIPdict) + '"\n'

            f = open("config/params.conf", "w")
            f.writelines(lines)
            f.close()
            # return fourGlobalIPlist
            self.params["FOUR_GLOBAL_HDIME_IPS"] = fourGlobalIPlist
        except:
            printAndLog(self, "Cannot reach " + docURL + ". Will be using the 4 global HDInsight Management IP addresses saved in params.conf before on " + time.ctime(int(str(self.params["HDIME_IPS_CHECK_DATETIME"]).split(".")[0])) + " UTC")
            # return self.params['FOUR_GLOBAL_HDIME_IPS']
            # self.params['FOUR_GLOBAL_HDIME_IPS']


def getSingleRegionalServiceTagsFromDocs(self):
    """Ref: https://docs.microsoft.com/en-us/azure/hdinsight/hdinsight-service-tags#use-a-single-regional-service-tag"""

    serviceTags = {}
    docURL = "https://docs.microsoft.com/en-us/azure/hdinsight/hdinsight-service-tags"

    try:

        webpage = requests.get(docURL)
        soup = BeautifulSoup(webpage.content, "lxml")
        first_table = soup.find("tbody")
        for tr in first_table.find_all("tr"):
            tdindex = 0
            row_region = ""
            row_service_tag = ""
            for td in tr.find_all("td"):  # Each row has 4 cells / tds
                tdindex = tdindex + 1
                if tdindex % 4 == 1:  # 1st td "Country", ignore
                    pass
                elif tdindex % 4 == 2:  # 2nd TD, "Region"
                    row_region = str(td.text)
                elif tdindex % 4 == 3:  # 3rd TD, "Service tag"
                    row_service_tag = str(td.text)
                # 4th TD - EMPTY
            serviceTags[row_region] = row_service_tag
        # printAndLog(self,serviceTags)

        # write the result to params.conf file
        f = open("config/params.conf", "r")
        lines = f.readlines()
        line_index = -1
        for line in lines:
            line_index = line_index + 1
            if line.startswith("SINGLE_REGIONAL_SERVICE_TAGS"):
                lines[line_index] = 'SINGLE_REGIONAL_SERVICE_TAGS="' + str(serviceTags) + '"\n'
            if line.startswith("SINGLE_REGIONAL_SERVICE_TAGS_CHECK_DATETIME"):
                lines[line_index] = 'SINGLE_REGIONAL_SERVICE_TAGS_CHECK_DATETIME="' + str(time.time()) + '"\n'

        f = open("config/params.conf", "w")
        f.writelines(lines)
        f.close()

    except:
        printAndLog(self, "Cannot reach " + docURL + ". Will be using the single regional service tags saved in params.conf before on " + time.ctime(int(str(self.params["SINGLE_REGIONAL_SERVICE_TAGS_CHECK_DATETIME"]).split(".")[0])) + " UTC")
        serviceTags = self.params["SINGLE_REGIONAL_SERVICE_TAGS"]

    # Also generate a similar dictionary (with a dictionary name suffix '_SHORT') with the "short" region names
    serviceTagsShort = {}
    for regionDisplayName in serviceTags:
        serviceTagsShort[convertRegionDisplayNameToRegionName(serviceTags[regionDisplayName])] = serviceTags[regionDisplayName]
    self.params["SINGLE_REGIONAL_SERVICE_TAGS_SHORT"] = serviceTagsShort

    return serviceTags


def getMultipleRegionalServiceTagsForGroup1FromDocs(self):
    """Ref: https://docs.microsoft.com/en-us/azure/hdinsight/hdinsight-service-tags#use-multiple-regional-service-tags"""

    serviceTags = {}
    docURL = "https://docs.microsoft.com/en-us/azure/hdinsight/hdinsight-service-tags#group-1"

    try:

        webpage = requests.get(docURL)
        soup = BeautifulSoup(webpage.content, "lxml")

        # this time we will need 2nd table/tbody
        tables = soup.find_all("tbody")

        second_table = ""
        tableindex = 0
        for table in tables:
            tableindex = tableindex + 1
            if tableindex == 2:
                second_table = table
                exit

        for tr in second_table.find_all("tr"):
            tdindex = 0
            row_region = ""
            row_service_tag = ""
            for td in tr.find_all("td"):  # Each row has 4 cells / tds
                tdindex = tdindex + 1
                if tdindex % 4 == 1:  # 1st td "Country", ignore
                    pass
                elif tdindex % 4 == 2:  # 2nd TD, "Region"
                    row_region = str(td.text)
                elif tdindex % 4 == 3:  # 3rd TD, "Service tag"
                    row_service_tag = str(td.text)
                # 4th TD - EMPTY
            serviceTags[row_region] = row_service_tag
        # printAndLog(self,serviceTags)

        # write the result to params.conf file
        f = open("config/params.conf", "r")
        lines = f.readlines()
        line_index = -1
        for line in lines:
            line_index = line_index + 1
            if line.startswith("MULTIPLE_REGIONAL_SERVICE_TAGS_FOR_GROUP1"):
                lines[line_index] = 'MULTIPLE_REGIONAL_SERVICE_TAGS_FOR_GROUP1="' + str(serviceTags) + '"\n'
            if line.startswith("MULTIPLE_REGIONAL_SERVICE_TAGS_FOR_GROUP1_CHECK_DATETIME"):
                lines[line_index] = 'MULTIPLE_REGIONAL_SERVICE_TAGS_FOR_GROUP1_CHECK_DATETIME="' + str(time.time()) + '"\n'

        f = open("config/params.conf", "w")
        f.writelines(lines)
        f.close()

    except:
        printAndLog(self, "Cannot reach " + docURL + ". Will be using the multiple regional service tags for Group1 whic was saved in params.conf before on " + time.ctime(int(str(self.params["MULTIPLE_REGIONAL_SERVICE_TAGS_FOR_GROUP1_CHECK_DATETIME"]).split(".")[0])) + " UTC")
        serviceTags = self.params["MULTIPLE_REGIONAL_SERVICE_TAGS_FOR_GROUP1"]

    # Also generate a similar dictionary (with a dictionary name suffix '_SHORT') with the "short" region names
    serviceTagsShort = {}
    for regionDisplayName in serviceTags:
        serviceTagsShort[convertRegionDisplayNameToRegionName(serviceTags[regionDisplayName])] = serviceTags[regionDisplayName]
    self.params["MULTIPLE_REGIONAL_SERVICE_TAGS_FOR_GROUP1_SHORT"] = serviceTagsShort

    return serviceTags

def getHDInsightManagementEndpointIPsForCurrentRegion(self):
    """Get the HDIME IPs for current region (based on the IPs in the table in docs, not from Service Tag JSON!)"""

    # We have current region name in "short" format like "eastus" in "self.regionName"
    # But the IPs that we are looking for in self.params["ALL_REGIONAL_HDIME_IPS"] in a format like 'East US': ['13.82.225.233', '40.71.175.99']
    # We need to convert "eastus" to "East US". To achieve this, we will use "self.azurePublicCloudRegionNames" that has the "mapping" in a format like 'australiacentral':'HDInsight.AustraliaCentral'
    # So, we need to refer to "self.azurePublicCloudRegionNames" as the first step

    # To avoid confusion, creating variable for each "version" of the region name
    shortRegionName = self.regionName  # E.g. "eastus"
    longRegionName = ""  # E.g. "East US"
    longRegionNameWithoutSpace = ""  # E.g. "EastUS"

    # print(self.regionName)
    longRegionNameWithoutSpace = str(self.azurePublicCloudRegionNames[self.regionName]).split(".")[1]
    # print(longRegionNameWithoutSpace)

    # Now we can look for the IPs in self.params["ALL_REGIONAL_HDIME_IPS"]
    for regionName in self.params["ALL_REGIONAL_HDIME_IPS"]:
        if regionName.replace(" ", "") == longRegionNameWithoutSpace:
            longRegionName = regionName
            break
    # print(longRegionName)
    return self.params["ALL_REGIONAL_HDIME_IPS"][longRegionName]
