from lib.utils import *
from netaddr import *
from prettytable import PrettyTable


def getAzureFirewall(self):
    """Check if the the next hop ip belongs to an Azure Firewall in the subscription and return the Azure Firewall if any"""

    azure_firewall = None
    # Get all the Azure Firewalls in the subscription and match the private ip address of an Azure Firewall with the private ip found above in the UDR routes via getNextHopIP method
    azure_firewalls_in_subscription = self.network_client.azure_firewalls.list_all()
    for azure_firewall in azure_firewalls_in_subscription:
        if azure_firewall.ip_configurations[0].private_ip_address == self.current_next_hop_ip:
            break
    return azure_firewall


def checkAzureFirewallRulesForAllowAllOutbound(self):
    """Check If there is an "allow all outbound" rule. If this is set, rule '2,3,4,5,6' won't be required. Ref : https://docs.microsoft.com/en-us/azure/hdinsight/hdinsight-restrict-outbound-traffic"""

    # Check Network_Rule_Collections
    for network_rule_collection in self.azure_fw.network_rule_collections:
        # printAndLog(self,'NRC name: ' + network_rule_collection.name + ', action: ' + network_rule_collection.action.type)
        for rule in network_rule_collection.rules:
            # printAndLog(self,'     ' + str(rule))
            if (("TCP" in rule.protocols) or ("Any" in rule.protocols)) and ("*" in rule.destination_ports) and ("*" in rule.destination_addresses):
                if ("*" in rule.source_addresses) or (IPNetwork(self.current_subnet.address_prefix) in IPNetwork(rule.source_addresses)):
                    if self.verboseMode:
                        printAndLog(self, '  The rule named "' + rule.name + '" under "' + network_rule_collection.name + '" network rule collection allows all outbound access')
                    return True
    return False


def checkAzureFirewallRule1(therule):
    """Checks if 'WindowsUpdate' and 'HDInsight' FQDN tags are set or not in given ApplicationRule rule. Ref : https://docs.microsoft.com/en-us/azure/hdinsight/hdinsight-restrict-outbound-traffic"""

    result = False
    if "*" in therule.source_addresses and "HDInsight" in therule.fqdn_tags and "WindowsUpdate" in therule.fqdn_tags:
        result = True
    return result


def checkAzureFirewallRule2or3or4(therule, theTargetFQDN):
    """Checks if 'theTargetFQDN' target FQDN is set (with protocol_type 'Https' and port '443') or not in given ApplicationRule rule. Ref : https://docs.microsoft.com/en-us/azure/hdinsight/hdinsight-restrict-outbound-traffic"""

    result = False
    if theTargetFQDN in therule.target_fqdns:
        for protocol in therule.protocols:
            if "*" in therule.source_addresses and protocol.protocol_type == "Https" and protocol.port == 443:
                result = True
    return result


def checkAzureFirewallRule5or6(therule, theServiceTag, theDestinationPort):
    """Checks if "theServiceTag" service tag is set (with "*" source address and "theDestinationPorts" destination ports) in givien NetworkRule rule. Ref : https://docs.microsoft.com/en-us/azure/hdinsight/hdinsight-restrict-outbound-traffic"""

    result = False
    if theServiceTag in therule.destination_addresses:
        if "*" in therule.source_addresses and theDestinationPort in therule.destination_ports:
            if "TCP" in therule.protocols or "Any" in therule.protocols:
                result = True
    return result


# To avoid asymmetric routing for (HDInsight Management Endpoint) HDIME IPs, we need to make sure that we are allowing "Outbound" traffic back to 6 HDIME IPs (6 = 4 Global + 2 Regional)
# Ref: https://docs.microsoft.com/en-us/azure/hdinsight/hdinsight-restrict-outbound-traffic#create-and-configure-a-route-table
# Returns True if;
#  + Customer added ServiceTags into UDR (PREVIEW!)
#  or
#  + If route table has "Internet" NextHop to 4 "Global" HDIME AND 2 regional HDIME IPs
def checkRouteTableforAzureFirewall(self):

    NSGinUDRcheckResult = False  # Check1
    FourGlobalIPsinUDRCheckResult = False
    RegionalIPsinUDRCheckResult = False

    result = False

    routesCheckGlobal = {}
    routesCheckRegional = {}

    # CHECK1 :
    # PREVIEW: Customers can use ServiceTags in route tables instead of putting 4+2 IPs
    # ADD  : az network route-table route create -g farukc-RG --route-table-name farukc-udr-1 -n myHDInsightEastUSroute --address-prefix HDInsight.EastUS --next-hop-type Internet
    # DELETE: az network route-table route delete -g "farukc-RG" --route-table-name "farukc-udr-1" -n myHDInsightEastUSroute
    # Ref: https://docs.microsoft.com/en-us/azure/virtual-network/virtual-networks-udr-overview#service-tags-for-user-defined-routes-preview
    # Check if customer defined global "HDInsight" service tag or the "requiredServiceTags" in route table

    # Check if there is any service tag containing "HDInsight" keyword is added into any routes
    usingHDInsightServiceTaginUDR = False
    for route in self.current_route_table.routes:
        if "HDInsight" in route.address_prefix:
            # Found "HDInsight" keyword in at least one route
            usingHDInsightServiceTaginUDR = True
            break

    if usingHDInsightServiceTaginUDR:
        # Check if the global "HDInsight" tag is added already
        for route in self.current_route_table.routes:
            if (route.address_prefix == "HDInsight") and (route.next_hop_type == "Internet"):
                NSGinUDRcheckResult = True

        # Check if "requiredServiceTags" are added in to the route table
        # Create a temp dict for checks
        requiredServiceTagsToCheck = {}
        for requiredServiceTag in self.requiredServiceTags:
            requiredServiceTagsToCheck[self.requiredServiceTags[requiredServiceTag]] = False

        for requiredServiceTagToCheck in requiredServiceTagsToCheck:
            for route in self.current_route_table.routes:
                if (route.address_prefix == requiredServiceTagToCheck) and (route.next_hop_type == "Internet"):
                    requiredServiceTagsToCheck[requiredServiceTagToCheck] = True

        for requiredServiceTagToCheck in requiredServiceTagsToCheck:
            if requiredServiceTagsToCheck[requiredServiceTagToCheck] == False:
                printAndLog(self, '    + You are missing the "' + requiredServiceTagToCheck + '" service tag in your UDR. KO!')
                NSGinUDRcheckResult = False
    else:
        # Customer is not using HDInsight service tags in route table (preview feature)! We'll need to check the HDIME IPs instead
        if self.verboseMode:
            printAndLog(self, "   + You are not using HDInsight service tags in route table!")

    # Check if 4 Global HDIME IPs exists in route table and pointed to "Internet" next hop
    for global_hdime_ip in self.params["FOUR_GLOBAL_HDIME_IPS"]:
        routesCheckGlobal[global_hdime_ip] = False
        for route in self.current_route_table.routes:
            if global_hdime_ip in route.address_prefix and route.next_hop_type == "Internet":
                routesCheckGlobal[global_hdime_ip] = True

    # If all "Global" HDIME IPs are added in UDR
    if all(routesCheckGlobal[routesCheck] == True for routesCheck in routesCheckGlobal):
        FourGlobalIPsinUDRCheckResult = True
    elif self.verboseMode:
        for global_hdime_ip in routesCheckGlobal:
            if routesCheckGlobal[global_hdime_ip] == False:
                printAndLog(self, '   "' + str(global_hdime_ip) + '" Global HDInsight Management Endpoint IP is not correctly set in your UDR. KO!')
            else:
                printAndLog(self, '   "' + str(global_hdime_ip) + '" Global HDInsight Management Endpoint IP is added in your UDR to be routed to "Internet". OK!')

    # Same check for 2 regional HDIME IPs (or 4 for China North and China South)
    #
    # regionalHDMEIPs = getRegionalHDIMEIPsByRegionName(self, 'chinanorth')
    regionalHDMEIPs = getRegionalHDIMEIPsByRegionName(self, self.regionName)

    for regional_hdime_ip in regionalHDMEIPs:
        routesCheckRegional[regional_hdime_ip] = False
        for route in self.current_route_table.routes:
            # printAndLog(self,route)
            if regional_hdime_ip in route.address_prefix and route.next_hop_type == "Internet":
                routesCheckRegional[regional_hdime_ip] = True

    # If all "Regional" HDIME IPs are added in UDR
    if all(routesCheckRegional[routesCheck] == True for routesCheck in routesCheckRegional):
        RegionalIPsinUDRCheckResult = True
    elif self.verboseMode:
        for global_hdime_ip in routesCheckRegional:
            if routesCheckRegional[global_hdime_ip] == False:
                printAndLog(self, '   "' + str(global_hdime_ip) + '" Regional HDInsight Management Endpoint IP is not correctly set in your UDR. KO!')
            else:
                printAndLog(self, '   "' + str(global_hdime_ip) + '" Regional HDInsight Management Endpoint IP is added in your UDR to be routed to "Internet". OK!')

    if NSGinUDRcheckResult or (FourGlobalIPsinUDRCheckResult and RegionalIPsinUDRCheckResult):
        result = True

    return result


def checkAzureFirewallRules(self):
    # Logic source: from https://docs.microsoft.com/en-us/azure/hdinsight/hdinsight-restrict-outbound-traffic

    # Below list will contain the "AzureFirewallRuleCheckResult" objects for each rule
    azureFirewallRuleCheckResults = []

    # Check if there is a rule in any network rule collection that is allowing all outbound traffic
    self.allowAllOutboundRuleExistsInAzureFirewall = checkAzureFirewallRulesForAllowAllOutbound(self)

    # Check if customer allowed traffic to Azure DNS if customer is using Azure DNS (allow access to 168.63.129.16 on port 53 for both TCP and UDP)
    # Ref: https://docs.microsoft.com/en-us/azure/hdinsight/hdinsight-management-ip-addresses#azure-dns-service

    azureDNSCheck = False
    # if not(self.vnet_is_using_custom_dns):
    #    printAndLog(self,'    + As you are using Azure DNS checking if you have allowed access to Azure DNS 168.63.129.16 on port 53 for both TCP and UDP')
    if self.verboseMode:
        printAndLog(self, "  Azure DNS check in Azure Firewall rules...", end="")
    if self.allowAllOutboundRuleExistsInAzureFirewall:
        azureDNSCheck = True
        if self.verboseMode:
            printAndLog(self, '   As you already have "allow all outbound traffic" rule in your Azure Firewall, Azure DNS firewall rule is also OK!')
    else:
        for network_rule_collection in self.azure_fw.network_rule_collections:
            for rule in network_rule_collection.rules:
                if ("168.63.129.16" in rule.destination_addresses) and ("*" in rule.source_addresses) and ("53" in rule.destination_ports or "*" in rule.destionation_ports):
                    if ("Any" in rule.protocols) or ("TCP" in rule.protocols and "UDP" in rule.protocols):
                        azureDNSCheck = True
                        if self.verboseMode:
                            printAndLog(self, "   Azure DNS firewall rule is OK!")

    rule1Check = False
    rule2Check = False
    rule3Check = False
    # Check Application_Rule_Collections
    if self.verboseMode:
        printAndLog(self, "  Checking Application Rule Collections ...")
    for application_rule_collection in self.azure_fw.application_rule_collections:
        if application_rule_collection.action.type == "Allow":
            for rule in application_rule_collection.rules:
                if checkAzureFirewallRule1(rule) == True:
                    rule1Check = True
                    # (self, direction, priority, name, source_addresses, protocols, target_fqdns, fqdn_tags, destination_addresses, destination_ports, destination_fqdns, ruleNameinDocs, isOK):
                    # "✖", "✔"
                    tmpProtocolsString = ""
                    for protocol in rule.protocols:
                        tmpProtocolsString = tmpProtocolsString + " " + str(protocol.protocol_type) + ":" + str(protocol.port)
                    tmpAzureFirewallRuleCheckResult = AzureFirewallRuleCheckResult(rule.additional_properties["direction"], rule.name, rule.source_addresses, tmpProtocolsString, rule.target_fqdns, rule.fqdn_tags, "", "", "", "Rule 1", "✔")
                    azureFirewallRuleCheckResults.append(tmpAzureFirewallRuleCheckResult)

                    if self.verboseMode:
                        printAndLog(self, " " + '  + Rule1 : "HDInsight" and "WindowsUpdate" FQDN tags are OK!')

                if checkAzureFirewallRule2or3or4(rule, "login.windows.net") == True:
                    rule2Check = True
                    tmpProtocolsString = ""
                    for protocol in rule.protocols:
                        tmpProtocolsString = tmpProtocolsString + " " + str(protocol.protocol_type) + ":" + str(protocol.port)
                    tmpAzureFirewallRuleCheckResult = AzureFirewallRuleCheckResult(rule.additional_properties["direction"], rule.name, rule.source_addresses, tmpProtocolsString, rule.target_fqdns, rule.fqdn_tags, "", "", "", "Rule 2", "✔")
                    azureFirewallRuleCheckResults.append(tmpAzureFirewallRuleCheckResult)

                    if self.verboseMode:
                        printAndLog(self, " " + "  + Rule2 : login.windows.net Target FQDN is set. OK!")

                if checkAzureFirewallRule2or3or4(rule, "login.microsoftonline.com") == True:
                    rule3Check = True
                    tmpProtocolsString = ""
                    for protocol in rule.protocols:
                        tmpProtocolsString = tmpProtocolsString + " " + str(protocol.protocol_type) + ":" + str(protocol.port)
                    tmpAzureFirewallRuleCheckResult = AzureFirewallRuleCheckResult(rule.additional_properties["direction"], rule.name, rule.source_addresses, tmpProtocolsString, rule.target_fqdns, rule.fqdn_tags, "", "", "", "Rule 3", "✔")
                    azureFirewallRuleCheckResults.append(tmpAzureFirewallRuleCheckResult)
                    if self.verboseMode:
                        printAndLog(self, " " + "  + Rule3 : login.microsoftonline.com Target FQDN is set. OK!")

                if checkAzureFirewallRule2or3or4(rule, "blob.core.windows.net") == True:
                    rule4Check = True
                    tmpProtocolsString = ""
                    for protocol in rule.protocols:
                        tmpProtocolsString = tmpProtocolsString + " " + str(protocol.protocol_type) + ":" + str(protocol.port)
                    tmpAzureFirewallRuleCheckResult = AzureFirewallRuleCheckResult(rule.additional_properties["direction"], rule.name, rule.source_addresses, tmpProtocolsString, rule.target_fqdns, rule.fqdn_tags, "", "", "", "Rule 4", "✔")
                    azureFirewallRuleCheckResults.append(tmpAzureFirewallRuleCheckResult)
                    if self.verboseMode:
                        printAndLog(self, " " + "  + Rule4 : blob.core.windows.net Target FQDN is set. OK!")

                # if (checkAzureFirewallRule2or3or4(rule, 'dfs.core.windows.net') == True):
                #     if self.verboseMode:
                #         printAndLog(self,'   ' + '  + Rule4 : dfs.core.windows.net Target FQDN is set. OK!')

    rule5aCheck = False
    rule5bCheck = False
    rule6Check = False
    # Check Network_Rule_Collections
    if self.verboseMode:
        printAndLog(self, "  Checking Network Rule Collections ...")
    for network_rule_collection in self.azure_fw.network_rule_collections:
        # printAndLog(self,'   ' + '  NRC name: ' + network_rule_collection.name + ', action: ' + network_rule_collection.action.type)
        for rule in network_rule_collection.rules:
            if checkAzureFirewallRule5or6(rule, "Sql", "1433") == True:
                rule5aCheck = True
                tmpProtocolsString = ""
                for protocol in rule.protocols:
                    tmpProtocolsString = tmpProtocolsString + " " + str(protocol)
                tmpAzureFirewallRuleCheckResult = AzureFirewallRuleCheckResult("", rule.name, rule.source_addresses, tmpProtocolsString, "", "", rule.destination_addresses, rule.destination_ports, rule.destination_fqdns, "Rule 5a", "✔")
                azureFirewallRuleCheckResults.append(tmpAzureFirewallRuleCheckResult)
                if self.verboseMode:
                    printAndLog(self, " " + "  + Rule5, SQL 1433. OK!")

            if checkAzureFirewallRule5or6(rule, "Sql", "11000-11999") == True:
                rule5bCheck = True
                tmpProtocolsString = ""
                for protocol in rule.protocols:
                    tmpProtocolsString = tmpProtocolsString + " " + str(protocol)
                tmpAzureFirewallRuleCheckResult = AzureFirewallRuleCheckResult("", rule.name, rule.source_addresses, tmpProtocolsString, "", "", rule.destination_addresses, rule.destination_ports, rule.destination_fqdns, "Rule 5b", "✔")
                azureFirewallRuleCheckResults.append(tmpAzureFirewallRuleCheckResult)
                if self.verboseMode:
                    printAndLog(self, " " + "  + Rule5, SQL 11000-11999. OK!")

            if checkAzureFirewallRule5or6(rule, "AzureMonitor", "*") == True:
                rule6Check = True
                tmpProtocolsString = ""
                for protocol in rule.protocols:
                    tmpProtocolsString = tmpProtocolsString + " " + str(protocol)
                tmpAzureFirewallRuleCheckResult = AzureFirewallRuleCheckResult("", rule.name, rule.source_addresses, tmpProtocolsString, "", "", rule.destination_addresses, rule.destination_ports, rule.destination_fqdns, "Rule 6", "✔")
                azureFirewallRuleCheckResults.append(tmpAzureFirewallRuleCheckResult)
                if self.verboseMode:
                    printAndLog(self, " " + "  + Rule6, AzureMonitor * . OK!")

    udrCheck = False
    if checkRouteTableforAzureFirewall(self):
        udrCheck = True
        if self.verboseMode:
            printAndLog(self, ' "' + Fore.GREEN + self.current_route_table.name + Style.RESET_ALL + '" route table is OK!')

    if self.verboseMode:
        printAndLog(self, "Azure Firewall Rules related to HDInsight : ")
        pt = PrettyTable(["Direction", "Name", "Source_addresses", "Protocols", "Target_FQDNs", "FQDN_tags", "Destination_addresses", "Destination_ports", "Destination_FQDNs", "RuleNameinDocs", "isOK"])
        for azureFirewallCheckResult in azureFirewallRuleCheckResults:
            pt.add_row([azureFirewallCheckResult.direction, azureFirewallCheckResult.name, azureFirewallCheckResult.source_addresses, azureFirewallCheckResult.protocols, azureFirewallCheckResult.target_fqdns, azureFirewallCheckResult.fqdn_tags, azureFirewallCheckResult.destination_addresses, azureFirewallCheckResult.destination_ports, azureFirewallCheckResult.destination_fqdns, azureFirewallCheckResult.ruleNameinDocs, azureFirewallCheckResult.isOK])
        print("")
        printAndLog(self, pt)

    if (azureDNSCheck and rule1Check and rule2Check and rule3Check and rule5aCheck and rule5bCheck and rule6Check and udrCheck) or (azureDNSCheck and rule1Check and rule2Check and rule3Check and (self.isAzureSQLOutboundAllowedByServiceEndpoint) and rule6Check and udrCheck):
        return True
    else:
        return False
