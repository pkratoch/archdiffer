# -*- coding: utf-8 -*-

# This file is part of Archdiffer and is released under
# the MIT License: http://www.opensource.org/licenses/mit-license.php

"""
Created on Thu May 10 10:22:09 2018

@author: Pavla Kratochvilova <pavla.kratochvilova@gmail.com>
"""

import os
from tempfile import mkdtemp
from shutil import rmtree
import copy
import time
import subprocess
import unittest
import socket
import requests
import json
from ..config import config
from .. import database

_curdir = os.path.dirname(os.path.abspath(__file__))
_basedir = os.path.dirname(os.path.dirname(_curdir))
_frontend_launcher = 'debug_flask.py'

class RESTTest(unittest.TestCase):
    @classmethod
    def update_configfile(cls):
        """Update config with new database url and save to temporary test
        configfile.
        """
        # New database path
        cls.database_path = os.path.join(cls.tmpdir, 'test.db')
        cls.database_url = 'sqlite:///%s' % cls.database_path

        # Update config with database url
        config['common']['DATABASE_URL'] = cls.database_url

        # New config file
        cls.config_path = os.path.join(cls.tmpdir, 'test.conf')
        with open(cls.config_path, 'w') as configfile:
            config.write(configfile)

    @classmethod
    def random_port(cls):
        """Get random port for frontend. Save the whole url into baseurl.
        
        :return int port: random port
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('localhost', 0))
        port = sock.getsockname()[1]
        cls.baseurl = 'http://127.0.0.1:%s/' % port
        sock.close()
        return port

    @classmethod
    def wait_for_frontend_start(cls):
        """Repeatedly try request to ensure the frontend started. Otherwise
        raise an exception.

        :raise Exception: if frontend doesn't start in 5 seconds.
        """
        for i in range(50):
            time.sleep(0.1)
            try:
                requests.get(cls.baseurl + 'rest')
                break
            except requests.exceptions.ConnectionError:
                print('Waiting for frontend to start.')
        else:
            cls.cleanupClass()
            raise Exception("Frontend didn't start even after 5 seconds.")

    @classmethod
    def setUpClass(cls):
        """Update config; run frontend and backend."""
        # Make temporal directory to store database.
        cls.tmpdir = mkdtemp()

        # Update config with database url
        cls.update_configfile()

        # Create env with ARCHDIFFER_CONFIG
        cls.env = copy.copy(os.environ)
        cls.env.update({'ARCHDIFFER_CONFIG': cls.config_path})

        # Run frontend
        cls.frontend = subprocess.Popen(
            ['python3', _frontend_launcher, str(cls.random_port())],
            cwd=_basedir,
            env=cls.env,
        )

        # Run backend
        cls.backend = subprocess.Popen(
            ['python3', '-m', 'archdiffer.backend', 'worker', '-c', '1'],
            cwd=_basedir,
            env=cls.env,
        )

        # Wait for frontend to start
        cls.wait_for_frontend_start()

    def init_db(self):
        """Initialize database."""
        database.Base.metadata.create_all(database.engine(force_new=True))

    def fill_db(self):
        """Fill in database."""
        pass

    def create_test_user(self):
        """Add new user to the database and generate new api_login and
        api_token. Save the api_login and api_token into auth.
        """
        db_session = database.session()
        user = database.User.add(db_session, 'test_openid', 'test_username')
        user.new_token(
            db_session,
            size=int(config['web']['API_TOKEN_LENGTH']),
            token_expiration=int(config['web']['API_TOKEN_EXPIRATION']),
        )
        self.auth = (user.api_login, user.api_token)
        db_session.close()

    def setUp(self):
        """Create new database with test user."""
        # Initialize database
        self.init_db()

        # Fill in database
        self.fill_db()

        # Create user with api_login and api_token
        self.create_test_user()

    def get(self, route, params=None):
        """Send GET request and save response status code and data.

        :param string route: route to the source
        :param dict params: parameters to be passed in url
        """
        r = requests.get(self.baseurl + route, params=params)
        self.status_code = r.status_code
        try:
            self.response = r.json()
        except ValueError:
            self.response = None

    def post(self, route, data=None):
        """Send POST request and save response status code and data.

        :param string route: route to the source
        :param data: data of the request, will be jsonified
        """
        r = requests.post(
            self.baseurl + route, auth=self.auth, data=json.dumps(data),
        )
        self.status_code = r.status_code
        try:
            self.response = r.json()
        except ValueError:
            self.response = None

    def put(self, route, data=None):
        """Send PUT request and save response status code and data.

        :param string route: route to the source
        :param data: data of the request, will be jsonified
        """
        r = requests.put(
            self.baseurl + route, auth=self.auth, data=json.dumps(data),
        )
        self.status_code = r.status_code
        try:
            self.response = r.json()
        except ValueError:
            self.response = None

    def assert_code_eq(self, code):
        """Assert that response status code is equal to given code.

        :param int code: status code to compare to response
        """
        self.assertEqual(self.status_code, code)

    def assert_code_ok(self):
        """Assert that response status code is OK."""
        self.assert_code_eq(requests.codes.ok)

    def run_celery_inspect(self, inspect_type):
        """Run celery inspect utility and return its output.

        :param string inspect_type: first parameter to the celery inspect
        :return string: celery inspect output
        """
        return subprocess.check_output(
            ['celery-3', '-A', 'archdiffer.backend', 'inspect', inspect_type],
            cwd=_basedir,
            env=self.env,
        ).decode('utf-8')

    def check_inspect_output(self, inspect_output):
        """Check if all items in the inspect output are empty.

        :param string inspect_output: celery inspect output
        :return bool: True if all is empty
        """
        empty = True
        for line in inspect_output:
            if line.startswith('->') and not empty:
                # TODO: wait for the tasks to end
                return False
            elif line.startswith('->') and empty:
                empty = False
            elif 'empty' in line:
                empty = True
        return empty

    def wait_for_unfinished_tasks(self):
        """Wait for all active celery tasks to finish."""
        active_tasks = self.run_celery_inspect('active')
        while not self.check_inspect_output(active_tasks):
            active_tasks.stdout.close()
            time.sleep(0.5)
            active_tasks = self.run_celery_inspect('active')

    def tearDown(self):
        """Ensure there are no celery tasks remaining; remove database."""
        # Check there are no scheduled tasks
        scheduled_tasks = self.run_celery_inspect('scheduled')
        reserved_tasks = self.run_celery_inspect('reserved')
        active_tasks = self.run_celery_inspect('active')
        scheduled_empty = self.check_inspect_output(scheduled_tasks)
        reserved_empty = self.check_inspect_output(reserved_tasks)
        active_empty = self.check_inspect_output(active_tasks)

        # Remove messages from queues
        subprocess.call(
            ['celery-3', '-A', 'archdiffer.backend', 'purge', '-f'],
            cwd=_basedir,
            env=self.env,
        )

        # Wait for any unfinished active tasks
        self.wait_for_unfinished_tasks()

        # Determine if exception should be raised
        if not scheduled_empty or not reserved_empty or not active_empty:
            raise Exception

        # Remove the database.
        os.remove(os.path.join(self.tmpdir, 'test.db'))

    @classmethod
    def tearDownClass(cls):
        cls.cleanupClass()

    @classmethod
    def cleanupClass(cls):
        """Terminate frontend and backend; remove temporal files."""
        # Terminate frontend
        cls.frontend.terminate()
        cls.frontend.wait()

        # Terminate backend
        cls.backend.terminate()
        cls.backend.wait()

        # Remove the temporal directory.
        rmtree(cls.tmpdir)

if __name__ == '__main__':
    unittest.main()
