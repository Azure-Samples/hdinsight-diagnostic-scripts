from lib.utils import *
import time
from netaddr import *
from prettytable import PrettyTable

from xml.etree.ElementTree import *
from azure.identity import DefaultAzureCredential  # ,DeviceCodeCredential
from azure.mgmt.hdinsight.models import *

NETWORK_WATCHER_NAME_PREFIX = "HDInsightDiagNW-"


def getCurrentVNet(self):
    """Get current VNet"""
    current_subnet_id = self.current_vm_nic.ip_configurations[0].subnet.id
    current_vm_vnet_name = current_subnet_id.split("/")[-3]
    allVNets = self.network_client.virtual_networks.list_all()
    for vnet in allVNets:
        if current_vm_vnet_name == vnet.id.split("/")[-1]:
            return vnet
    return None


def getCurrentVNetsResourceGroup(self):
    """Get current VNet's resource group"""
    currentVNetRGName = self.current_vnet.id.split("/")[4]
    resource_groups = self.resource_client.resource_groups.list()
    for rg in resource_groups:
        if str(currentVNetRGName).lower() == str(rg.name).lower():
            return rg


def getCurrentSubnet(self):
    """Get current subnet"""
    subnet = self.network_client.subnets.get(self.current_vnet_rg.name, self.current_vnet.name, self.current_subnet_name, "ipConfigurations")
    return subnet


def getNSG(current_subnet_nsg_rg, current_subnet_nsg_name, self):
    """Get NSG set on the subnet if any"""
    nsg = self.network_client.network_security_groups.get(current_subnet_nsg_rg, current_subnet_nsg_name)
    return nsg


def getSecurityRules(current_subnet_nsg_rg, current_subnet_nsg_name, network_client):
    """Get NSG rules per given NSG RG/Name"""
    security_rules = network_client.security_rules.list(current_subnet_nsg_rg, current_subnet_nsg_name)
    return security_rules


def getRouteTable(self):
    # Returns the route table set for the current subnet
    route_table_rg = self.current_subnet.route_table.id.split("/")[4]
    route_table_name = self.current_subnet.route_table.id.split("/")[8]
    route_table = self.network_client.route_tables.get(route_table_rg, route_table_name)
    return route_table


def getNextHopIP(self):
    next_hop_ip = ""
    # Get the NextHop IP finding a route with VirtualAppliance next_hop_type by iterating the routes in the UDR
    for route in self.current_route_table.routes:
        if route.next_hop_type == "VirtualAppliance":
            next_hop_ip = route.next_hop_ip_address
            break
    return next_hop_ip


# Checks if customer enabled "Service Endpoints" for Azure SQL, Azure Storage and Azure Active Directory
# Ref: https://docs.microsoft.com/en-us/azure/hdinsight/network-virtual-appliance#service-endpoint-capable-dependencies
def checkSubnetServiceEndpoints(self):
    # printAndLog(self, self.current_subnet)
    printAndLog(self, self.current_subnet.service_endpoints)


def checkSubnetServiceEndpointsForAzureSQL(self):
    serviceEndpoints = self.current_subnet.service_endpoints
    if serviceEndpoints == None:
        showTextWithIcon(self, "  You DON'T have any service endpoint added for your subnet. You need to be sure that your Firewall allows traffic to Azure SQL in the outbound direction for TCP 1433 port and TCP 11000-11999 port range", "line", "warn")
    else:
        for serviceEndpoint in serviceEndpoints:
            if serviceEndpoint.service == "Microsoft.Sql" and serviceEndpoint.provisioning_state == "Succeeded":
                if not (self.verboseMode):
                    return True
                else:
                    showTextWithIcon(self, '  You have "Microsoft.Sql" service endpoint added for your subnet ')
                    return True
        showTextWithIcon(self, '  You don\'t have "Microsoft.Sql" service endpoint added for your subnet ', "line", "warn")
    return False


# TODO
# https://docs.microsoft.com/en-us/azure/hdinsight/service-endpoint-policies
# https://github.com/Azure-Samples/hdinsight-enterprise-security/blob/main/hdinsight-service-endpoint-policy-resources.json
# https://raw.githubusercontent.com/Azure-Samples/hdinsight-enterprise-security/main/hdinsight-service-endpoint-policy-resources.json
def checkSubnetServiceEndpointPoliciesForAzureStorage(self):
    printAndLog(self, self.current_subnet.service_endpoint_policies)
    printAndLog(self, "")


def getSubnetNSGRules(self):
    """Gets the NSG rules in a Subnet"""
    nsgRules = getSecurityRules(self.current_subnet_nsg_rg_name, self.current_subnet_nsg_name, self.network_client)
    return nsgRules


def checkSubnetNSGRulesIfItHasAnyHDInsightServiceTags(self):
    """Checks the Subnet NSG Rules if "any" HDInsight Service Tag is added or not. This is used to see whether customer is adding HDIME IPs manually or via Service Tags"""
    current_subnet_nsg_rules = getSubnetNSGRules(self)
    for security_rule in current_subnet_nsg_rules:

        if ( len(security_rule.source_address_prefix)>0 ):
            if (
                # First 9 characters should be "HDInsight" (Covers both "HDInsight" global tag as well as any other "HDInsight.someregion" regional tags)
                security_rule.source_address_prefix[:9] == "HDInsight"
                and (security_rule.destination_port_range == "443" or security_rule.destination_port_range == "*")
                and (security_rule.direction == "Inbound")
            ):
                return True
    return False


def checkSubnetNSGRulesForServiceTags(self):
    """Checks the Subnet NSG Rules if HDInsight Service Tags are added correctly or not"""
    # Ref: https://docs.microsoft.com/en-us/azure/hdinsight/hdinsight-service-tags

    # There could be 4 combinations customer could have been using :

    # Scenario 1 : All global
    # Example :
    # HDInsight 443, 9400

    # Scenario 2 : All regional
    # Example :
    # HDInsight.EastUS 443, 9400
    # HDInsight.WestUS 443, 9400

    # Scenario 3 : 443 global, 9400 regional
    # Example :
    # HDInsight 443
    # HDInsight.EastUS 9400
    # HDInsight.WestUS 9400

    # Scenario 4: 9400 global, 443 regional
    # Example :
    # HDInsight 9400
    # HDInsight.EastUS 443
    # HDInsight.WestUS 443

    isPort443okWithHDInsightGlobalTag = False
    isPort9400okWithHDInsightGlobalTag = False
    isPort443okWithAllHDInsightRegionalTags = False
    isPort9400okWithAllHDInsightRegionalTags = False

    #  Below dict will store the HDInsight region names (like "HDInsight.EastUS") as key, and "True" for the value if the serviceTag
    #  Initialize the dict with the key names with short region names, "False" as their values
    serviceTagValidationsFor443 = {}
    for serviceTag in self.requiredServiceTags:
        serviceTagValidationsFor443[self.requiredServiceTags[serviceTag]] = False

    # If Kafka Rest Proxy is enabled, TCP 9400 needed to be open to HDIME IPs
    if self.kafkaRestProxyEnabled:
        serviceTagValidationsFor9400 = {}
        for serviceTag in self.requiredServiceTags:
            serviceTagValidationsFor9400[self.requiredServiceTags[serviceTag]] = False

    # https://github.com/Azure/azure-sdk-for-python/blob/azure-mgmt-network_18.0.0/sdk/network/azure-mgmt-network/azure/mgmt/network/v2020_11_01/models/_models.py#L17753

    current_subnet_nsg_rules = getSubnetNSGRules(self)

    if self.verboseMode:
        printAndLog(self, "  NSG rules in your subnet is as follows :")
        # Show the NSG rules in a PrettyTable
        pt = PrettyTable(["Priority", "Rule Name", "Direction", "Source Address Prefix", "Destination Port Range"])
    for security_rule in current_subnet_nsg_rules:
        if self.verboseMode:
            pt.add_row([str(security_rule.priority), security_rule.name, security_rule.direction, security_rule.source_address_prefix, str(security_rule.destination_port_range)])

        # A-Start checking from Global "HDInsight" tag perspective
        if self.kafkaRestProxyEnabled:
            if security_rule.source_address_prefix == "HDInsight" and (security_rule.destination_port_range == "443" or security_rule.destination_port_range == "*") and (security_rule.direction == "Inbound"):
                isPort443okWithHDInsightGlobalTag = True
                if self.verboseMode:
                    printAndLog(self, '    + OK ==> Above security rule with priority "' + str(security_rule.priority) + '" should be allowing HDInsight Management Endpoint traffic from all regions to HTTPS port 443')
            if security_rule.source_address_prefix == "HDInsight" and (security_rule.destination_port_range == "9400" or security_rule.destination_port_range == "*") and (security_rule.direction == "Inbound"):
                isPort9400okWithHDInsightGlobalTag = True
                if self.verboseMode:
                    printAndLog(self, '    + OK ==> Above security rule with priority "' + str(security_rule.priority) + '" should be allowing HDInsight Management Endpoint traffic from all regions to HTTPS port 9400 for Kafka Rest Proxy')
            # Scenario1 (with Kafka Rest Proxy)
            if isPort443okWithHDInsightGlobalTag and isPort9400okWithHDInsightGlobalTag:
                if self.verboseMode:
                    printAndLog(self, '  You are using HDInsight "global tag" for both 443 and 9400 ports')
                return True
        else:
            if security_rule.source_address_prefix == "HDInsight" and (security_rule.destination_port_range == "443" or security_rule.destination_port_range == "*") and (security_rule.direction == "Inbound"):
                # Scenario1 (without Kafka Rest Proxy)
                if self.verboseMode:
                    printAndLog(self, Fore.GREEN + '    ✔ : Above security rule with priority "' + str(security_rule.priority) + '" should be allowing HDInsight Management Endpoint traffic from all regions to HTTPS port 443')
                    printAndLog(self, '  You are using HDInsight "global tag" for port 443')
                return True

        # B-Start checking from required regional tags (like HDInsight.EastUS, HDInsight.WestUS etc) perspective

        # Check all service tags
        if self.kafkaRestProxyEnabled:
            # if Kafka Rest Proxy is enabled in the cluster, we need to check for port 443 and 9400 access separately
            if (security_rule.source_address_prefix in serviceTagValidationsFor443) and (security_rule.destination_port_range == "443" or security_rule.destination_port_range == "*") and (security_rule.direction == "Inbound"):
                serviceTagValidationsFor443[security_rule.source_address_prefix] = True

            if (security_rule.source_address_prefix in serviceTagValidationsFor9400) and (security_rule.destination_port_range == "9400" or security_rule.destination_port_range == "*") and (security_rule.direction == "Inbound"):
                serviceTagValidationsFor9400[security_rule.source_address_prefix] = True
        else:
            if (security_rule.source_address_prefix in serviceTagValidationsFor443) and (security_rule.destination_port_range == "443" or security_rule.destination_port_range == "*") and (security_rule.direction == "Inbound"):
                serviceTagValidationsFor443[security_rule.source_address_prefix] = True

    if self.verboseMode:
        printAndLog(self, pt)

    if all(x == True for x in serviceTagValidationsFor443.values()):
        isPort443okWithAllHDInsightRegionalTags = True

    if self.kafkaRestProxyEnabled:
        if all(x == True for x in serviceTagValidationsFor9400.values()):
            isPort9400okWithAllHDInsightRegionalTags = True

    # If all required service tags are in place or not
    if self.kafkaRestProxyEnabled:
        if isPort443okWithAllHDInsightRegionalTags and isPort9400okWithAllHDInsightRegionalTags:
            # Scenario2
            printAndLog(self, '  You are using "regional tags" for both 443 and 9400 ports')
            return True
        elif isPort443okWithHDInsightGlobalTag and isPort9400okWithAllHDInsightRegionalTags:
            # Scenario3
            printAndLog(self, '  You are using HDInsight "global tag" for 443 and "regional tags" for port 9400')
            return True
        elif isPort443okWithAllHDInsightRegionalTags and isPort9400okWithHDInsightGlobalTag:
            # Scenario4
            printAndLog(self, '  You are using "regional tags" for 443 and HDInsight "global tag" for port 9400')
            return True
        else:
            # Something is missing, inform user!
            if self.verboseMode:
                if isPort443okWithAllHDInsightRegionalTags:
                    # 443 is ok with regional tags but 9400 is missing
                    for serviceTagValidation in serviceTagValidationsFor9400:
                        if serviceTagValidationsFor9400[serviceTagValidation] == False:
                            printAndLog(self, Fore.RED + '    ✖ : "' + str(serviceTagValidation) + '" service tag is missing in your NSG for port 9400 for Kafka REST Proxy. For port 9400, you need to add this regional service tag (or the global "HDInsight" service tag)')
                        else:
                            printAndLog(self, Fore.GREEN + '    ✔ : "' + str(serviceTagValidation) + '" is ok in your NSG for port 9400 for Kafka REST Proxy')

                if isPort9400okWithAllHDInsightRegionalTags:
                    # 9400 is ok with regional tags but 443 is missing
                    for serviceTagValidation in serviceTagValidationsFor443:
                        printAndLog(self, "For 443 : " + serviceTagValidation + " " + str(serviceTagValidationsFor443[serviceTagValidation]))
                        if serviceTagValidationsFor443[serviceTagValidation] == False:
                            printAndLog(self, Fore.RED + '    ✖ : "' + str(serviceTagValidation) + '" service tag is missing in your NSG for port 443. For port 443, you need to add this regional service tag (or the global "HDInsight" service tag)')
                        else:
                            printAndLog(self, Fore.GREEN + '    ✔ : "' + str(serviceTagValidation) + '" is ok in your NSG for port 443')

                # TODO
                # if ...
    else:  # No Kafka Rest Proxy
        if all(x == True for x in serviceTagValidationsFor443.values()):
            if self.verboseMode:
                printAndLog(self, '  You are using "regional tags" for port 443')
            return True
        else:
            if self.verboseMode:
                for serviceTagValidation in serviceTagValidationsFor443:
                    if serviceTagValidationsFor443[serviceTagValidation] == False:
                        printAndLog(self, Fore.RED + '    ✖ : "' + str(serviceTagValidation) + '" service tag is missing in your NSG for port 443. For port 443, you need to add this regional service tag (or the global "HDInsight" service tag)')
                    else:
                        printAndLog(self, Fore.GREEN + '    ✔ : "' + str(serviceTagValidation) + '" is ok in your NSG')

    return False


def checkSubnetNSGRulesForHDIMEIPs(self):
    """Checks the Subnet NSG rules for 4 "global" + 2 "regional" HDIME IPs. Ref: https://docs.microsoft.com/en-us/azure/hdinsight/hdinsight-management-ip-addresses"""
    resultDict = {}
    printAndLog(self, "  As you haven't used any HDInsight service tag in the subnet NSG, checking HDInsight Management Endpoint (HDIME) IPs in subnet NSG")
    current_subnet_nsg_rules = getSubnetNSGRules(self)

    # Temp dict to store if an HDIME IP is added or not
    HDIMEIPValidationsFor443 = {}
    isAllHDIMEIPsOKForPort443 = False
    # Similar dict If Kafka Rest Proxy is enabled
    if self.kafkaRestProxyEnabled:
        HDIMEIPValidationsFor9400 = {}
        isAllHDIMEIPsOKForPort9400 = False

    # Initialize the dict with False for each HDIME IP. We will put 4 global + 2 regional HDIME IPs together into the same dict
    # Start with 4 global
    for HDIME_IP in self.params["FOUR_GLOBAL_HDIME_IPS"]:
        # HDIMEIPValidationsFor443[HDIME_IP] = False
        tmpHDIMEIPNSGCheckResult = HDIMEIPNSGCheckResult(False, str(HDIME_IP), 443, "Global")
        HDIMEIPValidationsFor443[HDIME_IP] = tmpHDIMEIPNSGCheckResult

        if self.kafkaRestProxyEnabled:
            # HDIMEIPValidationsFor9400[HDIME_IP] = False
            tmpHDIMEIPNSGCheckResult = HDIMEIPNSGCheckResult(False, str(HDIME_IP), 9400, "Global")
            HDIMEIPValidationsFor9400[HDIME_IP] = tmpHDIMEIPNSGCheckResult

    # Do the same for 2 regional
    for HDIME_IP in self.CURRENT_REGION_HDIME_IPS:
        # HDIMEIPValidationsFor443[HDIME_IP] = False
        tmpHDIMEIPNSGCheckResult = HDIMEIPNSGCheckResult(False, str(HDIME_IP), 443, "Regional")
        HDIMEIPValidationsFor443[HDIME_IP] = tmpHDIMEIPNSGCheckResult

        if self.kafkaRestProxyEnabled:
            # HDIMEIPValidationsFor9400[HDIME_IP] = False
            tmpHDIMEIPNSGCheckResult = HDIMEIPNSGCheckResult(False, str(HDIME_IP), 9400, "Regional")
            HDIMEIPValidationsFor9400[HDIME_IP] = tmpHDIMEIPNSGCheckResult

    if self.verboseMode:
        # Store the NSG rules in a PrettyTable, to return it from this function back
        pt = PrettyTable(["Priority", "Rule Name", "Direction", "Source Address Prefix", "Destination Port Range"])
        # pt.align["Destination Port Range"] = "r"

    for security_rule in current_subnet_nsg_rules:
        if self.verboseMode:
            # Highlight HDInsight service tags
            if "HDInsight" in security_rule.source_address_prefix:
                pt.add_row([str(security_rule.priority), security_rule.name, security_rule.direction, Fore.GREEN + security_rule.source_address_prefix + Style.RESET_ALL, str(security_rule.destination_port_range)])
            else:
                pt.add_row([str(security_rule.priority), security_rule.name, security_rule.direction, security_rule.source_address_prefix, str(security_rule.destination_port_range)])

        currentIP = ""
        isSourceAddressPrefixOK = False
        # Check if customer is using "CIDR syntax" or "IP syntax"
        if "/" in security_rule.source_address_prefix:
            # Customer is using "CIDR syntax" in NSG rule

            # Check if it's a "global" HDIME IP
            for requiredHDIMEIP in self.params["FOUR_GLOBAL_HDIME_IPS"]:
                if IPAddress(requiredHDIMEIP) in IPNetwork(security_rule.source_address_prefix):
                    isSourceAddressPrefixOK = True
                    currentIP = requiredHDIMEIP
                    break

            # Check if it's a "regional" HDIME IP
            for requiredHDIMEIP in self.CURRENT_REGION_HDIME_IPS:
                if IPAddress(requiredHDIMEIP) in IPNetwork(security_rule.source_address_prefix):
                    isSourceAddressPrefixOK = True
                    currentIP = requiredHDIMEIP
                    break
        else:
            # Customer is using "IP syntax" in NSG rule

            # Check if it's a "global" HDIME IP
            for requiredHDIMEIP in self.params["FOUR_GLOBAL_HDIME_IPS"]:
                if requiredHDIMEIP == security_rule.source_address_prefix:
                    isSourceAddressPrefixOK = True
                    currentIP = requiredHDIMEIP
                    break

            # Check if it's a "regional" HDIME IP
            for requiredHDIMEIP in self.CURRENT_REGION_HDIME_IPS:
                if requiredHDIMEIP == security_rule.source_address_prefix:
                    isSourceAddressPrefixOK = True
                    currentIP = requiredHDIMEIP
                    break

        if isSourceAddressPrefixOK and (security_rule.destination_port_range == "443" or security_rule.destination_port_range == "*") and (security_rule.direction == "Inbound"):
            # HDIMEIPValidationsFor443[currentIP] = True
            if str(currentIP) in self.params["FOUR_GLOBAL_HDIME_IPS"]:
                tmpHDIMEIPNSGCheckResult = HDIMEIPNSGCheckResult(True, str(currentIP), 443, "Global")
            else:
                tmpHDIMEIPNSGCheckResult = HDIMEIPNSGCheckResult(True, str(currentIP), 443, "Regional")
            HDIMEIPValidationsFor443[currentIP] = tmpHDIMEIPNSGCheckResult

        if self.kafkaRestProxyEnabled:
            if isSourceAddressPrefixOK and (security_rule.destination_port_range == "9400" or security_rule.destination_port_range == "*") and (security_rule.direction == "Inbound"):
                # HDIMEIPValidationsFor9400[security_rule.source_address_prefix] = True
                if str(currentIP) in self.CURRENT_REGION_HDIME_IPS:
                    tmpHDIMEIPNSGCheckResult = HDIMEIPNSGCheckResult(True, str(currentIP), 9400, "Global")
                else:
                    tmpHDIMEIPNSGCheckResult = HDIMEIPNSGCheckResult(True, str(currentIP), 9400, "Regional")
                HDIMEIPValidationsFor9400[security_rule.source_address_prefix] = tmpHDIMEIPNSGCheckResult

    if self.verboseMode:
        # printAndLog(self, pt)
        resultDict["allNSGRulesInPrettyTable"] = pt

    # if all(x == True for x in HDIMEIPValidationsFor443.values()):
    if all(x.isOk == True for x in HDIMEIPValidationsFor443.values()):
        isAllHDIMEIPsOKForPort443 = True

    if self.kafkaRestProxyEnabled:
        # print("9400: " + str(HDIMEIPValidationsFor9400))
        # if all(x == True for x in HDIMEIPValidationsFor9400.values()):
        if all(x.isOk == True for x in HDIMEIPValidationsFor9400.values()):
            isAllHDIMEIPsOKForPort9400 = True

    # resultDict["443"] = isAllHDIMEIPsOKForPort443
    resultDict["443"] = HDIMEIPValidationsFor443
    if self.kafkaRestProxyEnabled:
        # resultDict["9400"] = isAllHDIMEIPsOKForPort9400
        resultDict["9400"] = HDIMEIPValidationsFor9400

    return resultDict


# #Check if the "childCIDR" is child of "parentCIDR". For example; it returns true if parentCIDR=10.70.0.0/16 and childCIDR=10.70.2.0/24, returns True
# def checkIfSourceCIDRwithinTargetCIDR(childCIDR, parentCIDR):

#     if IPNetwork(childCIDR) in IPNetwork(parentCIDR):
#         return True
#     else:
#         return False


def getNetworkWatcher(self, theSpinner):
    """Get Azure Azure Network Watcher"""
    RESOURCE_GROUP_NW = "NetworkWatcherRG"
    current_nw = None

    # Get the network watchers in subscription, if any
    networkWatchers = self.network_client.network_watchers.list(RESOURCE_GROUP_NW)
    for networkWatcher in networkWatchers:
        # printAndLog(self, networkWatcher.name + ' ' + networkWatcher.location)
        if networkWatcher.location == self.regionName:
            current_nw = networkWatcher
            break

    if current_nw == None:
        # printAndLog(self, 'Couldn\'t find a network watcher in subscription. Will look for network watcher in the current resource group')
        # Get the network watchers in resource group
        networkWatchers = self.network_client.network_watchers.list(self.current_vm_rg.name)

        for networkWatcher in networkWatchers:
            # printAndLog(self, networkWatcher.name + ' ' + networkWatcher.location)
            if networkWatcher.location == self.regionName:
                current_nw = networkWatcher
                break

    if current_nw == None:
        if self.verboseMode:
            printAndLog(self, "Couldn't find a network watcher in subscription or resource group. Creating one in current VM's resource group " + self.current_vm.id.split("/")[4] + " ...")
        # No NW found in the "self.regionName". We need to create a NW
        nwCreateJSON = {"location": self.regionName}
        current_nw = self.network_client.network_watchers.create_or_update(self.current_vm_rg.name, NETWORK_WATCHER_NAME_PREFIX + generateCharacters(5), nwCreateJSON)

        # Because there is no begin_create_or_update method for network_watchers to poll the status, we are waiting for 5 seconds to allow some time for network watcher creation
        time.sleep(5)

        # printAndLog(self, current_nw)
    return current_nw


# Contains retry-logic
def doSafeNetworkWatcherVerifyIpFlowCheck(self, vifParams, showSpinner=True):
    """Do Verify IP Flow check, with retry-logic"""
    RETRY_LIMIT = 5
    retry_count = 1
    while retry_count <= RETRY_LIMIT:
        retry_count = retry_count + 1
        result = doNetworkWatcherVerifyIpFlowCheck(self, vifParams, showSpinner=True)
        if result.access == "Unknown":
            printAndLog(self, " Retry #" + str(retry_count) + " of " + str(RETRY_LIMIT))
        else:
            return result


def doNetworkWatcherVerifyIpFlowCheck(self, vifParams, showSpinner=True):
    """Do Verify IP Flow check"""
    current_nw_rg_name = self.current_nw.id.split("/")[4]
    # begin_verify_ip_flow() method's first param current_nw_rg is the RG of the NW. But "vifParams" should contain the RG for the VM!
    vif = self.network_client.network_watchers.begin_verify_ip_flow(current_nw_rg_name, self.current_nw.name, vifParams)
    result = vif.result()
    return result


def doNetworkWatcherVerifyIpFlowCheckFromHDIMEIP(self, remote_ip, showSpinner=True):
    vifParams = {
        "target_resource_id": "/subscriptions/" + self.subscription_id + "/resourceGroups/" + self.current_vm.id.split("/")[4] + "/providers/Microsoft.Compute/virtualMachines/" + self.current_vm.name + "",
        "direction": "Inbound",
        "protocol": "TCP",
        "local_port": "443",
        "remote_port": "*",
        "local_ip_address": self.current_vm_ip,
        "remote_ip_address": remote_ip,
    }

    vifResult = doSafeNetworkWatcherVerifyIpFlowCheck(self, vifParams, showSpinner=True)
    return vifResult


def getNextHop(self, destinationIP):
    # NextHop check
    # https://docs.microsoft.com/en-us/azure/network-watcher/network-watcher-next-hop-overview
    # https://github.com/Azure/azure-sdk-for-python/blob/azure-mgmt-network_18.0.0/sdk/network/azure-mgmt-network/tests/test_cli_mgmt_network_watcher.py#L785
    # printAndLog(self, 'Checking NextHop set for current subnet ...' )
    nextHopParams = {
        "target_resource_id": "/subscriptions/" + self.subscription_id + "/resourceGroups/" + self.current_vm_rg.name + "/providers/Microsoft.Compute/virtualMachines/" + self.current_vm.name + "",
        "source_ip_address": self.current_vm_ip,
        "destination_ip_address": destinationIP,
    }
    nexthop_from_current_vm = self.network_client.network_watchers.begin_get_next_hop(self.current_nw_rg_name, self.current_nw.name, nextHopParams)
    nexthop_result = nexthop_from_current_vm.result()

    # write the result to params.conf file
    f = open("config/params.conf", "r")
    lines = f.readlines()
    line_index = -1
    for line in lines:
        line_index = line_index + 1
        if line.startswith("NEXTHOP_CHECK_RESULT"):
            lines[line_index] = 'NEXTHOP_CHECK_RESULT="' + str(nexthop_result.next_hop_type) + '"\n'
        if line.startswith("NEXTHOP_CHECK_DATETIME"):
            lines[line_index] = 'NEXTHOP_CHECK_DATETIME="' + str(time.time()) + '"\n'

    f = open("config/params.conf", "w")
    f.writelines(lines)
    f.close()
    return nexthop_result


def deleteNetworkWatcher(self):
    # printAndLog(self,'Confirm if you want to delete the Network Watcher named "' + self.current_nw.name + '"')
    printAndLog(self, 'Deleting network watcher named "' + self.current_nw.name + '" ...')
    deletionResult = self.network_client.network_watchers.begin_delete(self.current_nw_rg_name, self.current_nw.name)

    # result = deletionResult.result()
    # printAndLog(self,result)

    spinner = Spinner("Deleting ...")
    while deletionResult.status() == "InProgress":
        time.sleep(0.1)
        spinner.next()
    printAndLog(self, "")
    printAndLog(self, '"' + self.current_nw.name + '" network watcher has been deleted')
