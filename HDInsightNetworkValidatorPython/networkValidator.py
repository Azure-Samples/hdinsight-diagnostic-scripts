#<---- This script is is still a work in-progress ---->
#This script is to validate the network connectivity needed to successfully deploy your HDInsight cluster.

from utils import *

#x = httpsCheck('https://www.google.com')
#x = ncCheck('www.google.com','80')
#x = nslCheck('www.bing.com')
#print(x)

errors = {}

#Check if we are running on an HDInsight cluster node
if not(inHDInsightClusterNode()):
    #Running on an Azure Linux VM

    #Read the parameters file
    params = readParamsFromTxt()

    print(params['region'])

    #1 - Validate Custom Ambari DB
    if params['AMBARIDB'] != '':        
        print(dbCheck(params['AMBARIDB']))
    
    #2 - Validate Custom Hive DB
    if params['HIVEDB'] != '':
        print(dbCheck(params['HIVEDB']))

    #3 - Validate Custom Oozie DB
    if params['OOZIEDB'] != '':
        print(dbCheck(params['OOZIEDB']))
 
    #4 - Validate Custom Ranger DB
    if params['RANGERDB'] != '':
        print(dbCheck(params['HIVRANGERDBEDB']))
    
    #5 - Validate primary storage account
    if params['PrimaryStorage'] != '':
        print( ncCheck(params['PrimaryStorage'], '443')  )

    #6 - Validate secondary storage account
    if params['SecondaryStorage'] != '':
        print( ncCheck(params['SecondaryStorage'], '443')  )

    #7 - Validate keyvault  account
    if params['KV1'] != '':
        print( ncCheck(params['KV1'], '443')  )
    
    #8 - Validate Azure Management Connectivity:    
    print( ncCheck('management.azure.com', '443')  )

    #9 - Validate Microsoft OAuth endpoint Connectivity:    
    print( ncCheck('login.windows.net', '443')  )

    #10 - Validate Microsoft OAuth endpoint Connectivity:    
    print( ncCheck('login.microsoftonline.com', '443')  )


else:
    #Running on an HDInsight cluster

    #Do the imports for HDInsight python modules like hdinsight_common etc.
    import re

    #Get the cluster manifest
