# Copyright 2022 Red Hat, Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from socket import AF_INET6
from unittest import mock

from oslo_concurrency import processutils

from ovn_bgp_agent.privileged import linux_net as priv_linux_net
from ovn_bgp_agent.tests import base as test_base
from ovn_bgp_agent.utils import linux_net


class FakeException(Exception):
    stderr = ''


class TestPrivilegedLinuxNet(test_base.TestCase):

    def setUp(self):
        super(TestPrivilegedLinuxNet, self).setUp()
        # Mock pyroute2.NDB context manager object
        self.mock_ndb = mock.patch.object(linux_net.pyroute2, 'NDB').start()
        self.fake_ndb = self.mock_ndb().__enter__()
        # Mock pyroute2.IPRoute context manager object
        self.mock_iproute = mock.patch.object(
            linux_net.pyroute2, 'IPRoute').start()
        self.fake_iproute = self.mock_iproute().__enter__()

        self.mock_exc = mock.patch.object(processutils, 'execute').start()

        # Helper variables used accross many tests
        self.ip = '10.10.1.16'
        self.ipv6 = '2002::1234:abcd:ffff:c0a8:101'
        self.dev = 'ethfake'
        self.mac = 'aa:bb:cc:dd:ee:ff'

    def test_route_create(self):
        fake_route = {'dst': 'default',
                      'oif': 1,
                      'table': 10,
                      'scope': 253,
                      'proto': 3}
        priv_linux_net.route_create(fake_route)
        self.fake_ndb.routes.create.assert_called_once_with(fake_route)

    def test_route_delete(self):
        fake_route = mock.MagicMock()
        self.fake_ndb.routes.__getitem__.return_value = fake_route
        priv_linux_net.route_delete(fake_route)
        fake_route.__enter__().remove.assert_called_once_with()

    def test_route_delete_keyerror(self):
        fake_route = mock.MagicMock()
        self.fake_ndb.routes.__getitem__.side_effect = KeyError
        priv_linux_net.route_delete(fake_route)
        fake_route.__enter__().remove.assert_not_called()

    def test_rule_create(self):
        fake_rule = mock.MagicMock()
        self.fake_ndb.rules.__getitem__.side_effect = KeyError
        priv_linux_net.rule_create(fake_rule)
        self.fake_ndb.rules.create.assert_called_once_with(fake_rule)

    def test_rule_create_existing(self):
        fake_rule = mock.MagicMock()
        self.fake_ndb.rules.__getitem__.return_value = fake_rule
        priv_linux_net.rule_create(fake_rule)
        self.fake_ndb.rules.create.assert_not_called()

    def test_rule_delete(self):
        fake_rule = mock.MagicMock()
        rules_dict = {'fake-rule': fake_rule}
        self.fake_ndb.rules = rules_dict
        priv_linux_net.rule_delete('fake-rule')
        fake_rule.remove.assert_called_once()

    def test_rule_delete_keyerror(self):
        fake_rule = mock.MagicMock()
        self.fake_ndb.rules.__getitem__.side_effect = KeyError
        priv_linux_net.rule_delete(fake_rule)
        fake_rule.__enter__().remove.assert_not_called()

    def test_set_kernel_flag(self):
        priv_linux_net.set_kernel_flag('net.ipv6.conf.fake', 1)
        self.mock_exc.assert_called_once_with(
            'sysctl', '-w', 'net.ipv6.conf.fake=1')

    def test_set_kernel_flag_exception(self):
        self.mock_exc.side_effect = FakeException()
        self.assertRaises(
            FakeException,
            priv_linux_net.set_kernel_flag, 'net.ipv6.conf.fake', 1)

    def test_add_ndp_proxy(self):
        priv_linux_net.add_ndp_proxy(self.ipv6, self.dev)
        self.mock_exc.assert_called_once_with(
            'ip', '-6', 'nei', 'add', 'proxy', self.ipv6, 'dev', self.dev)

    def test_add_ndp_proxy_vlan(self):
        priv_linux_net.add_ndp_proxy(self.ipv6, self.dev, vlan=10)
        self.mock_exc.assert_called_once_with(
            'ip', '-6', 'nei', 'add', 'proxy', self.ipv6,
            'dev', '%s.10' % self.dev)

    def test_add_ndp_proxy_exception(self):
        self.mock_exc.side_effect = FakeException()
        self.assertRaises(
            FakeException,
            priv_linux_net.add_ndp_proxy, self.ipv6, self.dev)

    def test_del_ndp_proxy(self):
        priv_linux_net.del_ndp_proxy(self.ipv6, self.dev)
        self.mock_exc.assert_called_once_with(
            'ip', '-6', 'nei', 'del', 'proxy', self.ipv6, 'dev',
            self.dev, env_variables=mock.ANY)

    def test_del_ndp_proxy_vlan(self):
        priv_linux_net.del_ndp_proxy(self.ipv6, self.dev, vlan=10)
        self.mock_exc.assert_called_once_with(
            'ip', '-6', 'nei', 'del', 'proxy', self.ipv6, 'dev',
            '%s.10' % self.dev, env_variables=mock.ANY)

    def test_del_ndp_proxy_exception(self):
        self.mock_exc.side_effect = FakeException()
        self.assertRaises(
            FakeException,
            priv_linux_net.del_ndp_proxy, self.ipv6, self.dev)

    def test_del_ndp_proxy_exception_no_such_file(self):
        exp = FakeException()
        exp.stderr = 'No such file or directory'
        self.mock_exc.side_effect = exp
        self.assertIsNone(priv_linux_net.del_ndp_proxy(self.ipv6, self.dev))

    def test_add_ip_nei(self):
        priv_linux_net.add_ip_nei(self.ip, self.mac, self.dev)

        self.fake_iproute.link_lookup.assert_called_once_with(ifname=self.dev)
        self.fake_iproute.neigh.assert_called_once_with(
            'replace', dst=self.ip, lladdr=self.mac,
            ifindex=mock.ANY, state=mock.ANY)

    def test_add_ip_nei_ipv6(self):
        priv_linux_net.add_ip_nei(self.ipv6, self.mac, self.dev)

        self.fake_iproute.link_lookup.assert_called_once_with(ifname=self.dev)
        self.fake_iproute.neigh.assert_called_once_with(
            'replace', dst=self.ipv6, family=AF_INET6,
            lladdr=self.mac, ifindex=mock.ANY, state=mock.ANY)

    def test_del_ip_nei(self):
        priv_linux_net.del_ip_nei(self.ip, self.mac, self.dev)

        self.fake_iproute.link_lookup.assert_called_once_with(ifname=self.dev)
        self.fake_iproute.neigh.assert_called_once_with(
            'del', dst=self.ip, lladdr=self.mac,
            ifindex=mock.ANY, state=mock.ANY)

    def test_del_ip_nei_ipv6(self):
        priv_linux_net.del_ip_nei(self.ipv6, self.mac, self.dev)

        self.fake_iproute.link_lookup.assert_called_once_with(ifname=self.dev)
        self.fake_iproute.neigh.assert_called_once_with(
            'del', dst=self.ipv6, family=AF_INET6,
            lladdr=self.mac, ifindex=mock.ANY, state=mock.ANY)

    def test_del_ip_nei_index_error(self):
        self.fake_iproute.link_lookup.side_effect = IndexError
        priv_linux_net.del_ip_nei(self.ip, self.mac, self.dev)

        self.fake_iproute.link_lookup.assert_called_once_with(ifname=self.dev)
        self.fake_iproute.neigh.assert_not_called()

    def test_add_unreachable_route(self):
        priv_linux_net.add_unreachable_route('fake-vrf')
        calls = [mock.call('ip', -4, 'route', 'add', 'vrf', 'fake-vrf',
                           'unreachable', 'default', 'metric', '4278198272',
                           env_variables=mock.ANY),
                 mock.call('ip', -6, 'route', 'add', 'vrf', 'fake-vrf',
                           'unreachable', 'default', 'metric', '4278198272',
                           env_variables=mock.ANY)]
        self.mock_exc.assert_has_calls(calls)

    def test_add_unreachable_route_exception(self):
        self.mock_exc.side_effect = FakeException()
        self.assertRaises(
            FakeException,
            priv_linux_net.add_unreachable_route, 'fake-vrf')

    def test_add_unreachable_route_exception_file_exists(self):
        exp = FakeException()
        exp.stderr = 'RTNETLINK answers: File exists'
        self.mock_exc.side_effect = exp
        self.assertIsNone(priv_linux_net.add_unreachable_route('fake-vrf'))

    @mock.patch('builtins.open', new_callable=mock.mock_open())
    def test_create_routing_table_for_bridge(self, mock_o):
        priv_linux_net.create_routing_table_for_bridge(17, 'fake-bridge')
        mock_o.assert_called_once_with('/etc/iproute2/rt_tables', 'a')
        mock_o().__enter__().write.assert_called_once_with('17 fake-bridge\n')
