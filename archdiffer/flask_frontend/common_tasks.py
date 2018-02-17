# -*- coding: utf-8 -*-
"""
Created on Wed Aug 30 14:55:56 2017

@author: pavla
"""

from flask import render_template, request, flash, redirect, url_for, g
from flask import session as flask_session
from flask_openid import OpenID
from .flask_app import flask_app
from ..database import session as db_session
from ..database import ComparisonType, User

oid = OpenID(flask_app, '/tmp', safe_roots=[])

def my_render_template(html, **arguments):
    """Call render_template with comparison_types as one of the arguments."""
    arguments.setdefault(
        'comparison_types', ComparisonType.query(g.db_session)
    )
    return render_template(html, **arguments)

@flask_app.before_request
def new_database_session():
    """Get new database session for each request."""
    g.db_session = db_session()

@flask_app.before_request
def lookup_current_user():
    """Get user for the request."""
    g.user = None
    if 'openid' in flask_session:
        g.user = User.query_by_openid(g.db_session, flask_session['openid'])

@flask_app.teardown_request
def close_database_session(exception):
    """Commit and close database session at the end of request."""
    ses = getattr(g, 'db_session', None)
    if ses is not None:
        try:
            ses.commit()
        except:
            pass
        finally:
            ses.close()

@flask_app.route('/login', methods=['GET', 'POST'])
@oid.loginhandler
def login():
    if g.user is not None:
        return redirect(oid.get_next_url())
    if request.method == 'POST':
        openid = request.form.get('openid')
        if openid:
            return oid.try_login(
                openid,
                ask_for=['email', 'nickname'],
                ask_for_optional=['fullname']
            )
    return my_render_template('login.html', next=oid.get_next_url(),
                              error=oid.fetch_error())

@oid.after_login
def create_or_login(resp):
    flask_session['openid'] = resp.identity_url
    user = User.query_by_openid(g.db_session, resp.identity_url)
    if user is not None:
        flash(u'Successfully signed in')
        g.user = user
        return redirect(oid.get_next_url())
    return redirect(url_for('create_profile', next=oid.get_next_url(),
                            name=resp.fullname or resp.nickname,
                            email=resp.email))

@flask_app.route('/create-profile', methods=['GET', 'POST'])
def create_profile():
    if g.user is not None or 'openid' not in flask_session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        if not name:
            flash(u'Error: you have to provide a name')
        elif '@' not in email:
            flash(u'Error: you have to enter a valid email address')
        else:
            flash(u'Profile successfully created')
            User.add(g.db_session, flask_session['openid'], name, email)
            return redirect(oid.get_next_url())
    return render_template('create_profile.html', next=oid.get_next_url())

@flask_app.route('/logout')
def logout():
    flask_session.pop('openid', None)
    flash(u'You were signed out')
    return redirect(oid.get_next_url())
