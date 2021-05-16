import mediafile
from mutagen.id3._frames import POPM

from beetsplug.banshee import Mp3BansheeScaler
from beetsplug.mm import Mp3MediaMonkeyScaler
from beetsplug.scaler import (Mp3BeetsScaler, Mp3MusicBeeScaler,
                              Mp3QuodlibetScaler, Mp3WinampScaler)
from beetsplug.wmp import Mp3WindowsMediaPlayerScaler

class MP3UserRatingStorageStyle(mediafile.MP3StorageStyle):
    """
    A codec for MP3 user ratings in files.

    Since we chose to use POPM as our baseline, we don't have to do
    any conversion, just look for the various possible tags

    """
    TAG = 'POPM'

    _KNOWN_EXTERNAL_SCALERS = [Mp3WindowsMediaPlayerScaler(), Mp3MediaMonkeyScaler(), Mp3BansheeScaler(),
                               Mp3QuodlibetScaler(),
                               Mp3WinampScaler(), Mp3MusicBeeScaler()]

    def __init__(self, **kwargs):
        self._log = kwargs.get('_log')
        self._is_external = kwargs.get('_is_external')
        super(MP3UserRatingStorageStyle, self).__init__(self.TAG)
        if self._is_external:
            self.scalers = MP3UserRatingStorageStyle._KNOWN_EXTERNAL_SCALERS
        else:
            self.scalers = [Mp3BeetsScaler()]

    def get(self, mutagen_file):
        # Create a map of all our email -> rating entries
        user_ratings = {frame.email: frame.rating for frame in mutagen_file.tags.getall(self.TAG)}
        for scaler in self.scalers:
            key = scaler.known(user_ratings)
            if key is not None:
                result = scaler.scale(user_ratings[key])
                return result
        return None

    def get_list(self, mutagen_file):
            raise NotImplementedError(u'MP3 Rating storage does not support lists')


    def set(self, mutagen_file, value):
        if value is not None:
            existing_ratings = {frame.email for frame in mutagen_file.tags.getall(self.TAG)}
            for scaler in self.scalers:
                if scaler.name in existing_ratings:
                    mutagen_file[self.TAG] = POPM(scaler.name, scaler.unscale(value))


    def set_list(self, mutagen_file, values):
        raise NotImplementedError(u'MP3 Rating storage does not support lists')

class AmarokRatingStorageStyle(mediafile.StorageStyle):
    """
    A codec for user ratings in FLAC files using the Amarok storage style
    format which is FMPS_RATING=0-1
    """

    TAG = 'FMPS_RATING'

    def __init__(self, **kwargs):
        self._log = kwargs.get('_log')
        self._is_external = kwargs.get('_is_external')
        super(AmarokRatingStorageStyle, self).__init__(self.TAG)

    def get(self, mutagen_file):
        if mutagen_file.tags.get(self.TAG) is None:
            return None

        return int(float(mutagen_file.get(self.TAG)[0]) * 10)

    def get_list(self, mutagen_file):
        raise NotImplementedError(u'UserRating storage does not support lists')

    def set(self, mutagen_file, value):
        if value is not None and 'audio/flac' in mutagen_file.mime:
            val = value / 10
            mutagen_file["FMPS_RATING"] = "%.1f" % val

    def set_list(self, mutagen_file, values):
        raise NotImplementedError(u'UserRating storage does not support lists')

class UserRatingStorageStyle(mediafile.StorageStyle):
    """
    A codec for user ratings in files using an accepted format (still not normalized)
    format which is RATING:[:@email]=value
    Note that for FLAC/ALAC, value seems to be between 0 and 100
    For other format, the 0 to 255 value still seems to be the accepted range.
    """

    TAG = 'RATING'

    def __init__(self, **kwargs):
        self._log = kwargs.get('_log')
        self._is_external = kwargs.get('_is_external')
        super(UserRatingStorageStyle, self).__init__(self.TAG)

    # The ordered list of which "email" entries we will look
    # for/prioritize in POPM tags.  Should eventually be configurable.
    popm_order = ["no@email", "Windows Media Player 9 Series", "rating@winamp.com", "", "Banshee"]

    def get(self, mutagen_file):
        max_value = 100 if 'audio/flac' in mutagen_file.mime else 255
        return next((int(float(mutagen_file.get(tag)[0]) / max_value * 10) for tag in self.popm_order if
                     mutagen_file.tags.get(self.TAG) is not None),
                    None)

    def get_list(self, mutagen_file):
        raise NotImplementedError(u'UserRating storage does not support lists')

    def set(self, mutagen_file, value):
        if value is not None:
            max_value = 100 if 'audio/flac' in mutagen_file.mime else 255
            val = value / 10 * max_value
            for user in self.popm_order:
                mutagen_file["RATING:{0}".format(user)] = str(val)

    def set_list(self, mutagen_file, values):
        raise NotImplementedError(u'UserRating storage does not support lists')


class ASFRatingStorageStyle(mediafile.ASFStorageStyle):
    """
    A codec for user ratings in ASF/WMA unsing Windows MEdia player tag format
    """

    TAG = 'WM/SharedUserRating'

    asf_order = ["no@email"]

    def __init__(self, **kwargs):
        self._log = kwargs.get('_log')
        self._is_external = kwargs.get('_is_external')
        super(ASFRatingStorageStyle, self).__init__(self.TAG)

    def get(self, mutagen_file):
        # Create a map of all our email -> rating entries
        if mutagen_file.tags.get(self.TAG) is not None:
            user_ratings = {frame.email: int(frame.rating) for frame in mutagen_file.tags.get(self.TAG)}
        else:
            user_ratings = {self.asf_order[0]: None}

        # Find the first entry from asf_order, or None
        return next((user_ratings.get(user) for user in self.asf_order if user in user_ratings), None)

    def get_list(self, mutagen_file):
        raise NotImplementedError(u'MP3 Rating storage does not support lists')

    def set(self, mutagen_file, value):
        if value is not None:
            for user in self.asf_order:
                tag = "{0}:{1}".format(self.TAG, user)
                mutagen_file[tag] = value

    def set_list(self, mutagen_file, values):
        raise NotImplementedError(u'MP3 Rating storage does not support lists')
