# Copyright 2017, Michael Dorman.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

import glob
import os
import time

import mediafile
from beets import plugins, ui
from beets.dbcore import types
from beets.dbcore.types import Integer
from beets.library import Item
from beets.util import (bytestring_path, mkdirall, normpath, path_as_posix,
                        sanitize_path, syspath)

from .rating_styles import (AmarokRatingStorageStyle, ASFRatingStorageStyle, DefaultValueStorageStyle,
                            MP3UserRatingStorageStyle, UserRatingStorageStyle)


class NullInteger(Integer):
    """Same as `Integer`, but does not normalize `None` to `0` but '-1'.
    """
    null = None


NULL_INTEGER = NullInteger()


class UserRatingsPlugin(plugins.BeetsPlugin):
    """
    A plugin for managing track ratings.

    We're using the POPM tag http://id3.org/id3v2.3.0#Popularimeter as
    our storage format (values 0-255, with 0 meaning no rating).
    """

    item_types = {
        'userrating': NULL_INTEGER,
        'externalrating': NULL_INTEGER
    }

    def __init__(self):
        super(UserRatingsPlugin, self).__init__()

        self.config.add({
            # Should we automatically import any values we find?
            'auto': True,
            # Should we overwrite an existing entry?
            'overwrite': False,
            # Should we sync others player ratings when updating a rating
            'sync_ratings': True,
            # SHould we save ratings to a playlist file? (Android Poweramp)
            'ratings_file': "",
            'forward_slash': False
        })

        # Add importing ratings to the import process
        if self.config['auto']:
            self.import_stages = [self.imported]

        # Given the complexity of the storage style implementations, I
        # find it handy to allow them to do unified logging.
        userrating_field = mediafile.MediaField(
            AmarokRatingStorageStyle(_log=self._log, _is_external=False),
            MP3UserRatingStorageStyle(_log=self._log, _is_external=False),
            UserRatingStorageStyle(_log=self._log, _is_external=False),
            ASFRatingStorageStyle(_log=self._log, _is_external=False),
            DefaultValueStorageStyle(_log=self._log, _is_external=True),
            out_type=int
        )

        externalrating_field = mediafile.MediaField(
            AmarokRatingStorageStyle(_log=self._log, _is_external=True),
            MP3UserRatingStorageStyle(_log=self._log, _is_external=True),
            UserRatingStorageStyle(_log=self._log, _is_external=True),
            ASFRatingStorageStyle(_log=self._log, _is_external=True),
            DefaultValueStorageStyle(_log=self._log, _is_external=True),
            out_type=int
        )

        if 'userrating' not in mediafile.MediaFile.__dict__:
            self.add_media_field('userrating', userrating_field)

        # this is only to be able to import existing value to beet userrating
        # and export/sync updated values.
        if 'externalrating' not in mediafile.MediaFile.__dict__:
            self.add_media_field('externalrating', externalrating_field)
        
        if self.config['ratings_file'].get():
            self.register_listener(
                "database_change", lambda lib, model: self.register_write_listener())

    def valid_rating(self, rating):
        return rating is not None and rating != 0

    # We do present a command, though it doesn't do anything as yet
    def commands(self):
        """
        Return the "userrating" ui subcommand.
        """

        cmd = ui.Subcommand('userrating', help=u'manage user ratings for tracks')
        cmd.func = lambda lib, opts, args: self.handle_tracks(lib.items(ui.decargs(args)), opts)
        cmd.parser.add_option(
            u'-u', u'--update', action='store',
            help=u'all files will be rated with given value',
        )
        cmd.parser.add_option(
            u'-i', u'--imported', action='store_true',
            help=u'all files will be rated if possible with known players value in file',
        )
        cmd.parser.add_option(
            u'-o', u'--overwrite', action='store_true',
            help=u'allow overwriting rated file (default is to skip already rated file)',
        )
        cmd.parser.add_option(
            u'-s',u'--sync', action='store',
            help=u'write rating for existing players rating (default is to not update any players rating but beets)',
        )
        cmd.parser.add_option(
            u'-a', u'--all', action='store_true',
            help=u'write rating for all known players (default is to not update any players rating but beets)',
        )

        cmd2 = ui.Subcommand(
            'ratingsfile', help=u'write library ratings to playlist file')
        cmd2.func = lambda lib, opts, args: self.write_ratings_file(lib)

        return [cmd, cmd2]

    def imported(self, session, task):
        """
        Add rating info to items of ``task`` during import.
        """
        class Object(object):
            pass
        opts = Object()
        opts.imported = True
        opts.update = False
        opts.overwrite = False
        opts.all = False
        opts.sync = False
        self.handle_tracks(task.imported_items(), opts)

    def handle_tracks(self, items, opts):
        """
        Abstract out our iteration code.
        """
        if len(items) == 0:
            self._log.warning("no item found.")
        for item in items:
            self.handle_track(item, opts)

    def handle_track(self, item, opts):
        """
        Ask for user rating for track and store it in the item.

        If user rating information is already present in the item,
        nothing is done unless ``overwrite`` has been set.
        """
        if opts.update is None and opts.imported is None:
            self.display_track_rating(item)
        else:
            if opts.imported:
                self.import_track_rating(item, opts)
            if opts.update:
                self.update_track_rating(item, opts)

    def display_track_rating(self, item):
        if 'userrating' in item:
            self._log.info(u'{0} is rated with {1}', item, item.userrating)
        else:
            self._log.warning(u'{0} is not rated', item)

    def import_track_rating(self, item, opts):
        should_write = ui.should_write()
        self._log.debug(u'Getting rating for {0}', item)
        # Get any rating already in the file
        rating = item.userrating if 'userrating' in item else None
        self._log.debug(u'Found rating value "{0}"', rating)
        imported_rating = item.externalrating if 'externalrating' in item else None
        self._log.debug(u'Found external rating value "{0}"', imported_rating)
        if self.valid_rating(imported_rating):
            if not self.valid_rating(rating) or opts.overwrite:
                item.userrating = int(imported_rating)
                if should_write and item.try_write():
                    item.store()
                    self._log.info(u'Applied rating {0}', imported_rating)
            else:
                # We should consider asking here
                self._log.info(u'skip already-rated track {0}', item.path)

    def update_track_rating(self, item, opts):
        should_write = ui.should_write()
        self._log.debug(u'Getting rating for {0}', item)
        # Get any rating already in the file
        rating = item.userrating if 'userrating' in item else None
        self._log.debug(u'Found rating value "{0}"', rating)
        if not self.valid_rating(rating) or opts.overwrite:
            item['userrating'] = int(opts.update)
            if opts.sync or opts.all:
                item['externalrating'] = int(opts.update)
            if should_write and item.try_write():
                item.store()
                self._log.info(u'Applied rating {0}', opts.update)
        else:
            # We should consider asking here
            self._log.info(u'skip already-rated track {0}', item.path)

    def register_write_listener(self):
        self.register_listener("cli_exit", self.write_ratings_file)

    def write_ratings_file(self, lib):
        """ Android Poweramp supports importing ratings from playlist files
            This function writes a playlist file containing all songs with
            metadata tag #EXT-X-RATING:<n>, where n is 1-5.
        """

        if not self.config["ratings_file"]:
            return
        # FIXME: Unsanitized rating file location
        rating_file = os.path.expanduser(bytestring_path(self.config["ratings_file"].get()))
        rating_dir = os.path.dirname(rating_file)
        if not os.path.exists(rating_dir):
            os.makedirs(rating_dir)

        # If the file has %s use a timestamp
        if "%s" in str(rating_file):
            old_files = glob.glob(rating_file % b"*")
            if len(old_files):
                # Remove up to one file to avoid surprises
                os.remove(old_files[0])
            rating_file = rating_file % bytearray(str(int(time.time())), "utf-8")


        ratings = {}
        for item in lib.items(""):
            # Grab rating
            userrating = None
            if 'userrating' in item:
                userrating = item.userrating
            elif 'externalrating' in item:
                userrating = item.externalrating
            
            # Add to dict
            if userrating is not None:
                item_path = os.path.relpath(item.path, rating_dir)
                ratings[item_path] = userrating

        # Write ratings to rating file
        with open(rating_file, 'wb') as f:
            for fn, rating in ratings.items():
                if self.config['forward_slash'].get():
                    fn = path_as_posix(fn)
                f.write(b"#EXT-X-RATING:" + bytes("%d" % (rating // 2), 'utf-8') 
                    + b"\n" + fn + b"\n")

        self._log.info(u"Wrote ratings to {0}", rating_file)
