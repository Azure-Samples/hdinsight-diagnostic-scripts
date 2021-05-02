import os
from os import path
import sys
import subprocess
import requests

def inHDInsightClusterNode():
    if path.exists('/usr/hdp/current') :
    #if path.exists('/tmp/') :
        print('Running on cluster')
        return True
    else:
        print('Running on an Azure Linux VM')
        return False

def executeCommand(cmdName: str, params: str = ''):
    myProc = subprocess.run( cmdName + ' ' + params , shell=True, check=True, stdout=subprocess.PIPE, universal_newlines=True)
    #print('Command execution output for : ' + cmdName + ' ' + params + ' : '  + myProc.stdout)
    return myProc.stdout

#netcat
def ncCheck(target: str, port: str , protocol: str = 'TCP', timeOut:str = '5'):
    #nc -vz -w 5 $line 443 2>&1    
    if (protocol=='TCP'):
        ncCheckResult = executeCommand('nc -vz -w ' + timeOut + ' ' + target + ' ' + port)
    elif (protocol=='UDP'):
        ncCheckResult = executeCommand('nc -vzu -w ' + timeOut + ' ' + target + ' ' + port)    
    return ncCheckResult

#nslookup
def nslCheck(target: str):
    nslCheckResult = executeCommand('nslookup ' + target)
    return nslCheckResult

#db specific netcat
def dbCheck(dbServerName: str, dbServerSuffix:str = 'database.windows.net', port: str = '1433'):
    return ncCheck(dbServerName + '.' + dbServerSuffix, '1433')

def httpsCheck(targetURL: str, httpRequestType: str = 'GET') :

    httpsCheckResult = ''
    
    if (httpRequestType == 'POST'):
        print('POSTTT')
        httpsCheckResult = 'POSTTT'
    else:
      r = requests.get(targetURL, allow_redirects=True)
    httpsCheckResult = r.content
    
    return(httpsCheckResult)

def readParamsFromTxt():
    if not( path.exists('params.txt')):
        print('ERROR: Cannot find  \'params.txt\' in the current folder')
        sys.exit()

    ##Dictionary to store params
    params = {} 
    f = open('params.txt','r')

    for line in f:        
        if ( line.startswith('#') or line == '' or line == '\n'):
            next
        else:
            #print('Line: '  + line)
            tmpArr = line.split('=')
            
            tmpKey = tmpArr[0]

            tmpValue = (tmpArr[1])
            #if lined ends with \n, remove it
            if tmpValue.endswith('\n'):
                tmpValue = tmpValue[0:-1]
            #strip the double quotes
            tmpValue = tmpValue[1:-1]

            params[tmpKey] = tmpValue
    f.close()
    #print(params)
    return(params)

