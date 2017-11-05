# -*- coding: utf-8 -*-
"""
Created on Wed Aug 30 14:55:56 2017

@author: pavla
"""

from flask import render_template, request, flash, redirect, url_for, g
from flask import session as flask_session
from .flask_app import flask_app
from ..database import session, Comparison, Plugin

def my_render_template(html, **arguments):
    arguments.setdefault('plugins', g.session.query(Plugin).order_by(Plugin.id))
    return render_template(html, **arguments)

@flask_app.before_request
def before_request():
    """Get new database session for each request."""
    g.session = session()

@flask_app.teardown_request
def teardown_request(exception):
    """Commit and close database session at the end of request."""
    session = getattr(g, 'session', None)
    if session is not None:
        try:
            session.commit()
        except:
            pass
        finally:
            session.close()

@flask_app.route('/')
def index():
    comparisons = g.session.query(Comparison).order_by(Comparison.id).all()
    return my_render_template('show_comparisons.html', comparisons=comparisons)

@flask_app.route('/plugins')
def show_plugins():
    return my_render_template('show_plugins.html')

@flask_app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form['username'] != flask_app.config['USERNAME']:
            error = 'Invalid username'
        elif request.form['password'] != flask_app.config['PASSWORD']:
            error = 'Invalid password'
        else:
            flask_session['logged_in'] = True
            flash('You were logged in')
            return redirect(url_for('index'))
    return my_render_template('login.html', error=error)

@flask_app.route('/logout')
def logout():
    flask_session.pop('logged_in', None)
    flash('You were logged out')
    return redirect(url_for('index'))

