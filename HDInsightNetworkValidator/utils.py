import os
from os import path
import sys
import subprocess
import requests

def inHDInsightClusterNode():
    if path.exists('/usr/hdp/current') :    
        print('Please don\'t run this script on your existing cluster node, yet!')
        sys.exit()
        return True
    else:
        #print('Running on an Azure Linux VM')
        return False

def executeCommand(cmdName, params = ''):
    #myProc = subprocess.run( cmdName + ' ' + params , shell=True, check=True, stdout=subprocess.PIPE, universal_newlines=True)
    #return myProc.stdout
    
    myProc = subprocess.Popen( cmdName + ' ' + params , stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)    
    stdout, stderr = myProc.communicate()
    if ( len(str(stdout)) > len(str(stderr)) ): 
        return stdout
    else:
        return stderr

#netcat
def ncCheck(target, port , protocol = 'TCP', timeOut = '5'):
    cr = CheckResult()
    #nc -vz -w 5 $line 443 2>&1    
    if (protocol=='TCP'):
        cr.result = executeCommand('nc -vz -w ' + str(timeOut) + ' ' + target + ' ' + str(port))
    elif (protocol=='UDP'):
        cr.result = executeCommand('nc -vzu -w ' + str(timeOut) + ' ' + target + ' ' + str(port))
    
    if ('succeeded!') in str(cr.result):
        cr.isOk = True        
    return cr

#nslookup
def nslCheck(target):
    cr = CheckResult()
    cr.result = executeCommand('nslookup ' + target)
    if ('succeeded!') in str(cr.result):
        cr.isOk = True        
    return cr

#db specific netcat
def dbCheck(dbServerName, dbServerSuffix = 'database.windows.net', port= '1433'):    
    return ncCheck(dbServerName + '.' + dbServerSuffix, '1433')

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
            
            #if line ends with \n, remove it
            if tmpValue.endswith('\n'):
                tmpValue = tmpValue[0:-1]
            #strip the double quotes
            tmpValue = tmpValue[1:-1]

            params[tmpKey] = tmpValue
    f.close()
    #print(params)
    return(params)


class CheckResult(object):    
    isOk = False
    result = ''

class Validation:
    def __init__(self, id, name, type, hostname, protocol, port, timeout):
        self.id = id
        self.name = name
        self.type = type
        self.hostname = hostname
        self.protocol = protocol
        self.port = port
        self.timeout = timeout
        self.succeeded = False
        self.cmdout    = ""

def doValidation(v):
    cr = CheckResult()
    if ( v.type == 'nc'):
        cr = ncCheck(v.hostname, v.port, v.protocol, v.timeout)
        if cr.isOk:            
            v.succeeded = True
            v.cmdout = cr.result
        else:
            #failedValidationCount = failedValidationCount+1
            v.succeeded = False
            v.cmdout = cr.result
    #TODO
    elif ( v.type == 'nsl'):
        cr = ncCheck(v.hostname, v.port, v.protocol, v.timeout)
        if cf.isOk:            
            v.succeeded = True
            v.cmdout = cr.result
        else:
            #failedValidationCount = failedValidationCount+1
            v.succeeded = False
            v.cmdout = cr.result

    return v    
