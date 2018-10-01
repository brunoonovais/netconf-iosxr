#!/usr/bin/env python

import paramiko
import sys
import socket
from time import sleep
from lxml import etree

#### Exit Codes
# -1 = missing all arguments
# 1 = ip not in right format
# 2 = missing number of iterations or it' not an integer
# 3 = missing sleep time

def verify_arguments(arguments):

# This function verifies that we have proper number of arguments
# also verifies ip is in proper format

    if len(arguments) < 4:
        print """Please use script as follows:
              <script> <ip> <username> <password> <Operation> <iterations> <sleep time in minutes>
              """
        sys.exit(-1)
    if not socket.inet_aton(arguments[1]):
        print 'IP is not in right format'
        sys.exit(1)

    if not int(sys.argv[5]):
        print 'Please include number of iterations'
        sys.exit(2)

    if not float(sys.argv[6]):
        print 'Please include sleep time between queries in seconds'
        sys.exit(3)

def connect_paramiko(router_ip_p, username_p, password_p):

# This function creates an object by connecting to a router passed by arguments
# it then returns the object

    router = paramiko.SSHClient()
    router.load_system_host_keys()
    router.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        router.connect(router_ip_p, username=username_p, password=password_p, allow_agent=False, look_for_keys=False, timeout=None)
        print 'Connected via SSH to {}'.format(router_ip_p)
    except:
        print 'Couldn\'t connect to {}'.format(router_ip_p)

    return router

def start_netconf(self):

# This function sends a "netconf format" to the router object
# It then returns the stdin, stdout, stderr output back

    stdin, stdout, stderr = self.exec_command('netconf format', get_pty=True)

    return stdin, stdout, stderr

def get_oper_netconf(self, operation, stdin, stdout, stderr):

# This function will get operational data from a router object
# operation = i.e. 'InterfaceTable'

    supported_operations = ['InterfaceTable']
    hello = """
            <?xml version="1.0" encoding="UTF-8" ?>
                    <hello>
                        <capabilities>
                            <capability>
                                urn:ietf:params:netconf:base:1.0
                            </capability>
                        </capabilities>
                    </hello>
            ]]>]]>
            """
    close = """
    <?xml version="1.0" encoding="UTF-8" ?>
        <rpc message-id="1" xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
            <close-session/>
        </rpc>
       ]]>]]>
    """
    # First verify it's a supported operation for this script
    if operation in supported_operations:
        print 'Operation is supported'
        if operation == 'InterfaceTable':
            print 'InterfaceTable requested'
            query_interfaceTable="""<?xml version="1.0" encoding="UTF-8" ?>
                                    <rpc message-id="1" xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
                                      <get>
                                        <filter>
                                          <Operational>
                                            <Interfaces>
                                              <InterfaceTable>
                                              </InterfaceTable>
                                            </Interfaces>
                                          </Operational>
                                        </filter>
                                      </get>
                                    </rpc>
                                  ]]>]]>"""

            header = """<?xml version="1.0" encoding="UTF-8" ?>
                    <rpc message-id="1" xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">"""
            ending = """</rpc>
                    ]]>]]>"""


            # Now we loop through the number of iterations mentioned.
            stdin.write(hello + '\n')
            stdin.write(query_interfaceTable + '\n')
            stdin.flush()

            # the loop below will stop until we see rpc-reply tag closing, which means we finish the reply
            # print.
            for line in stdout:
                print line.rstrip()
                if line.strip() == '</rpc-reply>':
                    break

def main():

    # first verify arguments
    verify_arguments(sys.argv)

    # assign variables
    router_ip = sys.argv[1]
    username = sys.argv[2]
    password = sys.argv[3]
    operation = sys.argv[4]
    num_iterations = sys.argv[5]
    sleep_time = sys.argv[6]
    count=0

    # We will loop through the whole process depending on the number of iterations requested.
    while int(count) < int(num_iterations):

        # now we need to connect to the router in question
        router = connect_paramiko(router_ip, username, password)

        # now need to start netconf shell
        stdin, stdout, stderr = start_netconf(router)

        # now we can actually send a get via netconf along with hello
        get_oper_netconf(router, operation, stdin, stdout, stderr)

        router.close()

        count += 1
        sleep(float(sleep_time))

if __name__ == '__main__':
    main()
