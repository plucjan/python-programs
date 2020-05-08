# coding: utf-8
__version__ = '1.0'
__author__ = 'Paweł Łucjan'

try:
    import logging
    from libnestclient import Plugin
except:
    import sys
    print(Plugin.msg['lib_import'])
    sys.exit(1)


class Zombies(Plugin):
    supported_OSes = 'Linux'

    def __init__(self, queue, stop_flag, env, additional_info):
        self.logger = logging.getLogger(self.__class__.__name__)
        super(self.__class__, self).__init__(queue, stop_flag, env, additional_info)

    def get_config(self, interval=60, host_ip='', users=(), skip=0, **kwargs):
        self.time_period = int(interval)
        self.host_ip = str(host_ip) or self.host_ip
        self.ps = '/bin/ps -ax -o state,user,uid,pid,cmd' if not users else '/bin/ps -u %s -o state,user,uid,pid,cmd' % ','.join(users)
        self.zombies = []
        self.ignore = self.skip = int(skip)
        self.verify_kwargs(kwargs)

    def main(self):
        status, output = self.execute(self.ps)
        error = False
        if status:
            self.logger.error(self.msg['command'] % self.ps)
        else:
            if self.os_type == 'Linux':
                current_zombies = []
                counter = {}
                for line in output[1:]:
                    if line.startswith('Z'):
                        current_zombies.append(line)
                self.zombies.insert(0, current_zombies)
                self.zombies = self.zombies[:self.ignore+1]
                endless_zombies = set.intersection(*map(set, self.zombies))
                if len(endless_zombies):
                    error = True
                    if not self.skip:
                        for zombie_line in endless_zombies:
                            counter[zombie_line.split()[1]] = counter.get(zombie_line.split()[1], 0) + 1
                        alert_string = ', '.join(['{0}: {1}'.format(user, amount) for user, amount in counter.iteritems()])
                        self.send_critical('Zombies detected - %s!' % alert_string)
        if error:
            if self.skip:
                self.skip -= 1
        else:
            self.skip = self.ignore

