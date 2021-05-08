#This script is to validate the network connectivity needed to successfully deploy your HDInsight cluster.

from sys import version
from utils import *
import json

scriptVersion = '1.0.0'

#Globals
#Dictionary to store all 'Validation' objects
validations = []

#Counts
totalValidationCount = 0
failedValidationCount = 0


#Read the standard validations from JSON file
with open('./std_validations.json') as f:
    validationsJSON = json.load(f)

#Parse the standard validations from JSON
for item in validationsJSON['validations']:
    #Add validation to the list    
    validations.append( Validation( int(item['id']), item['name'], item['type'], item['hostname'], item['protocol'], int(item['port']), int(item['timeout'])) )
    totalValidationCount = totalValidationCount + 1

#Check if we are running on an HDInsight cluster node
if not(inHDInsightClusterNode()):
    #Running on an Azure Linux VM

    #Read the parameters file
    params = readParamsFromTxt()  

    if params['PrimaryStorage'] != '':
        totalValidationCount = totalValidationCount + 1
        validations.append( Validation( totalValidationCount, "Primary Storage Connectivity", "nc", params['PrimaryStorage'], "TCP", 443, 5) )
    
    if params['SecondaryStorage'] != '':
        totalValidationCount = totalValidationCount + 1
        validations.append( Validation( totalValidationCount, "Secondary Storage Connectivity", "nc", params['SecondaryStorage'], "TCP", 443, 5) ) 
    
    if params['AMBARIDB'] != '':
        totalValidationCount = totalValidationCount + 1
        validations.append( Validation( totalValidationCount, "AmbariDB Server Connectivity", "nc", params['AMBARIDB'], "TCP", 1433, 5) )
        
    if params['HIVEDB'] != '':
        totalValidationCount = totalValidationCount + 1
        validations.append( Validation( totalValidationCount, "HiveDB Server Connectivity", "nc", params['HIVEDB'], "TCP", 1433, 5) )
    
    if params['OOZIEDB'] != '':
        totalValidationCount = totalValidationCount + 1
        validations.append( Validation( totalValidationCount, "OozieDB Server Connectivity", "nc", params['OOZIEDB'], "TCP", 1433, 5) ) 
    
    if params['RANGERDB'] != '':
        totalValidationCount = totalValidationCount + 1
        validations.append( Validation( totalValidationCount, "RangerDB Server Connectivity", "nc", params['RANGERDB'], "TCP", 1433, 5) ) 
    
    if params['KV1'] != '':
        totalValidationCount = totalValidationCount + 1
        validations.append( Validation( totalValidationCount, "Key Vault Connectivity", "nc", params['KV1'], "TCP", 443, 5) ) 

else:    
    print('Coming soon...')

print('========================================================================')
print('HDInsight Pre-deployment Network Configuration Checks - v ' + scriptVersion)
print('========================================================================' + "\n")

print('Starting validations....' + '\n')

for v in validations:    
    print('Validation #' + str(v.id) + ' "' + v.name + '" started')
    print('Trying to access "' + v.hostname + ' ' + v.protocol + ' ' + str(v.port) + '" within ' + str(v.timeout) +  's timeout period...')

    v = doValidation(v)

    if  v.succeeded:
        print('Result : Success')
        print('CmdOut : ' + v.cmdout)
    else:
        failedValidationCount = failedValidationCount+1
        print('Result : Failure')
        print('Error : ' + v.cmdout)

    #print('Validation #' + str(v.id) + ' ended' )

if (failedValidationCount>0):
    print('============================================================RESULT==========================================================================')
    print(str(failedValidationCount) + ' validations out of ' + str(len(validations)) + ' below are failed : \n')

    for v in validations:
        if not(v.succeeded):
            print('#' + str(v.id) + ' - ' + v.name)        
            print('Host: \"' + v.hostname + '\"' + ' , Protocol: ' + v.protocol + ' , Port: ' + str(v.port) + '\n')            

    print('ACTION REQUIRED: Please check your NSG/UDR/Firewall to see if you are allowing traffic to those hosts/ports in \"Outbound\" direction')
    print('============================================================================================================================================')
else:
    print('===============RESULT================================================\n')
    print('SUCCESS: You can create your HDInsight cluster in this VNet/Subnet :)\n')
    print('===============RESULT================================================')

print("\nP.S : Don't forget to delete this Azure VM if you've created to run this HDInsight pre-deployment network checks script only.")
