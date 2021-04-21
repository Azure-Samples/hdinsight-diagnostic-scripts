#!/bin/bash
#This script is to validate the network connectivity needed to successfully deploy your HDInsight cluster.

#Read the parameters file
. params.txt

#Get the HDInsight Management IP files from Azure storage account
wget https://hdidiagscripts.blob.core.windows.net/data/HDInsightManagementIPs_$region.txt

#Loop for checking HDInsight Management IPs by region
regionFile="HDInsightManagementIPs_$region.txt"

##Read the file line-by-line using while loop
while IFS= read -r line
do
  printf '****************************************************************************\n'
  echo "Testing connectivity to IP $line in $region"
  ncResult="$(nc -vz -w 5 $line 443| grep '[tcp/https] succeeded!')"
if [ ! -z "$ncResult" ]; then
        echo "Connection to IP $line in $region was successful"
else
        echo "Connection to IP $line in $region failed. Verify that any Network Security Group (NSG), User-Defined Routes (UDR), or firewall has the IP $line as allowed on port 443"
fi

done < "$regionFile"

#Validate Custom Ambari DB
	echo "*********************************************************************"
if [ ! -z "$AMBARIDB" ]; then
	echo "Validating connectivity to custom Ambari DB: $AMBARIDB.database.windows.net" 
	AmbariErr="$(nc -vz -w 5 $AMBARIDB.database.windows.net 1433 2>&1)"
	echo "Custom Ambari DB Results: $AmbariErr"
	echo "************************************"
else
	echo "No custom Ambari DB defined"
	echo "*********************************************************************"
fi

#Validate Custom Hive DB
if [ ! -z "$HIVEDB" ]; then 
	echo "Validating connectivity to custom Hive DB: $HIVEDB.database.windows.net" 
	HiveErr="$(nc -vz -w 5 $HIVEDB.database.windows.net 1433 2>&1)"
	echo "Custom Hive DB Results: $HiveErr"
	echo "*********************************************************************"
else
	echo "No custom Hive DB defined"
	echo "*********************************************************************"
fi

#Validate Custom OOZIE DB
if [ ! -z "$OOZIEDB" ]; then 
	echo "Validating connectivity to custom OOZIE DB: $OOZIEDB.database.windows.net" 
	OozieErr="$(nc -vz -w 5 $OOZIEDB.database.windows.net 1433 2>&1)"
	echo "Custom Oozie DB Results: $OozieErr"
	echo "*********************************************************************"
else
	echo "No custom Oozie DB defined"
	echo "*********************************************************************"
fi

#Validate Custom RANGER DB
if [ ! -z "$RANGERDB" ]; then 
	echo "Validating connectivity to custom Ranger DB: $RANGERDB.database.windows.net" 
	RangerErr="$(nc -vz -w 5 $RANGERDB.database.windows.net 1433 2>&1)"
	echo "Custom Ranger DB Results: $RangerErr"
	echo "************************************"
else
	echo "No custom Ranger DB defined"
	echo "************************************"
fi

#Validate Internal Metastore DBs
#Need a way to test connectivity to the Azure SQL DB endpoints used for internal Hive #and Ambari databases. Need to test ports 1433 and 11000 - 11999.

#Validate Primary Storage Account:
if [ ! -z "$PrimaryStorage" ]; then 
	echo "Validating connectivity to Primary Storage Account: $PrimaryStorage" 
	PrimStorErr="$(nslookup $PrimaryStorage 2>&1)"
	echo "Primary Storage Connectivity Results: $PrimStorErr"
	echo "************************************"
else
	echo "A primary storage account is required to create an HDInsight cluster"
	echo "************************************"
fi

#Validate Secondary Storage Account:
if [ ! -z "$SecondaryStorage" ]; then 
	echo "Validating connectivity to Secondary Storage Account: $SecondaryStorage" 
	SeconStorErr="$(nslookup $SecondaryStorage 2>&1)"
	echo "Secondary Storage Connectivity Results: $SeconStorErr"
	echo "************************************"
else
	echo "A Secondary storage account was not found"
	echo "************************************"
fi

#Validate KeyVault Connectivity:
if [ ! -z "$KV1" ]; then 
	echo "Validating connectivity to Azure Key Vault: $KV1" 
	KV1Err="$(nc -vz -w 5 $KV1 2>&1)"
	echo "Key Vault Connectivity Results: $KV1Err"
	echo "************************************"
else
	echo "No KeyVault entry was"
	echo "************************************"
fi



#ESP cluster related checks - BEGIN
if [ ! -z "$DOMAIN" ]; then

    LDAPS_TCP_PORT=636

    echo "*********************************************************************"
    echo -e "Starting ESP checks :\nUpdating and installing some packages. Please wait ..."

    cmdAptGetUpdate="$(sudo apt update 2>&1)"
    cmdAptInstall="$(sudo apt install krb5-user samba sssd sssd-tools libnss-sss libpam-sss ntp ntpdate realmd adcli 2>&1)"
    echo -e "Package update/intall completed!\n"
   
	echo -e "a) Name resolution check for AAD-DS domain '$DOMAIN'"
	cmdResult="$(nslookup $DOMAIN 2>&1)"
    #echo -e "$cmdResult"
    if [[ "$cmdResult" == *"server can't find"* ]]; then
        echo -e "Name resolution to $DOMAIN failed. Error message:\n$cmdResult"
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
        echo -e "TCP connection check to $DOMAIN:$LDAPS_TCP_PORT was not successful. Verify that any Network Security Group (NSG), User-Defined Routes (UDR), or firewall has the below IPs as allowed on TCP port 636 :\n$domainIPs"
    fi
    echo -e "------------------------------------\n"
    
    echo -e "c) Checking if AADDS is reachable with SSSD realm discover command"
    DOMAIN_UPPERCASED=${DOMAIN^^}
    cmdResult="$(sudo realm discover $DOMAIN_UPPERCASED 2>&1)"    

    if [[ "$cmdResult" == *"server-software: active-directory"* ]]; then    
        echo -e "Connected to AADDS successfully and gathered AADDS information as shown below :\n$cmdResult"
    else        
        echo -e "Cannot gather information from AADDS! Error message : $cmdResult"
    fi
    
    echo "*********************************************************************"
else
	echo "Skipping ESP checks as DOMAIN value in params.txt is empty string"
fi
#ESP cluster related checks - END







#Validate Azure Management Connectivity:
echo "Validating management.azure.com Connectivity:" 
	AzureMgmtErr="$(nc -vz -w 5 management.azure.com 443 2>&1)"
	echo "Azure Management Connectivity Results: $AzureMgmtErr"
	echo "************************************"

#Validate Microsoft OAuth endpoint Connectivity:
echo "Validating login.windows.net Connectivity" 
	MSFTloginErr="$(nc -vz -w 5 login.windows.net 443 2>&1)"
	echo "login.windows.net Connectivity Results: $MSFTloginErr"
	echo "************************************"

echo "Validating login.microsoftonline.com Connectivity" 
	MSFTonlineErr="$(nc -vz -w 5 login.microsoftonline.com 443 2>&1)"
	echo "login.microsoftonline.com Connectivity Results: $MSFTonlineErr"
	echo "************************************"


