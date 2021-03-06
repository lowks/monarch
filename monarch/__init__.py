# Core Imports
from datetime import datetime
import re
import os
import sys
import errno
import inspect
from importlib import import_module
from glob import glob
import collections

# 3rd Party Imports
import click
from click import echo

from .core import MongoBackedMigration, Migration

MIGRATION_TEMPLATE = '''
from monarch import {base_class}

class {migration_class_name}({base_class}):

    def run(self):
        """Write the code here that will migrate the database from one state to the next
            No Need to handle exceptions -- we will take care of that for you
        """
        raise NotImplementedError
'''

CAMEL_PAT = re.compile(r'([A-Z])')
UNDER_PAT = re.compile(r'_([a-z])')


class Config(object):

    MONGO = 'mongo'

    def __init__(self):
        self.migration_directory = None
        self.datastore = Config.MONGO

pass_config = click.make_pass_decorator(Config, ensure=True)

@click.group()
@click.option('--migration-directory', type=click.Path())
@pass_config
def cli(config, migration_directory):
    """ Your friendly migration manager

        To get help on a specific function you may append --help to the function
        i.e.
        monarch generate --help
    """
    if migration_directory is None:
        migration_directory = './migrations'
    config.migration_directory = migration_directory


@cli.command()
@click.argument('name')
@pass_config
def generate(config, name):
    """
    Generates a migration file.  pass it a name.  execute like so:

    monarch generate [migration_name]

    i.e.

    monarch generate add_indexes_to_user_collection

    """
    create_migration_directory_if_necessary(config.migration_directory)
    migration_name = generate_migration_name(config.migration_directory, name)
    class_name = "{}Migration".format(underscore_to_camel(name))
    output = MIGRATION_TEMPLATE.format(migration_class_name=class_name, base_class='MongoBackedMigration')
    with open(migration_name, 'w') as f:
        f.write(output)
    click.echo("Generated Migration Template: [{}]".format(migration_name))


@cli.command(name='list')
@pass_config
def lizt(config):
    """ Lists the migrations

    """
    migrations = find_migrations(config)
    if migrations:
        click.echo("The following migrations have not yet been applied:")
        for migration_name in migrations:
            click.echo(migration_name)
    else:
        click.echo("No pending migrations")


@cli.command()
@pass_config
def migrate(config):
    """
    Runs all migrations that have yet to have run.
    :return:
    """

    # 1) Find all migrations in the migrations/ directory
    # key = name, value = MigrationClass
    migrations = find_migrations(config)
    if migrations:
        for k, migration_class in migrations.iteritems():
            migration_instance = migration_class()

            # 3) Run the migration -- it will only run if it has not yet been run yet
            migration_instance.process()
    else:
        click.echo("No migrations exist")


def find_migrations(config):
    migrations = {}
    click.echo("fm 1 cwd: {}".format(os.getcwd()))
    for file in glob('{}/*_migration.py'.format(config.migration_directory)):
        migration_name = os.path.splitext(os.path.basename(file))[0]
        migration_module = import_module("migrations.{}".format(migration_name))
        for name, obj in inspect.getmembers(migration_module):
            if inspect.isclass(obj) and re.search('Migration$', name) and name not in ['BaseMigration', 'MongoBackedMigration']:
                migrations[migration_name] = obj

    # 2) Ensure that the are ordered
    ordered = collections.OrderedDict(sorted(migrations.items()))
    return ordered


def camel_to_underscore(name):
    return CAMEL_PAT.sub(lambda x: '_' + x.group(1).lower(), name)


def underscore_to_camel(name):
    return UNDER_PAT.sub(lambda x: x.group(1).upper(), name.capitalize())


def generate_migration_name(folder, name):
    # Can not start with a number so starting with a underscore
    rel_path = "{folder}/_{timestamp}_{name}_migration.py".format(
        folder=folder,
        timestamp=datetime.utcnow().strftime('%Y%m%d%H%M'),
        name=name
    )
    return os.path.abspath(rel_path)


def create_migration_directory_if_necessary(dir):
    try:
        os.makedirs(dir)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

    try:
        with open(os.path.join(os.path.abspath(dir), '__init__.py'), 'w') as f:
            f.write('# this file makes migrations a package')
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise




#
# @manager.command
# def test_migration():
#     """
#     This will copy either staging or production database your local database
#     Run the pending migrations
#     :return:
#     """
#     raise NotImplementedError
#
#


