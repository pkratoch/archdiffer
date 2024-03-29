# -*- coding: utf-8 -*-

# This file is part of Archdiffer and is released under
# the MIT License: http://www.opensource.org/licenses/mit-license.php

"""
Created on Wed Apr  5 19:32:41 2017

@author: Pavla Kratochvilova <pavla.kratochvilova@gmail.com>
"""

import datetime
import random
import string
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import (Column, Integer, String, DateTime, Date, ForeignKey,
                        func)
from sqlalchemy import create_engine
from sqlalchemy.orm import relationship
from sqlalchemy.orm.session import Session
from sqlalchemy.exc import IntegrityError
from .config import config
from .constants import STATE_NEW, STATE_STRINGS

Base = declarative_base()

class Comparison(Base):
    """Database model of comparisons."""
    __tablename__ = 'comparisons'

    id = Column(Integer, primary_key=True, nullable=False)
    # time is set when commited
    time = Column(DateTime, default=func.now())
    comparison_type_id = Column(
        Integer, ForeignKey('comparison_types.id'), nullable=False
    )
    state = Column(Integer, nullable=False, default=STATE_NEW)

    comparison_type = relationship(
        "ComparisonType", back_populates="comparisons"
    )

    def __repr__(self):
        return ("<Comparison(id='%s', time='%s', comparison_type_id='%s', "
                "state='%s')>") % (
                    self.id,
                    datetime.datetime.strftime(self.time, '%Y-%m-%d %H:%M:%S'),
                    self.comparison_type_id,
                    self.state,
                )

    def update_state(self, ses, state):
        """Add new Comparison.

        :param ses: session for communication with the database
        :type ses: qlalchemy.orm.session.Session
        :param int state: new state
        """
        self.state = state
        ses.add(self)
        ses.commit()

    @staticmethod
    def add(ses, comparison_type_name, state=STATE_NEW):
        """Add new Comparison.

        :param ses: session for communication with the database
        :type ses: qlalchemy.orm.session.Session
        :param int comparison_type_name: name of its comparison_type
        :param int state: state
        :return Comparison: newly added Comparison
        """
        comp_type_id = ComparisonType.get_cache(ses)[comparison_type_name]
        comparison = Comparison(comparison_type_id=comp_type_id, state=state)
        ses.add(comparison)
        ses.commit()
        return comparison

    @staticmethod
    def query(ses):
        """Query Comparison joined with its ComparisonType.

        :param ses: session for communication with the database
        :type ses: qlalchemy.orm.session.Session
        :return sqlalchemy.orm.query.Query: query
        """
        return ses.query(Comparison, ComparisonType).filter(
            Comparison.comparison_type_id == ComparisonType.id
        ).order_by(Comparison.id)

    @staticmethod
    def id_from_line(line):
        """Get Comparison id from line.

        :param line: named tuple (one item of query result) containing
            Comparison
        :return int: Comparison id
        """
        return line.Comparison.id

    @staticmethod
    def dict_from_line(line):
        """Get dict from line.

        :param line: named tuple (one item of query result) containing
            Comparison and its ComparisonType.
        :return dict: dict with Comparison and ComparisonType column values
        """
        result_dict = {
            'id': line.Comparison.id,
            'time': datetime.datetime.strftime(
                line.Comparison.time, '%Y-%m-%d %H:%M:%S'
            ),
            'state': STATE_STRINGS[line.Comparison.state],
        }
        result_dict['comparison_type'] = {
            'id': line.ComparisonType.id,
            'name': line.ComparisonType.name,
        }
        return result_dict

class ComparisonType(Base):
    """Database model of comparison types."""
    __tablename__ = 'comparison_types'

    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(String(255), nullable=False, unique=True)

    comparisons = relationship("Comparison", back_populates="comparison_type")

    _cache = {}

    def __repr__(self):
        return "<ComparisonType(id='%s', name='%s')>" % (self.id, self.name)

    @staticmethod
    def make_cache(ses):
        for comp_type in ComparisonType.query(ses).all():
            ComparisonType._cache[comp_type.name] = comp_type.id

    @staticmethod
    def get_cache(ses):
        if not ComparisonType._cache:
            ComparisonType.make_cache(ses)
        return ComparisonType._cache

    @staticmethod
    def query(ses):
        """Query ComparisonType.

        :param ses: session for communication with the database
        :type ses: qlalchemy.orm.session.Session
        :return sqlalchemy.orm.query.Query: query
        """
        return ses.query(ComparisonType).order_by(ComparisonType.id)

    @staticmethod
    def id_from_line(line):
        """Get ComparisonType id from line.

        :param ComparisonType line: ComparisonType
        :return int: ComparisonType id
        """
        return line.id

    @staticmethod
    def dict_from_line(line):
        """Get dict from line.

        :param ComparisonType line: ComparisonType
        :return dict: dict with ComparisonType column values
        """
        result_dict = {
            'id': line.id,
            'name': line.name,
        }
        return result_dict

class User(Base):
    """Database model of users."""
    __tablename__ = 'users'

    openid = Column(String(255), primary_key=True, nullable=False)
    name = Column(String(255), nullable=False, unique=True)

    # For aunthentication in REST
    api_login = Column(String(40))
    api_token = Column(String(40))
    api_token_expiration = Column(
        Date, nullable=False, default=datetime.date(2000, 1, 1)
    )

    def __repr__(self):
        return ("<User(openid='%s', name='%s', api_login='%s', "
                "api_token='%s', api_token_expiration='%s')>") % (
            self.openid,
            self.name,
            self.api_login,
            self.api_token,
            self.api_token_expiration,
        )

    def generate_api_token(self, size=30):
        """Generate a random string used as login or token for REST API.

        :param int size: the size of the token to generate, defaults to
            30 chars
        :return string: the API token for the user
        """
        return ''.join(
            random.choice(string.ascii_lowercase) for x in range(size)
        )

    def new_token(self, ses, size=30, token_expiration=180):
        self.api_login = self.generate_api_token(size)
        self.api_token = self.generate_api_token(size)
        self.api_token_expiration = datetime.date.today() + datetime.timedelta(
            days=token_expiration
        )
        ses.add(self)
        ses.commit()

    @staticmethod
    def query(ses, openid=None, name=None, api_login=None):
        """Query User by openid, name or api_login.

        :param ses: session for communication with the database
        :type ses: qlalchemy.orm.session.Session
        :param string openid: openid
        :param string name: name
        :param string api_login: api_login
        :return sqlalchemy.orm.query.Query: query
        """
        if openid is not None:
            return ses.query(User).filter_by(openid=openid).first()
        elif name is not None:
            return ses.query(User).filter_by(name=name).first()
        elif api_login is not None:
            return ses.query(User).filter_by(api_login=api_login).first()
        else:
            return None

    @staticmethod
    def add(ses, openid, name):
        """Add user to the database if it doesn't already exist.

        :param ses: session for communication with the database
        :type ses: qlalchemy.orm.session.Session
        :param string openid: openid
        :param string name: name
        :param string email: email
        :return User: user
        """
        try:
            user = User(openid=openid, name=name)
            ses.add(user)
            ses.commit()
        except IntegrityError:
            ses.rollback()
            user = None
        return user

class SessionSingleton():
    """Singleton that provides sqlalchemy engine and creates sessions."""
    engine = None

    @staticmethod
    def init(force_new=False):
        """Create engine if None.

        :param bool force_new: if True, this will always create new instance of
            engine; this option should only be used for testing purposes
        """
        if SessionSingleton.engine is None or force_new:
            SessionSingleton.engine = create_engine(
                config['common']['DATABASE_URL'], echo=True
            )

    @staticmethod
    def deinit():
        """Force reloading engine."""
        SessionSingleton.engine = None

    @staticmethod
    def get_engine(force_new=False):
        """Get the engine.

        :param bool force_new: if True, this will always create new instance of
            engine; this option should only be used for testing purposes
        :return sqlalchemy.engine.Engine: engine
        """
        SessionSingleton.init(force_new)
        return SessionSingleton.engine

    @staticmethod
    def get_session(*args, **kwargs):
        """Create new session.

        :param *args: arguments to be passed when creating session
        :param **kwargs: keyword arguments to be passed when creating session
        :return sqlalchemy.orm.session.Session: session
        """
        return Session(*args, bind=SessionSingleton.get_engine(), **kwargs)

def engine(force_new=False):
    """Get the engine.

    :param bool force_new: if True, this will always create new instance of
        engine; this option should only be used for testing purposes
    :return sqlalchemy.engine.Engine: engine
    """
    return SessionSingleton.get_engine(force_new)

def session(*args, **kwargs):
    """Get new session.

    :param *args: arguments to be passed when creating session
    :param **kwargs: keyword arguments to be passed when creating session
    :return sqlalchemy.orm.session.Session: session
    """
    return SessionSingleton.get_session(*args, **kwargs)

def modify_query(query, modifiers):
    """Modify query according to the modifiers.

    :param sqlalchemy.orm.query.Query query: query to be modified
    :param dict modifiers: dict of modifiers and their values
    :return sqlalchemy.orm.query.Query: modified query
    """
    if modifiers is None:
        return query
    if 'filter_by' in modifiers:
        query = query.filter_by(**modifiers['filter_by'])
    if 'filter' in modifiers:
        query = query.filter(*modifiers['filter'])
    if 'order_by' in modifiers:
        query = query.order_by(*modifiers['order_by'])
    if 'limit' in modifiers:
        query = query.limit(modifiers['limit'])
    if 'offset' in modifiers:
        query = query.offset(modifiers['offset'])
    return query

def general_iter_query_result(result, group_id, group_dict,
                              line_dict=None, name=None):
    """Process query result.

    :param sqlalchemy.orm.query.Query result: query
    :param callable group_id: function getting id from line of the result
    :param callable group_dict: function getting dict from line of the result;
        will be called each time id changes
    :param callable line_dict: function for geting dict from line of the
        result; will be called for every line and agregated into list
    :param string name: desired name of the list resulting from the aggregation
    :return Iterator[dict]: iterator of resulting dict
    """
    last_id = None
    result_dict = None
    outerjoin_items = []

    for line in result:
        if last_id is None:
            # Save new id and dict
            last_id = group_id(line)
            result_dict = group_dict(line)
        if group_id(line) != last_id:
            # Add aggregated list and yield
            if line_dict is not None and result_dict is not None:
                result_dict[name] = outerjoin_items
            yield result_dict
            # Save new id and dict
            last_id = group_id(line)
            result_dict = group_dict(line)
            outerjoin_items = []
        if line_dict is not None:
            item = line_dict(line)
            if item is not None:
                outerjoin_items.append(item)
    # Add aggregated list and yield
    if line_dict is not None and result_dict is not None:
        result_dict[name] = outerjoin_items
    if last_id is not None:
        yield result_dict

def iter_query_result(result, table):
    """Call general_iter_query_result based on given table.

    :param sqlalchemy.orm.query.Query result: query
    :param sqlalchemy.ext.declarative.api.declarativemeta table: database model

    :return: iterator of resulting dict from general_iter_query_result
    :rtype: Iterator[dict]
    """
    group_id = table.id_from_line
    group_dict = table.dict_from_line
    line_dict = None
    name = None

    return general_iter_query_result(
        result, group_id, group_dict, line_dict=line_dict, name=name
    )
