#!/usr/bin/env python3

## Author: Bruno Novais
## Email brusilva@cisco.com

import asyncssh, asyncio
import sys, time, argparse, os
from datetime import datetime
from lxml import etree

class SmartFormatter(argparse.HelpFormatter):

    def _split_lines(self, text, width):
        if text.startswith('R|'):
            return text[2:].splitlines()
        # this is the RawTextHelpFormatter._split_lines
        return argparse.HelpFormatter._split_lines(self, text, width)

def openFile(logfile):
    '''
    this function opens logfile and returns the object
    :param logfile:
    :return:
    '''
    f = open(logfile, 'a+')
    return f

def averageThroughput(sizeOfNetconfQuery, timeDelta_seconds):
    '''
    Receives size of a netconfquery response and divides by time it took.
    We then return the float based on KBps
    :param sizeOfNetconfQuery:
    :param timeDelta_seconds:
    :return: float
    '''
    return '%.2f kbps' % (((sizeOfNetconfQuery/timeDelta_seconds)*8)/1000)

def querySize(var) -> int:
    '''
    Calculates size of a list by writing to a file, reading size, then removing file.
    :param var:
    :return:
    '''
    filename = '/tmp/query' + str(datetime.now().microsecond)
    with open(filename, 'w') as q:
        q.write('\n'.join(var))

    statsq = os.stat(filename)
    os.remove(filename)
    return statsq.st_size

def buildXML(request) -> str:
    '''
    This function builds the XML request using etree library.
    We loop through 'request' list to create the hierarchy

    input: List
    return: XML String (netconfQuery)
    '''
    global header
    global end
    sizeOfRequest = len(request)
    header='''<?xml version="1.0" encoding="UTF-8" ?>
           <rpc message-id="1" xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">'''
    end='''</rpc>
        ]]>]]>
    '''

    # First create the standard XML part
    get = etree.Element('get')
    filter = etree.Element('filter')
    Operational = etree.Element('Operational')
    filter.append(Operational)
    get.append(filter)

    # Now the below loop through the list to build the rest that is variable.
    c = 0
    subTree = request[c]
    subElement = etree.Element(subTree)
    Operational.append(subElement)

    # First the netconfQuery is set to the headers and end and in between the tag of the 1st value of the list 'request'
    netconfQuery = header + etree.tostring(get).decode() + end

    # Then we will verify if the size of request is 1. If it is, nothing else needs to be done so we return netconfQuery
    if sizeOfRequest == 1:
        return netconfQuery
    else:
        # If it isn't, means we have deeper layers, so we go and loop through the list creating the elements
        # and adding up to the root Element. Eventually we finish it up and assign this new tree to netconfQuery
        # and return it.
        c = 1
        while c < sizeOfRequest:
            # if the value is an int, we make it text, not an element, so need a try block.
            try:
                var = int(request[c]) + 1
                # assign subElement to 2 parent levels as next element will be under that.
                subElement = subTree.getparent().getparent()
                subTree.text = request[c]
            except ValueError:
                # If not int, just create next subtree and make it child of subelement
                subTreeStr = request[c]
                subTree = etree.Element(subTreeStr)
                subElement.append(subTree)
                subElement = subTree
            finally:
                c += 1

        netconfQuery = header + etree.tostring(get).decode() + end

        return netconfQuery

async def run_client(netconfQuery, count, sleep, ip, user, password, file):
    '''
    this function creates a connection to an ios-xr box, runs netconf format,
    and loops through 'count' times running the netconf query specified in 'netconfQuery'

    :param netconfQuery:
    :param count:
    :param sleep:
    :return: None
    '''
    con, client = await asyncssh.create_connection(None, host =ip, username=user, password=password)
    stdin, stdout, stderr = await con.open_session(command='netconf format')
    time.sleep(1) # the magical sleep to wait for netconf hello exchange
    countTemp = count
    var = []

    # loop until count = 0, and sleep between interactions
    while count > 0:
        if count != countTemp:
            print('# zZz for {}s'.format(sleep*60))
            time.sleep(sleep*60)

        print('# Enough zZz! Sending query\n')
        timeBefore = datetime.today()
        sending_log = '{},{},'.format(' '.join(operation), str(timeBefore))
        file.write(sending_log)
        file.flush()
        stdin.write(netconfQuery + '\n') # write netconfQuery to stdin
        doItOnce = 0
        async for line in stdout:
            if doItOnce == 0:
                timeFirstLine = datetime.today()
                doItOnce += 1
            var.append(line)
            if '/rpc-reply' in line:
                break


        sizeOfNetconfQuery = querySize(var)
        timeAfter = datetime.today()
        timeDelta = timeAfter - timeFirstLine
        timeDelta_seconds = float(timeDelta.total_seconds())
        file.write('{},{},{},{} bytes,{}\n'.format(str(timeFirstLine)
                                          , str(timeAfter)
                                          , str(timeDelta)
                                          , sizeOfNetconfQuery
                                          , averageThroughput(sizeOfNetconfQuery, timeDelta_seconds)))
        file.flush()
        var = []
        count -= 1

if __name__ == "__main__":

    #### Argparse block ####
    helpOperation='R|Operation List. Example:\n\n "SystemMonitoring"\n "RSVP InterfaceSummaryTable"'
    parser = argparse.ArgumentParser(formatter_class=SmartFormatter)
    parser.add_argument("operation", type=str, help=helpOperation)
    parser.add_argument("--count", '-c', type=int, default=1, help="How many times to run query")
    parser.add_argument("--sleep", '-s', type=float, default=1, help="How many minutes to wait before next query")
    parser.add_argument("--ip", '-i', type=str, help="Host")
    parser.add_argument("--user", '-u', type=str, help="Username")
    parser.add_argument("--password", '-p', type=str, help="Password")
    parser.add_argument("--filename", '-f', type=str, help="Filename for logs")
    arguments = parser.parse_args()
    #### End of Argparse block ####

    # Assigning variables
    operation = [s for s in arguments.operation.split(' ')]
    count = arguments.count
    sleep = arguments.sleep
    ip = arguments.ip
    user = arguments.user
    password = arguments.password
    logfile = arguments.filename

    file = openFile(logfile)

    # Running buildXML to build the query based on the list 'operation'
    netconfQuery = buildXML(operation)

    #### Main block ####
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(run_client(netconfQuery, count, sleep, ip, user, password, file))
    except (OSError, asyncssh.Error) as exc:
        sys.exit('SSH connection failed: ' + str(exc))
    finally:
        loop.close()
        file.close()
    #### End of Main block ####
