# -*- coding: utf-8 -*-

# This file is part of Archdiffer and is released under
# the MIT License: http://www.opensource.org/licenses/mit-license.php

"""
Created on Fri May 18 13:13:29 2018

@author: Pavla Kratochvilova <pavla.kratochvilova@gmail.com>
"""

import time
import datetime
import requests
import pytz
from ....tests import RESTTest
from .... import database
from .tests_rest_constants import ROUTES

class RESTTestRpmdiffPostComparison(RESTTest):
    """Tests for posting comparison."""
    route = ROUTES['comparisons']

    def fill_db(self):
        """Fill database. Called in setUp."""
        db_session = database.session()
        comparison_types = [database.ComparisonType(id=1, name='rpmdiff')]
        db_session.add_all(comparison_types)
        db_session.commit()
        db_session.close()

    data = {
        'pkg1': {
            'name': 'python3',
            'arch': 'x86_64',
            'epoch': 0,
            'version': '3.5.2',
            'release': '4.fc25',
            'repository': (
                'http://mirror.karneval.cz/pub/fedora/linux/releases/'
                '25/Everything/x86_64/os/'
            ),
        },
        'pkg2': {
            'name': 'python3',
            'arch': 'x86_64',
            'epoch': 0,
            'version': '3.6.1',
            'release': '8.fc26',
            'repository': (
                'http://mirror.karneval.cz/pub/fedora/linux/releases/'
                '26/Everything/x86_64/os/'
            ),
        }
    }

    def assert_comparison(self, location):
        """Assert that comparison at the given location is well formed.

        :param string location: url to the comparison
        """
        r = requests.get(location)
        self.assertEqual(r.status_code, requests.codes.ok)
        response = r.json()
        self.assertEqual(len(response), 1)
        self.assertIn('id', response[0])
        self.assertIn('state', response[0])
        self.assertIn('type', response[0])
        self.assertIn('time', response[0])
        self.assertEqual(response[0]['type'], 'rpmdiff')
        response_time = pytz.utc.localize(
            datetime.datetime.strptime(
                response[0]['time'], '%Y-%m-%d %H:%M:%S'
            )
        )
        self.assertGreaterEqual(
            response_time, self.time_before - datetime.timedelta(seconds=1)
        )
        self.assertLessEqual(response_time, self.time_after)

    def wait_for_compare(self, location, timeout=600):
        """Wait until the comparison is done.

        :param string location: url to the comparison
        :param int timeout: how long should wait for the comparison to complete
        :return dict: dict of the finished comparison
        """
        while timeout > 0:
            r = requests.get(location)
            response = r.json()
            if response[0]['state'] == 'done':
                return response[0]
            else:
                time.sleep(5)
                timeout -= 5
        return None

    def assert_rpm_package(self, response_pkg, expected_pkg):
        """Assert the package is as expected.

        :param dict response_pkg: the package dict from response
        :param dict expected_pkg: the package dict from initial data
        """
        self.assertIn('id', response_pkg)
        self.assertIn('name', response_pkg)
        self.assertIn('filename', response_pkg)
        self.assertIn('arch', response_pkg)
        self.assertIn('epoch', response_pkg)
        self.assertIn('version', response_pkg)
        self.assertIn('release', response_pkg)
        self.assertIn('repo', response_pkg)
        self.assertIn('id', response_pkg['repo'])
        self.assertIn('path', response_pkg['repo'])
        self.assertEqual(response_pkg['name'], expected_pkg['name'])
        self.assertEqual(response_pkg['arch'], expected_pkg['arch'])
        self.assertEqual(response_pkg['epoch'], expected_pkg['epoch'])
        self.assertEqual(response_pkg['version'], expected_pkg['version'])
        self.assertEqual(response_pkg['release'], expected_pkg['release'])
        self.assertEqual(
            response_pkg['repo']['path'], expected_pkg['repository']
        )

    def assert_rpm_comparison(self, rpm_comparison_id):
        """Assert that the rpm comparison is well formed.

        :param int rpm_comparison_id: id of the rpm comparison
        """
        self.get('%s/%s' % (self.route, rpm_comparison_id))
        self.assert_code_ok()
        self.assertEqual(len(self.response), 1)
        rpm_comp = self.response[0]
        self.assertIn('id', rpm_comp)
        self.assertIn('id_group', rpm_comp)
        self.assertIn('state', rpm_comp)
        self.assertIn('time', rpm_comp)
        self.assertIn('type', rpm_comp)
        self.assertIn('pkg1', rpm_comp)
        self.assertIn('pkg2', rpm_comp)
        self.assertEqual(
            rpm_comp['id_group'], self.final_comparison['id']
        )
        self.assertEqual(rpm_comp['time'], self.final_comparison['time'])
        self.assertEqual(rpm_comp['state'], 'done')
        self.assertEqual(rpm_comp['type'], 'rpmdiff')
        self.assert_rpm_package(rpm_comp['pkg1'], self.data['pkg1'])
        self.assert_rpm_package(rpm_comp['pkg2'], self.data['pkg2'])

    def test_post(self):
        """Test posting new comparison."""
        self.time_before = pytz.utc.localize(datetime.datetime.utcnow())
        self.post(route=self.route, data=self.data)
        self.time_after = pytz.utc.localize(datetime.datetime.utcnow())
        self.assertLessEqual(
            self.time_after - self.time_before, datetime.timedelta(seconds=1)
        )
        self.assert_code_eq(requests.codes.created)
        self.assert_comparison(self.headers['location'])

        # Wait for the comparison process to complete
        self.final_comparison = self.wait_for_compare(self.headers['location'])
        # TODO: assert the timeout didn't occur
        self.assert_comparison(self.headers['location'])
        for rpm_comparison in self.final_comparison['comparisons']:
            self.assert_rpm_comparison(rpm_comparison['id'])