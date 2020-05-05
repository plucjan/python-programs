# coding: utf-8
__version__ = '1.1'
__author__ = 'Andrzej Mateja/Paweł Łucjan'

try:
    import logging
    from libnestclient import Plugin
except:
    import sys
    print(Plugin.msg['lib_import'])
    sys.exit(1)


class Interfaces(Plugin):
    supported_OSes = 'Linux', 'SunOS', 'AIX', 'HP-UX'

    def __init__(self, queue, stop_flag, env, additional_info):
        self.logger = logging.getLogger(self.__class__.__name__)
        super(self.__class__, self).__init__(queue, stop_flag, env, additional_info)

        if self.os_type == 'Linux':
            self.ifconfig = 'ip link'
            self.netstat = 'sudo ethtool -S ' # + interface name
        elif self.os_type == 'HP-UX':
            self.ifconfig = 'for i in `lanscan -i | awk \'{print $1}\'`; do ifconfig $i; done'
            self.netstat = 'netstat -i'
        else:
            self.ifconfig = 'ifconfig -a'
            self.netstat = 'netstat -i'
        self.ifce = {}
        self.ifcs = ()

    def get_config(self, interval=60, host_ip='', limits=(1, 1, 1), skip=0, **kwargs):
        self.time_period = int(interval)
        self.host_ip = str(host_ip) or self.host_ip
        self.limits = map(int, tuple(limits))
        if len(self.limits) != 3:
            raise Plugin.BadConfiguration
        self.ignore = self.skip = int(skip)
        self.verify_kwargs(kwargs)

    def main(self):
        status, output = self.execute(self.ifconfig, False)
        error = False
        if status:
            self.logger.error(self.msg['command'] % self.ifconfig)
        else:
            if self.os_type == 'Linux':
                for line in output.splitlines():
                    if 'mtu' in line:
                        interface = line.split(': ')[1]
                        self.ifcs = self.ifcs + (interface,)
                        state = True if 'NO-CARRIER' in line or 'UP' not in line else False # 'lo'?
                        if state:
                            error = True
                            if not self.skip:
                                self.send_critical('Interface %s has faulty state: %s.' % (interface, line.split('<')[1].split('>')[0]))
            elif self.os_type == 'HP-UX':
                output = filter(lambda a: 'UP' not in a, output.splitlines()[2:])
                for line in output:
                    error = True
                    if not self.skip:
                        self.send_critical('Interface %s has faulty state: %s.' % (line.split()[4], line.split()[3]))
            else:
                output = filter(lambda a: 'flags' in a and (('UP' not in a and 'INACTIVE' not in a) or 'RUNNING' not in a or 'FAILED' in a), output.splitlines())
                for line in output:
                    interface, state = line.split(': ')
                    error = True
                    if not self.skip:
                        self.send_critical('Interface %s has faulty state: %s.' % (interface, state.split('<')[1].split('>')[0].replace(',', ' ')))
        if error:
            if self.skip:
                self.skip -= 1
        else:
            self.skip = self.ignore


        if self.os_type == 'Linux':
            for ifc in self.ifcs:
                if 'lo' not in ifc:
                    status, output = self.execute(self.netstat + ifc)
                    if status:
                        self.logger.error(self.msg['command'] % self.netstat)
                    else:
                        output = filter(lambda a: a != '', output)
                        #self.send_critical('Dobrze %s' % ifc)
                        for line in output:
                            if 'rx_errors' in line:
                                rx_errors_tmp = line.split(': ')[1]
                            elif 'tx_errors' in line:
                                tx_errors_tmp = line.split(': ')[1]
                            elif 'rx_over_errors' in line:
                                rx_over_errors_tmp = line.split(': ')[1]
                        if self.initial:
                            self.ifce[ifc] = rx_errors_tmp, tx_errors_tmp, rx_over_errors_tmp
                        else:
                            try:
                                rxerrors, txerrors, rxovererrors = self.ifce[ifc]
                            except KeyError:
                                rxerrors = rx_errors_tmp
                                txerrors = tx_errors_tmp
                                rxovererrors = rx_over_errors_tmp
                            else:
                                if rxerrors + self.limits[0] < rx_errors_tmp:
                                    self.send_critical('Rx errors on network interface %s exceeded defined level.' % ifc)
                                if txerrors + self.limits[1] < tx_errors_tmp:
                                    self.send_critical('Tx errors on network interface %s exceeded defined level.' % ifc)
                                if rxovererrors + self.limits[2] < rx_over_errors_tmp:
                                    self.send_critical('Overruns on network interface %s exceeded defined level.' % ifc)
                            self.ifce[ifc] = rxerrors + rx_errors_tmp, txerrors + tx_errors_tmp, rxovererrors + rx_over_errors_tmp
        else:
            status, output = self.execute(self.netstat)
            if status:
                self.logger.error(self.msg['command'] % self.netstat)
            else:
                output = filter(lambda a: a != '', output)
                for line in output[1:]:
                    tmp = line.split()
                    if len(tmp) > 8:
                        ifc = tmp[0]
                        rxerrors_tmp = int(tmp[5])
                        txerrors_tmp = int(tmp[7])
                        overruns_tmp = int(tmp[8])
                        if self.initial:
                            self.ifce[ifc] = rxerrors_tmp, txerrors_tmp, overruns_tmp
                        else:
                            try:
                                rxerrors, txerrors, overruns = self.ifce[ifc]
                            except KeyError:
                                rxerrors = rxerrors_tmp
                                txerrors = txerrors_tmp
                                overruns = overruns_tmp
                            else:
                                if rxerrors + self.limits[0] < rxerrors_tmp:
                                    self.send_critical('Rx errors on network interface %s exceeded defined level.' % ifc)
                                if txerrors + self.limits[1] < txerrors_tmp:
                                    self.send_critical('Tx errors on network interface %s exceeded defined level.' % ifc)
                                if overruns + self.limits[2] < overruns_tmp:
                                    self.send_critical('Overruns on network interface %s exceeded defined level.' % ifc)
                            self.ifce[ifc] = rxerrors + rxerrors_tmp, txerrors + txerrors_tmp, overruns + overruns_tmp

