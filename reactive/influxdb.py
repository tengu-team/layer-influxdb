#!/usr/bin/env python3
# Copyright (C) 2016  Ghent University
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from subprocess import check_call

from charmhelpers.core import templating

from charmhelpers.core.hookenv import (
    status_set,
    open_port,
    unit_private_ip,
    config,
    log,
)
from charmhelpers.core import host
from charms.reactive import set_state, remove_state, hook, when, when_not
from charms.reactive.helpers import any_file_changed

import charms.apt

conf = config()

@when_not('apt.installed.influxdb')
def install_influxdb():
    status_set('maintenance', 'Installing InfluxDB')
    charms.apt.queue_install(['influxdb'])  # does not apt install influxdb-client

@when('apt.installed.influxdb')
@when_not('influxdb.available')
def configure_influxdb():
    status_set('maintenance', 'Configuring InfluxDB')
    config_ports()
    status_set('maintenance', 'Ready to start ...')
    set_state('influxdb.available')

@when('influxdb.available')
@when_not('influxdb.started')
def start_influxdb():
    log('Starting InfluxDB.')
    command = ['systemctl', 'start', 'influxdb']
    check_call(command)
    status_set('active', 'Ready (InfluxDB)')
    set_state('influxdb.started')

@hook('config-changed')
def config_changed():
    remove_state('influxdb.started')
    config_ports()
    log('Restarting InfluxDB.')
    command = ['systemctl', 'restart', 'influxdb']
    check_call(command)
    status_set('active', 'Ready (InfluxDB)')
    set_state('influxdb.started')
    

def config_ports():
    api_port = conf.get('api_port')
    rpc_port = conf.get('rpc_port')
    open_port(api_port, protocol='TCP')    # Port to the HTTP API endpoint
    open_port(rpc_port, protocol='TCP')    # Port to the RPC endpoint
    templating.render(
        source='influxdb.conf',
        target='/etc/influxdb/influxdb.conf',
        context={
            'api_port': api_port,
            'rpc_port': rpc_port
        }
    )    

@when('influxdb.started')
@when('api.api.available')
def configure_api_relation(api):
    log('Configuring InfluxDB api relation.')
    api.configure(unit_private_ip(), conf.get('api_port'), 'root', 'root')
    #log('Setting up juju database.')
    #command = ['/usr/bin/influx', '-execute', 'CREATE DATABASE juju']
    #check_call(command)

@when('influxdb.started')
@when('grafana-source.available')
def configure_grafana(grafana_source):
    log('Detected Grafana. Connecting...')
    api_port = conf.get('api_port')
    grafana_source.provide('influxdb@{}'.format(api_port), api_port, 'InfluxDB provided by Juju', 'root', 'root')


