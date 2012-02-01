#!/usr/bin/env python
"""
Created on 2012/01/01

@author: Matthias Grueter <matthias@grueter.name>
@copyright: Copyright (c) 2012 Matthias Grueter
@license: GPL

"""
import os
import optparse
import logging
import urlparse

import config

from local_connector import LocalConnector
from recipe import Recipe
from repo import Repo
from repo_handler import RepoHandler
from picture import Picture
from pipeline import Pipeline


class App(object):
    """PictureClerk's command line interface."""

    def __init__(self, connector, config_file, index_file):
        self.connector = connector
        self.config_file = config_file
        self.index_file = index_file
        self.repo = None
        self.repo_handler = None

    def _load_config_from_disk(self):
        self.connector.connect()
        with self.connector.open(self.config_file, 'r') as config_fh:
            self.repo_handler.load_config(config_fh)

    def _dump_config_to_disk(self):
        self.connector.connect()
        with self.connector.open(self.config_file, 'w') as config_fh:
            self.repo_handler.save_config(config_fh)

    def _load_index_from_disk(self):
        self.connector.connect()
        with self.connector.open(self.index_file, 'r') as index_fh:
            self.repo_handler.load_index(index_fh)

    def _save_index_to_disk(self):
        self.connector.connect()
        with self.connector.open(self.index_file, 'w') as index_fh:
            self.repo_handler.save_index(index_fh)

    def init(self):
        logging.debug("Initializing repository")
        self.repo = Repo()
        self.repo_handler = RepoHandler(self.repo,
                                        RepoHandler.create_default_config())
        RepoHandler.init_dir(self.repo_handler, self.connector)

    def add_pics(self, paths, process_enabled, process_recipe=None):
        """Add pictures to repository.
        
        Arguments:
        paths           -- the picture paths to be added
        process_enabled -- boolean flag if added pictures should be processed
        process_recipe  -- recipe to use for picture processing  
        
        """
        self.repo = Repo()
        self.repo_handler = RepoHandler(self.repo)
        self._load_config_from_disk()
        self._load_index_from_disk()

        pics = [Picture(path) for path in paths if os.path.exists(path)]
        self.repo.add_pictures(pics)

        # process pictures                
        if process_enabled:
            logging.debug("Processing pictures.")
            # set up pipeline
            if not process_recipe:
                process_recipe = Recipe.fromString(
                             self.repo_handler.config.get("recipes", "default"))
            pl = Pipeline('Pipeline1', process_recipe,
                          path=self.connector.url.path,
                          logdir=config.LOGDIR)
            for pic in pics:
                pl.put(pic)
            # process pictures
            pl.start()
            pl.join()
        
        logging.debug("Saving index to file.")
        self._save_index_to_disk()

    def list_pics(self):
        """List pictures in repository."""
        self.repo = Repo()
        self.repo_handler = RepoHandler(self.repo)
        self._load_config_from_disk()
        self._load_index_from_disk()
        for pic in sorted(self.repo.index.itervalues()):
            print pic

    def parse_command_line(self):
        """Parse command line (sys.argv) and return the parsed args & opts.
        
        Returns:
        cmd       -- PictureClerk command (e.g. init, add, list)
        args      -- CLI positional arguments (excluding cmd)
        verbosity -- the desired logging verbosity
        
        """
        usage = "Usage: %prog [-v|--verbose] <command> [<args>]\n\n"\
        "Commands:\n"\
        "  add     add picture files to the repository\n"\
        "  init    create an empty repository\n"\
        "  list    list of pictures in repository"
        parser = optparse.OptionParser(usage)
        parser.add_option("-v", "--verbose", dest="verbosity", action="count", 
                          help="increase verbosity (also multiple times)")
        
        # Options for the 'clone' command
        add_opts = optparse.OptionGroup(parser, "Add options",
                                 "Options for the add command.")
        add_opts.add_option("-n", "--noprocess",
                              action="store_false", dest="process_enabled",
                              help="do not process added files")
        add_opts.add_option("-r", "--recipe",
                              action="store", dest="process_recipe",
                              metavar="RECIPE",
                              help="comma sep. list of processing instructions")
        parser.add_option_group(add_opts)

        parser.set_defaults(process_enabled=True, process_recipe=None)
        
        opt, args = parser.parse_args()
        if not args:
            parser.error("no command given")
        cmd = args.pop(0)
        return cmd, args, opt.verbosity, opt.process_enabled, opt.process_recipe
    
    def init_logging(self, verbosity):
        """Configure logging module with supplied verbosity.
        
        Arguments:
        verbosity -- loglevel according to  0 -> warning, 1 -> info, 2 -> debug
        
        """
        log_level = logging.WARNING  # default
        if verbosity == 1:
            log_level = logging.INFO
        elif verbosity >= 2:
            log_level = logging.DEBUG
        # Basic configuration, out to stderr with a reasonable default format.
        logging.basicConfig(level=log_level)


    @staticmethod
    def main():
        url = urlparse.urlparse('.')
        connector = LocalConnector(url)
        app = App(connector, config_file=config.CONFIG_FILE,
                  index_file=config.INDEX_FILE)
        cmd, args, verbosity, process_enabled, process_recipe \
            = app.parse_command_line()
        app.init_logging(verbosity)

        if cmd == "init":
            app.init()
        elif cmd == "add":
            app.add_pics(args, process_enabled, process_recipe)
        elif cmd == "list":
            app.list_pics()
        else:
            logging.error("invalid command: %s" % cmd)


if __name__ == "__main__":
    import sys
    try:
        App.main()
    except KeyboardInterrupt:
        sys.exit(None)