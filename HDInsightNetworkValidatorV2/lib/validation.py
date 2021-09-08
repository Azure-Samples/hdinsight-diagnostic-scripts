from lib.utils import *
from lib.storage import *
from lib.scrapers import *
from lib.hdinsight import *
from lib.azurefirewall import *
from lib.network import *
from netaddr import *


class Validation:
    def __init__(self, id, name, tool, afterClusterCreated, hostname, protocol, port, direction, timeout):
        self.id = id
        self.name = name
        self.tool = tool
        self.afterClusterCreated = False
        self.hostname = hostname
        self.protocol = protocol
        self.port = port
        self.direction = direction
        self.timeout = timeout
        self.succeeded = False
        self.cmdout = ""
        self.active = False


class CheckResult(object):
    """A POCO class to store check results"""

    isOk = False
    result = ""


# netcat
def ncCheck(target, port, protocol="TCP", timeOut="5", showSpinner=True):
    """Checks the outbound connection using NetCat"""

    cr = CheckResult()

    if protocol == "TCP":
        cr.result = executeCommand("nc -vz -w " + str(timeOut) + " " + target + " " + str(port), "", showSpinner)
    elif protocol == "UDP":
        cr.result = executeCommand("nc -vzu -w " + str(timeOut) + " " + target + " " + str(port), "", showSpinner)

    if ("succeeded!") in str(cr.result):
        cr.isOk = True
    return cr


def doValidation(self, v, showSpinner=True):
    """Does the required validation by the given validation object"""

    cr = CheckResult()

    if v.tool == "nc":  # NetCat
        cr = ncCheck(v.hostname, v.port, v.protocol, v.timeout, showSpinner)
        if cr.isOk:
            v.succeeded = True
            v.cmdout = cr.result
        else:
            v.succeeded = False
            v.cmdout = cr.result

    elif v.tool == "nw":  # NetworkWatcher - VerifyIPFlow

        # If there is no NSG in the subnet, return True
        if self.current_subnet.network_security_group == None:
            v.succeeded = True
            v.cmdout = "Bypassed as there is no NSG set in your subnet"
        else:
            result = doNetworkWatcherVerifyIpFlowCheckFromHDIMEIP(self, v.hostname, True)

            if result.access == "Allow":
                v.succeeded = True
                v.cmdout = "Allowing rule_name : " + str(result.rule_name) + "\n"
            else:
                v.succeeded = False
                v.cmdout = "Denying rule_name : " + str(result.rule_name) + "\n"
    return v
