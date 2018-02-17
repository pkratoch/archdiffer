# -*- coding: utf-8 -*-
"""
Created on Sat Sep 16 22:54:57 2017

@author: pavla
"""

from flask import Blueprint, abort, request, flash, redirect, url_for, g
from flask import session as flask_session
from flask_restful import Api, Resource
from celery import Celery
from ..rpm_db_models import (RPMComparison, RPMDifference, RPMPackage,
                             RPMRepository, joined_query, iter_query_result)
from .. import constants
from ....flask_frontend.common_tasks import my_render_template
from ....flask_frontend.database_tasks import modify_query_by_request

celery_app = Celery(broker='pyamqp://localhost', )

bp = Blueprint(constants.COMPARISON_TYPE, __name__, template_folder='templates')
bp.config = {}
flask_api = Api(bp)

@bp.context_processor
def inject_constants():
    return vars(constants)

@bp.record
def record_params(setup_state):
    """Overwrite record_params only to keep app.config."""
    app = setup_state.app
    bp.config = dict(
        [(key, value) for (key, value) in app.config.items()]
    )

@bp.route('/')
def show_comparisons():
    comps = dict(iter_query_result(joined_query(g.db_session)))
    return my_render_template('rpm_show_comparisons.html', comparisons=comps)

@bp.route('/comparisons/<int:id_comp>')
def show_differences(id_comp):
    query = joined_query(g.db_session, RPMDifference).filter(RPMComparison.id==id_comp)
    comparison = dict(iter_query_result(query, RPMDifference))
    return my_render_template(
        'rpm_show_differences.html',
        comparison=comparison
    )

@bp.route('/packages/<int:pkg_id>')
def show_package(pkg_id):
    query = joined_query(g.db_session, RPMPackage).filter(RPMPackage.id==pkg_id)
    pkg = dict(iter_query_result(query, RPMPackage))[pkg_id]
    return my_render_template('rpm_show_package.html', pkg_id=pkg_id, pkg=pkg)

@bp.route('/repositories/<int:repo_id>')
def show_repository(repo_id):
    query = joined_query(g.db_session, RPMRepository).filter(RPMRepository.id==repo_id)
    repo = dict(iter_query_result(query, RPMRepository))[repo_id]
    return my_render_template(
        'rpm_show_repository.html', repo_id=repo_id, repo=repo
    )

@bp.route('/packages')
def show_packages():
    query = joined_query(g.db_session, RPMPackage)
    pkgs = dict(iter_query_result(query, RPMPackage))
    return my_render_template('rpm_show_packages.html', pkgs=pkgs)

@bp.route('/repositories')
def show_repositories():
    query = joined_query(g.db_session, RPMRepository)
    repos = dict(iter_query_result(query, RPMRepository))
    return my_render_template('rpm_show_repositories.html', repos=repos)

@bp.route('/add', methods=['POST'])
def add_entry():
    if 'openid' not in flask_session:
        abort(401)
    pkg1 = {
        'name': request.form['name1'],
        'arch': request.form['arch1'],
        'epoch': request.form['epoch1'],
        'version': request.form['version1'],
        'release': request.form['release1'],
        'repository': request.form['repo1'],
    }
    pkg2 = {
        'name': request.form['name2'],
        'arch': request.form['arch2'],
        'epoch': request.form['epoch2'],
        'version': request.form['version2'],
        'release': request.form['release2'],
        'repository': request.form['repo2'],
    }
    celery_app.send_task(
        'rpmdiff.compare', args=(pkg1, pkg2)
    )
    flash('New entry was successfully posted')
    return redirect(url_for('rpmdiff.show_comparisons'))

# Resources
class ShowRPMTable(Resource):
    def table_by_string(self, string_table):
        if string_table == "comparisons":
            return RPMComparison
        if string_table == "differences":
            return RPMDifference
        if string_table == "packages":
            return RPMPackage
        if string_table == "repositories":
            return RPMRepository

    def get(self, string_table):
        table = self.table_by_string(string_table)
        return dict(iter_query_result(modify_query_by_request(
            joined_query(g.db_session, table)), table
        ))

class ShowRPMTableItem(ShowRPMTable):
    def shown_table(self, table):
        if table == RPMDifference:
            return RPMComparison
        return table

    def get(self, string_table, id):
        table = self.table_by_string(string_table)
        query = joined_query(g.db_session, table).filter(self.shown_table(table).id == id)
        return dict(iter_query_result(modify_query_by_request(query), table))

flask_api.add_resource(ShowRPMTable, '/rest/<string:string_table>')
flask_api.add_resource(
    ShowRPMTableItem, '/rest/<string:string_table>/<int:id>'
)
