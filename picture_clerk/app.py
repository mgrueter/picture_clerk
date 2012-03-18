"""
@author: Matthias Grueter <matthias@grueter.name>
@copyright: Copyright (c) 2012 Matthias Grueter
@license: GPL

"""
import os
import logging

import repo

from connector import LocalConnector
from recipe import Recipe
from repo import Repo
from picture import Picture, get_sha1
from pipeline import Pipeline
from viewer import Viewer


log = logging.getLogger('pic.app')


class App(object):
    """PictureClerk's command line interface."""

    def __init__(self, connector, repo=None):
        self.connector = connector
        self.repo = repo

    def init_repo(self):
        """Initialize new repository."""
        repo_config = repo.new_repo_config()
        self.repo = Repo.create_on_disk(self.connector, repo_config)
        self.init_repo_logging(repo_config['logging.file'],
                               repo_config['logging.format'])
        log.info("Initialized empty PictureClerk repository")

    def load_repo(self):
        """Load existing repository from disk."""
        self.repo = Repo.load_from_disk(self.connector)
        self.init_repo_logging(self.repo.config['logging.file'],
                               self.repo.config['logging.format'])
        log.info("Loaded PictureClerk repository from disk")

    def add_pics(self, paths, process_enabled, process_recipe=None):
        """Add pictures to repository.
        
        Arguments:
        paths           -- the picture paths to be added
        process_enabled -- boolean flag if added pictures should be processed
        process_recipe  -- recipe to use for picture processing  
        
        """
        pics = [Picture(path) for path in paths if os.path.exists(path)]
        self.repo.index.add(pics)

        # process pictures                
        if process_enabled:
            log.info("Processing pictures.")
            # set up pipeline
            if not process_recipe:
                process_recipe = Recipe.fromString(
                                           self.repo.config['recipes.default'])
            pl = Pipeline('Pipeline1', process_recipe,
                          path=self.connector.url.path)
            for pic in pics:
                pl.put(pic)
            # process pictures
            pl.start()
            pl.join()

        log.info("Saving index to file.")
        try:
            self.connector.connect()
            self.repo.save_index_to_disk()
        finally:
            self.connector.disconnect()

    def remove_pics(self, files):
        """Remove pictures associated with supplied files from repo & disk."""
        pics = [self.repo.index[fname] for fname in files]
        self.repo.index.remove(pics)

        # remove all files associated with above pictures
        picfiles = (picfile for pic in pics
                            for picfile in pic.get_filenames())

        self.connector.connect()
        for picfile in picfiles:
            try:
                self.connector.remove(picfile)
            except OSError, e:
                if e.errno == 2: # ignore missing file (= already removed) error
                    log.debug("No such file: %s" % e.filename)
                else:
                    raise   # re-raise all other (e.g. permission error)

        log.info("Saving index to file.")
        self.repo.save_index_to_disk()
        self.connector.disconnect()

    def list_pics(self, mode):
        """Return information on pictures in repository."""
        if mode == "all":
            return '\n'.join(('%s' % str(pic)
                              for pic in self.repo.index.pics()))
        elif mode == "sidecars":
            return '\n'.join(('\n'.join(pic.get_sidecar_filenames())
                              for pic in self.repo.index.pics()))
        elif mode == "thumbnails":
            return '\n'.join(('\n'.join(pic.get_thumbnail_filenames())
                              for pic in self.repo.index.pics()))
        elif mode == "checksums":
            return '\n'.join(('%s *%s' % (pic.checksum, pic.filename)
                              for pic in self.repo.index.pics()))

    def view_pics(self, prog):
        """Launch viewer program and keep track of pictures deleted within."""
        if not prog:
            prog = self.repo.config['viewer.prog']
        v = Viewer(prog)
        deleted_pics = v.show(self.repo.index.pics())
        self.remove_pics([pic.filename for pic in deleted_pics])

    def migrate_repo(self):
        """Migrate repository from an old format to the current one."""
        log.info("Migrating repository to new format.")
        self.repo.config['index.format_version'] = repo.INDEX_FORMAT_VERSION
        try:
            self.connector.connect()
            self.repo.save_index_to_disk()
            self.repo.save_config_to_disk()
        finally:
            self.connector.disconnect()

    def check_pics(self):
        """Verify picture checksums. Return names of corrupt & missing pics."""
        corrupted = []
        missing = []
        try:
            self.connector.connect()
            for pic in self.repo.index.pics():
                try:
                    with self.connector.open(pic.filename, 'r') as buf:
                        checksum = get_sha1(buf.read())
                except (IOError, OSError):
                    missing.append(pic.filename)
                else:
                    if checksum != pic.checksum:
                        corrupted.append(pic.filename)
        finally:
            self.connector.disconnect()
        return corrupted, missing

    def init_repo_logging(self, log_file, log_format):
        # repo file logging (only if repo is local)
        if isinstance(self.connector, LocalConnector):
            log_path = os.path.join(self.connector.url.path, log_file)
            file_handler = logging.FileHandler(log_path)
            formatter = logging.Formatter(log_format)
            file_handler.setFormatter(formatter)
            logging.getLogger().addHandler(file_handler)

    def shutdown(self):
        log.info("Exiting...")
