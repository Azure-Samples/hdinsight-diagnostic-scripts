#!/bin/bash
<<COMMENT
This script is to validate the network connectivity needed to successfully deploy your HDInsight cluster.
COMMENT

#Read the parameters file
. params.txt

ERROR_COUNT=0

#Get the HDInsight Management IP files from Azure storage account
wget -O HDInsightManagementIPs_$region.txt https://hdidiagscripts.blob.core.windows.net/data/HDInsightManagementIPs_$region.txt

#Loop for checking HDInsight Management IPs by region
regionFile="HDInsightManagementIPs_$region.txt"

<<COMMENT
##This section tests the outbound connectivity to the HDInsight Management IPs for the region where the HDInsight cluster would be deployed. Need to check with HDInsight Control Plane Engineers on why outbound connections fail to some of the Management IPs. Until that is confirmed, DO NOT USE THIS SECTION!##
while IFS= read -r line
do
  printf '*****************************************************************\n\n'
  echo "Testing connectivity to IP $line in $region"
  ncResult="$(nc -vz -w 5 $line 443 2>&1)"
if grep -q "succeeded" <<< "$ncResult"; then
  echo "Connection to IP $line in $region was successful"
else
  echo "Connection to IP $line in $region failed. Verify that any Network Security Group (NSG), User-Defined Routes (UDR), or firewall has the IP $line as allowed on TCP port 443"
fi
done < "$regionFile"
COMMENT

#Validate Custom Ambari DB
printf '*****************************************************************\n\n'
if [ ! -z "$AMBARIDB" ]; then
	echo "Validating connectivity to custom Ambari DB: $AMBARIDB.database.windows.net" 
	AmbariErr="$(nc -vz -w 5 $AMBARIDB.database.windows.net 1433 2>&1)"
	if grep -q "succeeded" <<< "$AmbariErr"; then
	echo "Connection to custom Ambari DB $AMBARIDB successful"
	printf '***************************************************************\n\n'
	else
	ERROR_COUNT=$[ERROR_COUNT + 1]
	echo "ERROR: Connection to custom Ambari DB $AMBARIDB failed. Since you are using a custom SQL server for Ambari, then you need to allow the traffic to your own custom SQL Servers.\nVerify that any Network Security Group (NSG), User-Defined Routes (UDR), or firewall allows traffic on TCP port 1433 in outbound direction.\nOne option is to configure Service Endpoints for SQL Server on the HDInsight virtual network. For more information see https://docs.microsoft.com/azure/azure-sql/database/vnet-service-endpoint-rule-overview. If you are using a firewall, configure a network rule in the Service Tags section for SQL that will allow you to log and audit SQL traffic. For more information see https://docs.microsoft.com/azure/hdinsight/hdinsight-restrict-outbound-traffic#configure-the-firewall-with-network-rules."
	printf '***************************************************************\n\n'
    fi
else
	echo "No custom Ambari DB defined"
	printf '***************************************************************\n\n'
fi

#Validate Custom Hive DB
if [ ! -z "$HIVEDB" ]; then 
	echo "Validating connectivity to custom Hive DB: $HIVEDB.database.windows.net" 
	HiveErr="$(nc -vz -w 5 $HIVEDB.database.windows.net 1433 2>&1)"
	if grep -q "succeeded" <<< "$HiveErr"; then
	echo "Connection to custom Hive DB $HIVEDB successful"
	printf '***************************************************************\n\n'
	else
	ERROR_COUNT=$[ERROR_COUNT + 1]
	echo "ERROR: Connection to custom Hive DB $HIVEDB failed. Since you are using a custom SQL server for Hive metastore, then you need to allow the traffic to your own custom SQL Servers.\nVerify that any Network Security Group (NSG), User-Defined Routes (UDR), or firewall allows traffic on TCP port 1433 in outbound direction.\nOne option is to configure Service Endpoints for SQL Server on the HDInsight virtual network. For more information see https://docs.microsoft.com/azure/azure-sql/database/vnet-service-endpoint-rule-overview. If you are using a firewall, configure a network rule in the Service Tags section for SQL that will allow you to log and audit SQL traffic. For more information see https://docs.microsoft.com/azure/hdinsight/hdinsight-restrict-outbound-traffic#configure-the-firewall-with-network-rules."
	printf '***************************************************************\n\n'
    fi
else
	echo "No custom Hive DB defined"
	printf '***************************************************************\n\n'
fi

#Validate Custom OOZIE DB
if [ ! -z "$OOZIEDB" ]; then 
	echo "Validating connectivity to custom OOZIE DB: $OOZIEDB.database.windows.net" 
	OozieErr="$(nc -vz -w 5 $OOZIEDB.database.windows.net 1433 2>&1)"
	if grep -q "succeeded" <<< "$OozieErr"; then
	echo "Connection to custom Oozie DB $OOZIEDB successful"
	printf '***************************************************************\n\n'
	else
	ERROR_COUNT=$[ERROR_COUNT + 1]
	echo "ERROR: Connection to custom Ooze DB $OOZIEDB failed. Since you are using a custom SQL server for Oozie metastore, then you need to allow the traffic to your own custom SQL Servers.\nVerify that any Network Security Group (NSG), User-Defined Routes (UDR), or firewall allows traffic on TCP port 1433 in outbound direction.\nOne option is to configure Service Endpoints for SQL Server on the HDInsight virtual network. For more information see https://docs.microsoft.com/azure/azure-sql/database/vnet-service-endpoint-rule-overview. If you are using a firewall, configure a network rule in the Service Tags section for SQL that will allow you to log and audit SQL traffic. For more information see https://docs.microsoft.com/azure/hdinsight/hdinsight-restrict-outbound-traffic#configure-the-firewall-with-network-rules."
	printf '***************************************************************\n\n'
    fi
else
	echo "No custom Oozie DB defined"
	printf '***************************************************************\n\n'
fi

#Validate Custom RANGER DB
if [ ! -z "$RANGERDB" ]; then 
	echo "Validating connectivity to custom Ranger DB: $RANGERDB.database.windows.net" 
	RangerErr="$(nc -vz -w 5 $RANGERDB.database.windows.net 1433 2>&1)"
	if grep -q "succeeded" <<< "$RangerErr"; then
	echo "Connection to custom Ranger DB $RANGERDB successful"
	printf '***************************************************************\n\n'
	else
	ERROR_COUNT=$[ERROR_COUNT + 1]
	echo "ERROR: Connection to custom Ranger DB $RANGERDB failed. Since you are using a custom SQL server for Ranger metastore, then you need to allow the traffic to your own custom SQL Servers.\nVerify that any Network Security Group (NSG), User-Defined Routes (UDR), or firewall allows traffic on TCP port 1433 in outbound direction.\nOne option is to configure Service Endpoints for SQL Server on the HDInsight virtual network. For more information see https://docs.microsoft.com/azure/azure-sql/database/vnet-service-endpoint-rule-overview. If you are using a firewall, configure a network rule in the Service Tags section for SQL that will allow you to log and audit SQL traffic. For more information see https://docs.microsoft.com/azure/hdinsight/hdinsight-restrict-outbound-traffic#configure-the-firewall-with-network-rules."
	printf '***************************************************************\n\n'
    fi
else
	echo "No custom Ranger DB defined"
	printf '***************************************************************\n\n'
fi

#Validate Primary Storage Account:
if [ ! -z "$PrimaryStorage" ]; then 
	echo "Validating connectivity to Primary Storage Account: $PrimaryStorage" 
	PrimStorErr="$(nslookup $PrimaryStorage 2>&1)"
	if grep -q "canonical name " <<< "$PrimStorErr"; then
	echo "Connection to primary storage account $PrimaryStorage successful"
	printf '***************************************************************\n\n'
	else
	ERROR_COUNT=$[ERROR_COUNT + 1]
	echo "ERROR: Connection to primary storage account $PrimaryStorage failed. You need to allow the traffic to your primary storage account on TCP port 443. One option is to configure Service Endpoints for storage on the HDInsight virtual network. For more information see https://docs.microsoft.com/azure/storage/common/storage-network-security#grant-access-from-a-virtual-network. If you are using a firewall, configure a network rule in the Target FQDNs section that will allow traffic to your storage account. For more information see https://docs.microsoft.com/azure/hdinsight/hdinsight-restrict-outbound-traffic#configure-the-firewall-with-application-rules."
	printf '***************************************************************\n\n'
    fi
else
	echo "No primary storage found. A Primary storage acocunt is required to create an HDInsight cluster."
	printf '***************************************************************\n\n'
fi

#Validate Secondary Storage Account:
if [ ! -z "$SecondaryStorage" ]; then 
	echo "Validating connectivity to Secondary Storage Account: $SecondaryStorage" 
	SeconStorErr="$(nslookup $SecondaryStorage 2>&1)"
	if grep -q "canonical name " <<< "$SeconStorErr"; then
	echo "Connection to secondary storage account $SecondaryStorage successful"
	printf '***************************************************************\n\n'
	else
	ERROR_COUNT=$[ERROR_COUNT + 1]
	echo "ERROR: Connection to secondary storage account $SecondaryStorage failed. You need to allow the traffic to this storage account on TCP port 443. One option is to configure Service Endpoints for storage on the HDInsight virtual network. For more information see https://docs.microsoft.com/azure/storage/common/storage-network-security#grant-access-from-a-virtual-network. If you are using a firewall, configure a network rule in the Target FQDNs section that will allow traffic to your storage account. For more information see https://docs.microsoft.com/azure/hdinsight/hdinsight-restrict-outbound-traffic#configure-the-firewall-with-application-rules."
	printf '***************************************************************\n\n'
    fi
else
	echo "No secondary storage found."
	printf '***************************************************************\n\n'
fi

#Validate KeyVault Connectivity:
if [ ! -z "$KV1" ]; then 
	echo "Validating connectivity to Azure Key Vault: $KV1" 
	KV1Err="$(nc -vz -w 5 $KV1 443 2>&1)"
	if grep -q "succeeded" <<< "$KV1Err"; then
	echo "Connection to Key Vault $KV1 successful"
	printf '***************************************************************\n\n'
	else
	ERROR_COUNT=$[ERROR_COUNT + 1]
	echo "ERROR: Connection to Key Vault $KV1 failed. If you plan to use Azure Key Vault to store keys/secrets, you need to allow traffic on TCP port 443. One option is to configure service tags for Azure Key Vault on the HDInsight virtual network. For more information see https://docs.microsoft.com/en-us/azure/virtual-network/service-tags-overview#available-service-tags."
	printf '***************************************************************\n\n'
    fi
else
	echo "No Key Vault found."
	printf '***************************************************************\n\n'
fi

#Validate Azure Management Connectivity:
echo "Validating management.azure.com connectivity:" 
	AzureMgmtErr="$(nc -vz -w 5 management.azure.com 443 2>&1)"
if grep -q "succeeded" <<< "$AzureMgmtErr"; then
  echo "Connection to management.azure.com succeeded"
  printf '***************************************************************\n\n'
else
  ERROR_COUNT=$[ERROR_COUNT + 1]
  echo "ERROR: Connection to management.azure.com failed. Verify that any Network Security Group (NSG), User-Defined Routes (UDR), or firewall allows traffic on TCP port 443 in outbound direction."
  printf '***************************************************************\n\n'
fi

#Validate Microsoft OAuth endpoint Connectivity:
echo "Validating login.windows.net connectivity" 
	MSFTloginErr="$(nc -vz -w 5 login.windows.net 443 2>&1)"
if grep -q "succeeded" <<< "$MSFTloginErr"; then
  echo "Connection to login.windows.net succeeded"
  printf '***************************************************************\n\n'
else
  ERROR_COUNT=$[ERROR_COUNT + 1]
  echo "ERROR: Connection to login.windows.net failed. Verify that any Network Security Group (NSG), User-Defined Routes (UDR), or firewall allows traffic on TCP port 443 in outbound direction."
  printf '***************************************************************\n\n'
fi

echo "Validating login.microsoftonline.com connectivity" 
	MSFTonlineErr="$(nc -vz -w 5 login.microsoftonline.com 443 2>&1)"
if grep -q "succeeded" <<< "$MSFTonlineErr"; then
  echo "Connection to login.microsoftonline.com succeeded"
  printf '***************************************************************\n\n'
else
  ERROR_COUNT=$[ERROR_COUNT + 1]
  echo "ERROR: Connection to login.microsoftonline.com failed. Verify that any Network Security Group (NSG), User-Defined Routes (UDR), or firewall allows traffic on TCP port 443 in outbound direction."
  printf '***************************************************************\n\n'
fi

#Validate Name Resolution
echo "Validating connectivity to Azure Recursive Resolver(ARR) UDP port 443" 
	ARRErr443="$(nc -vzu -w 5 168.63.129.16 443 2>&1)"
if grep -q "succeeded" <<< "$ARRErr443"; then
  echo "Connection to ARR UDP port 443 succeeded"
  printf '***************************************************************\n\n'
else
  ERROR_COUNT=$[ERROR_COUNT + 1]
  echo "ERROR: Connection to ARR UDP port 443 failed. Verify that any Network Security Group (NSG), User-Defined Routes (UDR), or firewall allows traffic on TCP port 443 in outbound direction."
  printf '***************************************************************\n\n'
fi

echo "Validating connectivity to Azure Recursive Resolver(ARR) UDP port 53" 
	ARRErr53="$(nc -vzu -w 5 168.63.129.16 53 2>&1)"
if grep -q "succeeded" <<< "$ARRErr53"; then
  echo "Connection to ARR UDP port 53 succeeded"
  printf '***************************************************************\n\n'
else
  ERROR_COUNT=$[ERROR_COUNT + 1]
  echo "ERROR: Connection to ARR UDP port 53 failed. Verify that any Network Security Group (NSG), User-Defined Routes (UDR), or firewall allows traffic on UDP port 53 in outbound direction."
  printf '***************************************************************\n\n'
fi

echo "Validating connectivity to Azure Recursive Resolver(ARR) TCP port 443" 
	ARRErr443="$(nc -vz -w 5 168.63.129.16 443 2>&1)"
if grep -q "succeeded" <<< "$ARRErr443"; then
  echo "Connection to ARR TCP port 443 succeeded"
  printf '***************************************************************\n\n'
else
  ERROR_COUNT=$[ERROR_COUNT + 1]
  echo "ERROR: Connection to ARR TCP port 443 failed. Verify that any Network Security Group (NSG), User-Defined Routes (UDR), or firewall allows traffic on TCP port 443 in outbound direction."
  printf '***************************************************************\n\n'
fi

echo "Validating connectivity to Azure Recursive Resolver(ARR) TCP port 53" 
	ARRErr53="$(nc -vz -w 5 168.63.129.16 53 2>&1)"
if grep -q "succeeded" <<< "$ARRErr53"; then
  echo "Connection to ARR TCP port 53 succeeded"
  printf '***************************************************************\n\n'
else
  ERROR_COUNT=$[ERROR_COUNT + 1]
  echo "ERROR: Connection to ARR TCP port 53 failed. Verify that any Network Security Group (NSG), User-Defined Routes (UDR), or firewall allows traffic on TCP port 53 in outbound direction."
  printf '***************************************************************\n\n'
fi


#ESP cluster related checks - BEGIN
if [ ! -z "$DOMAIN" ]; then

    LDAPS_TCP_PORT=636

    echo "*********************************************************************"
    echo -e "Starting ESP checks :\nUpdating and installing some packages. Please wait ..."

    cmdAptGetUpdate="$(sudo apt update 2>&1)"
    cmdAptInstall="$(sudo apt install realmd 2>&1)"
    echo -e "Package update/intall completed!\n"
   
	echo -e "a) Name resolution check for AAD-DS domain '$DOMAIN'"
	cmdResult="$(nslookup $DOMAIN 2>&1)"
    #echo -e "$cmdResult"
    if [[ "$cmdResult" == *"server can't find"* ]]; then
	    ERROR_COUNT=$[ERROR_COUNT + 1]
        echo -e "ERROR: Name resolution to $DOMAIN failed. Error message:\n$cmdResult\n"
		echo -e "For more information see https://docs.microsoft.com/azure/hdinsight/domain-joined/apache-domain-joined-configure-using-azure-adds#network-configuration"
        echo -e "------------------------------------\n"
        echo -e "No further checks will be made as name resolution failed for $DOMAIN \n"
        exit
    else        
        echo -e "Name resolution to $DOMAIN was successful"
    fi	
    echo -e "------------------------------------\n"

	echo -e "b) Checking if ldaps://$DOMAIN:$LDAPS_TCP_PORT is up or not using telnet : "    
    ncResult="$(nc -vz -w 5 $DOMAIN $LDAPS_TCP_PORT 2>&1)"
    if [[ "$ncResult" == *"succeeded!"* ]]; then
        echo -e "TCP connection check to $DOMAIN:$LDAPS_TCP_PORT was successful"
    else
        domainIPs="$(getent hosts $DOMAIN | awk '{ print $1 }')" ## AAD-DS DNS IPs
		ERROR_COUNT=$[ERROR_COUNT + 1]
        echo -e "ERROR: TCP connection check to $DOMAIN:$LDAPS_TCP_PORT was not successful. Verify that any Network Security Group (NSG), User-Defined Routes (UDR), or firewall has the below  as allowed on TCP port 636 :\n$domainIPs\n"
		echo -e "For more information see https://docs.microsoft.com/azure/hdinsight/domain-joined/apache-domain-joined-configure-using-azure-adds#enable-azure-ad-ds"
    fi
    echo -e "------------------------------------\n"
    
    echo -e "c) Checking if AADDS is reachable with SSSD realm discover command"
    DOMAIN_UPPERCASED=${DOMAIN^^}
    cmdResult="$(sudo realm discover $DOMAIN_UPPERCASED 2>&1)"    

    if [[ "$cmdResult" == *"server-software: active-directory"* ]]; then    
        echo -e "Connected to AADDS successfully and gathered AADDS information as shown below :\n$cmdResult"
    else        
		ERROR_COUNT=$[ERROR_COUNT + 1]
        echo -e "ERROR: Cannot gather information from AADDS! Error message : $cmdResult\n"
		echo -e "For more information see https://docs.microsoft.com/azure/hdinsight/domain-joined/apache-domain-joined-configure-using-azure-adds#enable-azure-ad-ds"
    fi
    
    echo "*********************************************************************"
else
	echo "Skipping ESP checks as DOMAIN value in params.txt is empty string"
fi
#ESP cluster related checks - END

echo -e "\n\n"
echo -e "====================================================================="
echo -e "=                            SUMMARY                                ="
echo -e "====================================================================="
if [ "$ERROR_COUNT" == "0"  ]; then 
	echo -e "You encountered no errors, you can proceed with HDInsight cluster creation."
else
	echo -e "You hit $ERROR_COUNT errors. Please fix the errors listed above before trying to create your HDInsight cluster."
fi
echo -e "\n"
