# User rating support for Beets

The *beet userrating* plugin reads and manages a `userrating` tag on
your music files.

## Installation

Install package and scripts.

    $ pip install https://github.com/jphautin/beets-userrating/archive/master.zip

Add the plugin to beets configuration file.

```
plugins: (...) userrating
```

## Usage

    beet userrating -h
    Usage: beet userrating [options]
    Options:
     -h, --help   show this help message and exit

## FAQ

### Why not `beet rating`?

It turns out that the `mpdstats` plugin was already maintaining a
`rating` attribute.  It seemed easier to just adopt the `userrating`
nomenclature.

### What are the differences with Michael Alan Dorman repository ?

Major changes are:
- added support for WMA
- added a test suite
- add notion of scaler to be able to adapt value for any players
- add an import function (you can import rating on existing item of the library)

### Changes from Jean-Philippe repository
- Normalized rating styles from all types to an integer from 1-10
- Fixed some minor issues due to deprecated code
- Added MP3 support for MusicBee
- Added FLAC support for Amarok, Clementine
- Added option to export a playlist file with ratings
### Players supported

Players that are supported when importing ratings :

|           Player        | mp3 | wma | flac |
| ------------------------|-----|-----|------|
| Windows Media Player 9+ |  X  |     |      | 
| Banshee                 |  X  |     |      | 
| Media Monkey            |  X  |     |      | 
| Quod libet              |  x  |     |      | 
| Winamp                  |  x  |     |      | 
| MusicBee                |  x  |     |  x   |
| Amarok                  |     |     |  x   |
| Clementine              |     |     |  x   |

### Export Playlist file with Ratings
The android app Poweramp supports importing ratings from playlists that use
the `#EXT-X-RATING:<n>` metadata tag.
You can export that playlist file by modifying your config as follows:

```
plugins: userrating

userrating:
    ratings_file: '~/Music/all.m3u8'
```

And then running `beet ratingsfile`.
The file will also be updated automatically when the database changes.
The playlist will have paths relative to the file.

By including `%s` in the filename it will be replaced by a timestamp.
The plugin will attempt to delete up to one old file that matches the pattern
(`~/Music/*` will delete a random file, so prefix and suffix `%s`).
Use `%s` if in your usecase you need to know if the file has been updated.
Poweramp, for example, will only import new ratings if the playlist is new,
so your ratings will always be synced.
However, this will also cause the ratings you made in the app to be overwritten.
```
userrating:
    ratings_file: '~/Music/all.%s.m3u8'
```