#!/usr/bin/env python2

# Copyright 2013-present Barefoot Networks, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from mininet.net import Mininet
from mininet.topo import Topo
from mininet.log import setLogLevel, info
from mininet.cli import CLI

from p4_mininet import P4Switch, P4Host

import argparse
from time import sleep

parser = argparse.ArgumentParser(description='Mininet demo')
parser.add_argument('--behavioral-exe', help='Path to behavioral executable',
                    type=str, action="store", required=True)
parser.add_argument('--thrift-port', help='Thrift server port for table updates',
                    type=int, action="store", default=9090)
parser.add_argument('--json', help='Path to JSON config file',
                    type=str, action="store", required=True)
parser.add_argument('--pcap-dump', help='Dump packets on interfaces to pcap files',
                    type=str, action="store", required=False, default=False)

args = parser.parse_args()


class SingleSwitchTopo(Topo):
    "Single switch connected to n (< 256) hosts."
    def __init__(self, sw_path, json_path, thrift_port, pcap_dump, **opts):
        # Initialize topology and default options
        Topo.__init__(self, **opts)

        switch = self.addSwitch('s1',
                                sw_path = sw_path,
                                json_path = json_path,
                                thrift_port = thrift_port,
                                pcap_dump = pcap_dump,
                                enable_debugger = True)
        
        hosts = list()
        hosts.append(self.addHost('h1',
                ip = '10.0.0.2/24', mac = '00:04:00:00:00:01'))
        hosts.append(self.addHost('h2',
                ip = '10.0.0.17/31', mac = '00:04:00:00:00:02'))
        hosts.append(self.addHost('h3',
                ip = '10.0.1.2/24', mac = '00:04:00:00:00:03'))
        hosts.append(self.addHost('h4',
                ip = '10.0.1.19/31', mac = '00:04:00:00:00:04'))

        for host in hosts:
            self.addLink(host, switch)

def main():
    num_hosts = 4

    topo = SingleSwitchTopo(args.behavioral_exe,
                            args.json,
                            args.thrift_port,
                            args.pcap_dump
                            )
    net = Mininet(topo = topo,
                  host = P4Host,
                  switch = P4Switch,
                  controller = None)
    net.start()

    sw_mac = ["00:aa:bb:00:00:%02x" % n for n in xrange(num_hosts)]

    sw_addr = [
        "10.0.0.1",
        "10.0.0.16",
        "10.0.1.1",
        "10.0.1.18"
    ]

    for n in xrange(num_hosts):
        h = net.get('h%d' % (n + 1))
        h.setARP(sw_addr[n], sw_mac[n])
        h.setDefaultRoute("dev eth0 via %s" % sw_addr[n])
    net['h1'].cmd("ip route add 10.0.0.17 dev eth0 via 10.0.0.1")
    net['h3'].cmd("ip route add 10.0.1.19 dev eth0 via 10.0.1.1")

    for n in xrange(num_hosts):
        h = net.get('h%d' % (n + 1))
        h.describe()

    sleep(1)

    print "Ready !"

    CLI( net )
    net.stop()

if __name__ == '__main__':
    setLogLevel( 'info' )
    main()
