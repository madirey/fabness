from contextlib import contextmanager
from fabric import api as fab_api
from fabric.api import env, execute, local, run, sudo
from fabric.context_managers import cd, hide, lcd, prefix, settings
from fabric.decorators import task
from fabric.operations import prompt, put, get
from fabric.utils import abort

import json
import os
import shutil


AUTOMATION_DIR = 'auto' # TODO: make configurable
DEFAULT_TARGET = 'test'


def _resolve(unformatted):
    ''' Formats a string or list of strings using the env dict, and returns the formatted string. '''
    if isinstance(unformatted, basestring):
        formatted = unformatted % env
    else:
        # assume list/tuple
        formatted = []
        for el in unformatted:
            if isinstance(el, basestring):
                formatted.append(el % env)
            else:
                formatted.append('null')
    return formatted

@contextmanager
def _apply_context(ctx_):
    ''' Applies a `fabric.context_managers.<ctx_[0]>` context to a set of commands. '''
    if ctx_:
        f = globals()[ctx_[0]] # fabric context manager?  TODO: make this secure
        args = _resolve(ctx_[1])
        with f(*args):
            yield
    else:
        yield

@contextmanager
def _apply_cd(dir_):
    ''' Applies a `fabric.context_managers.cd` context to a set of commands. '''
    if dir_:
        with cd(_resolve(dir_)):
            yield
    else:
        yield

def _load_config(config_file, inject=True):
    ''' Loads a `build` from the json config files and optionally injects the data into the env. '''
    with open(config_file) as fp:
        json_data = json.load(fp)
    if inject:
        env.update(json_data)
    return json_data

# "Template" function for constructing custom fabric tasks.
# This is where all the magic happens.  Woohoo!
def _build(target):
    ''' Runs a build target. '''
    _task_name = env['command']
    print 'running %s for %s' % (_task_name, target)

    # load config for target and task
    json_data = _load_config(os.path.join(AUTOMATION_DIR, target, 'common.json'))
    json_data = _load_config(os.path.join(AUTOMATION_DIR, target, '%s.json' % _task_name))

    # prepare build environment
    shutil.rmtree(env['build_dir'], ignore_errors=True)
    os.mkdir(env['build_dir'])

    # carry out build stages
    # Note: DEEP nesting here, but many of these are context managers and not
    # loops.  This seems to be a necessary evil for this level of abstraction.
    # Even so, runtime performance does not seem to be an issue, as the total
    # number of applied operations is not large.
    try:
        with lcd(env['build_dir']):
            for stage in env['stages']:
                if stage.get('enabled', 1): # don't run stages that are marked `disabled`
                    print _resolve(stage['desc'])
                    with _apply_context(stage.get('context', None)):
                        with _apply_cd(stage.get('remote_dir', None)):
                            for substage in stage['substages']:
                                fab_cmnd = substage[0] # one of: local, run, sudo
                                if not fab_cmnd in ['local', 'run', 'sudo']:
                                    abort('Invalid fab command: %s' % fab_cmnd)
                                cmnd = _resolve(substage[1]) # the command to execute
                                for host in env['hosts']:
                                    with settings(host_string=host):
                                        getattr(fab_api, fab_cmnd)(cmnd) # dynamically execute the command
    finally:
        # clean up build environment
        shutil.rmtree(env['build_dir'])
    print 'finished running %s for %s' % (_task_name, target)


############# MAIN EXECUTION ################

#############################
# LOAD BUILD CONFIGURATIONS
#############################
available_tasks = [f.replace('.json', '') for f in os.listdir(os.path.join(AUTOMATION_DIR, 'common'))]
available_targets = [d for d in os.listdir(AUTOMATION_DIR) \
                     if os.path.isdir(os.path.join(AUTOMATION_DIR, d)) and not d == 'common']

# dynamically construct a fabric task for each build task found
for task_name in available_tasks:
    # load common configuration dynamic task instantiation
    json_data = _load_config(os.path.join(AUTOMATION_DIR, 'common', '%s.json' % task_name), inject=False)
    task_desc = json_data['meta']['desc']

    # construct new task and inject into global namespace so fab can find it
    f = lambda t=DEFAULT_TARGET: _build(t) # create a lambda from `_build` template
    f.__name__ = task_name # rename lambda
    f.__doc__ = task_desc # re-doc lambda
    globals()[f.__name__] = task(f) # decorate the lambda and inject into global namespace for fab to find

# load universal common configuration
_load_config(os.path.join(AUTOMATION_DIR, 'common.json'))

# fab task will be executed after this point
