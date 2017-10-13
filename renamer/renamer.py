#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import sys
import stat
import shutil
import string
import fnmatch
import requests
import discogs_client
from optparse import OptionParser
from mutagen.flac import FLAC, Picture
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.id3 import ID3, TIT2, TPE1, TYER, TALB, APIC, PictureType
from PIL import Image
from math import trunc
import settings
from utils import *


d = discogs_client.Client(settings.APPLICATION_NAME,
    user_token=settings.DISCOGS_USER_TOKEN)


def prepare_tags(prepared_tracks, file_counter, fetched_release_info):
    track_title_raw = re.sub(
        '([a-zA-Z])',
        lambda x: x.groups()[0].upper(),
        prepared_tracks[file_counter].title.strip(),
        1
    )
    track_title = track_title_raw.replace("(", "[").replace(")", "]").\
        replace("Remix", "remix").replace("Mix", "mix").replace("Edit", "edit").\
        replace("Version", "version").replace("Cover", "cover")
    track_artist_raw = prepared_tracks[file_counter].artists[0].name.\
        title().strip() if prepared_tracks[file_counter].\
        artists else fetched_release_info["artist"]
    track_artist = re.sub(r"\(\d+\)", '', track_artist_raw).strip()
    if prepared_tracks[file_counter].artists and len(
        prepared_tracks[file_counter].artists) > 1:
        track_artist = "{} & {}".format(
            prepared_tracks[file_counter].artists[0].name.title().strip(),
            prepared_tracks[file_counter].artists[1].name.title().strip()
        )
    track_position = prepared_tracks[file_counter].position
    multiple_discs = re.search('-', track_position)
    return track_title, track_artist, track_position, multiple_discs


def rename_files(opts, audio_file, file_counter, fetched_release_info,
                 multiple_discs, track_artist, track_position, track_title,
                 file_extension):
    # ==========================================================================
    if opts.debug:
        print(">>> DEBUG Track {} artist: {}".format(
            (file_counter + 1), fetched_release_info["artist"]))
        print(">>> DEBUG Track {} multiple: {}".format(
            (file_counter + 1), multiple_discs))
    # ==========================================================================
    os.rename(os.path.join(opts.folder, audio_file),
        os.path.join(
            opts.folder,
            "{}-{}{:02}-{}.{}".format(
                strip_accents(
                    track_artist.replace("?", "_").replace("/", "_") \
                    .replace(":", "")
                ),
                track_position.split('-')[0] if multiple_discs else "",
                int(track_position.split('-')[1]) if multiple_discs \
                    else (file_counter + 1),
                strip_accents(
                    track_title.replace("?", "_").replace("/", "_") \
                    .replace(":", "")
                ),
                file_extension
            ).replace(" ", "_") if not fetched_release_info["artist"] \
                == "Various" else "{}{:02}-{}-{}.{}".format(
                    track_position.split('-')[0] if multiple_discs \
                        else "",
                    int(
                        re.sub(r'[a-zA-Z]', '', track_position.split('-')[1])
                    ) if multiple_discs else (file_counter + 1),
                    strip_accents(
                        track_artist.replace("?", "_").replace("/", "_") \
                        .replace(":", "")
                    ),
                    strip_accents(
                        track_title.replace("?", "_").replace("/", "_") \
                        .replace(":", "")
                    ),
                    file_extension
            ).replace(" ", "_")
        )
    )


def main():
    op = OptionParser(usage=__doc__)
    op.add_option('--folder')
    op.add_option('--debug')
    op.add_option('--catno')
    op.add_option('--id')
    opts, args = op.parse_args()
    tracklist = []
    bitrates = []
    file_counter = 0
    total_duration = 0
    image_counter = 0
    fetched_release_info = {}
    folder_name_pattern = {}

    release_info = re.split('[^a-zA-Z\d\s:\!\.\']', opts.folder)
    release_info = filter(None, release_info)
    artist = next(release_info).strip()
    album = next(release_info).strip().title()
    folder_files = os.listdir(opts.folder)
    files_count, sample_file = filter_files(folder_files)
    print("audio files found:      ", files_count)
    # ==========================================================================
    if opts.debug:
        print(">>> DEBUG parsed artist:", artist)
        print(">>> DEBUG parsed album:", album)
        print(">>> DEBUG folder files:", folder_files)
        print(">>> DEBUG sample file:", sample_file)
    # ==========================================================================
    results = d.search(opts.catno, type='release') if opts.catno else d.search(
        album, artist=artist, type='release')
    print("release versions found: ", results.count)

    for i in range(results.count):
        prepared_tracks = [
            track for track in results[i].tracklist if track.position \
            and not re.search('[b-zB-Z]', track.position)
        ]
        if len(prepared_tracks) == files_count:
            picked_id = pick_release_format_id(results[i])
            first_track = strip_accents(
                prepared_tracks[0].title).lower().replace("/", " ")
            try:
                titles_match = any(map(
                    lambda v: v in first_track.split(), sample_file.split()))
            except AttributeError:
                titles_match = None
                pass
            # ==================================================================
            if opts.debug:
                print("\n>>> DEBUG resulted title:", results[i].title)
                print(">>> DEBUG resulted catalogue:", results[i].data["catno"])
                print(">>> DEBUG format name:", results[i].formats[0].get("name"))
                print(">>> DEBUG format details:",
                      results[i].formats[0].get("descriptions"))
                print(">>> DEBUG picked release ID:", picked_id)
                print(">>> DEBUG first track:", first_track)
                print(">>> DEBUG first track split:", first_track.split())
                print(">>> DEBUG sample track split:", sample_file.split())
                print(">>> DEBUG titles match:", titles_match)
                for j in first_track.split():
                    if j in sample_file.split():
                        print(j)
                print(">>> DEBUG re.search:",
                      re.search(first_track, sample_file, re.IGNORECASE))
            # ==================================================================
            if titles_match:
                fetched_release_info["index"] = i
                fetched_release_info["id"] = picked_id \
                    if results[i].id == picked_id else None
                fetched_release_info["artist"] = results[i].artists[0].name
                fetched_release_info["tracklist"] = [
                    track.title for track in prepared_tracks]
                fetched_release_info["year"] = results[i].year
                if opts.debug:
                    print(">>> DEBUG release ID:", fetched_release_info["id"])
                if fetched_release_info["artist"] == 'Various':
                    fetched_release_info["artists"] = [
                        re.sub(r"\(\d+\)", '', track.artists[0].name).strip() \
                            for track in results[i].tracklist if track.position
                    ]
                    if opts.debug:
                        print(">>> DEBUG artists:",
                              fetched_release_info["artists"])
                if fetched_release_info["id"]:
                    break

    if opts.id:
        fetched_release_info["id"] = opts.id
    if "id" in fetched_release_info.keys():
        release = d.release(fetched_release_info["id"])
    else:
        sys.exit("\n*** No such release found, please visit discogs.com to "
            "verify *** ")
    if opts.id:
        prepared_tracks = [
            track for track in release.tracklist if track.position]
        fetched_release_info["artist"] = release.artists[0].name
        fetched_release_info["tracklist"] = [
                    track.title for track in prepared_tracks]
        fetched_release_info["year"] = release.year
    # ==========================================================================
    if opts.debug:
        print(">>> DEBUG release:             ", release)
        print(">>> DEBUG release id:             ", fetched_release_info["id"])
        print(">>> DEBUG fetched format:         ",
              release.formats[0].get("descriptions"))
    # ==========================================================================

    # Process images
    for image in release.images:
        image_counter += 1
        f = open(os.path.join(opts.folder, '{}-{:02}.jpg'.format(
            fetched_release_info["id"], image_counter)),'wb')
        f.write(requests.get(image["resource_url"]).content)
        f.close()
    main_image = os.path.join(opts.folder,
        '{}-01.jpg'.format(fetched_release_info["id"]))
    main_image_size = Image.open(main_image).size if os.path.exists(
        main_image) else (0, 0)
    folder_image = os.path.join(opts.folder, 'folder.jpg')
    folder_image_size = Image.open(folder_image).size if os.path.exists(
        folder_image) else (0, 0)
    cover_image = os.path.join(opts.folder, 'cover.jpg')
    cover_image_size = Image.open(cover_image).size if os.path.exists(
        cover_image) else (0, 0)
    image_sizes = {
        "main": main_image_size[0],
        "folder": folder_image_size[0],
        "cover": cover_image_size[0]
    }
    chosen_image = None
    for k, v in image_sizes.items():
        if v in range(450, 650):
            if k == "main":
                chosen_image = main_image
            elif k == "folder":
                chosen_image = folder_image
            elif k == "cover":
                chosen_image = cover_image
    if chosen_image:
        # ======================================================================
        if opts.debug:
            print(">>> DEBUG chosen image:           ", chosen_image)
            print(">>> DEBUG chosen image size:      ",
                  Image.open(chosen_image).size)
        # ======================================================================
        try:
            shutil.copyfile(
                os.path.join(chosen_image),
                os.path.join(folder_image))
        except shutil.SameFileError:
            pass
    else:
        try:
            shutil.copyfile(
                os.path.join(opts.folder,
                             '{}-01.jpg'.format(fetched_release_info["id"])),
                os.path.join(folder_image))
        except shutil.SameFileError:
            pass
    print("fetched artist:         ", fetched_release_info["artist"])
    print("fetched tracklist:      ", fetched_release_info["tracklist"])
    print("fetched year:           ", fetched_release_info["year"])
    release_date = release.data["released"].replace("-", ".")
    catalogue_number = release.data["labels"][0]["catno"].replace("/", "_")
    if catalogue_number == "none":
        catalogue_number = ""
    print("catalogue code:         ", catalogue_number)

    # Process audio files
    for audio_file in folder_files:
        is_writeable = os.access(os.path.join(opts.folder, audio_file), os.W_OK)
        # ======================================================================
        if opts.debug:
            print(">>> ACCESS:", is_writeable)
        # ======================================================================
        if not is_writeable:
            os.chmod(os.path.join(opts.folder, audio_file), stat.S_IWRITE)
        file_extension = os.path.splitext(audio_file)[-1].lower()[1:]

        if file_extension == "mp3":
            track_title, track_artist, track_position, multiple_discs = prepare_tags(
                prepared_tracks, file_counter, fetched_release_info)
            # ==================================================================
            if opts.debug:
                print(">>> DEBUG tag track:", track_title)
                print(">>> DEBUG tag artist:", track_artist)
                print(">>> DEBUG track position:", track_position)
            # ==================================================================
            audio = ID3(os.path.join(opts.folder, audio_file))
            audio.add(
                TIT2(encoding=3, text=track_title)
            )
            audio.add(
                TPE1(encoding=3, text=track_artist)
            )
            audio.add(
                TALB(encoding=3, text=release.title.strip())
            )
            audio.add(
                TYER(encoding=3, text=str(fetched_release_info["year"]))
            )

            # Get bitrate information
            audio_for_info = MP3(os.path.join(opts.folder, audio_file))
            fetched_release_info["bitrate_mode"] = str(
                audio_for_info.info.bitrate_mode)
            # ==================================================================
            if opts.debug:
                print(
                    ">>> DEBUG bitrate mode:",
                    fetched_release_info["bitrate_mode"]
                )
            # ==================================================================
            bitrates.append(audio_for_info.info.bitrate)
            total_duration += audio_for_info.info.length

            # Embed the artwork
            albumart = os.path.join(opts.folder, 'folder.jpg')
            if albumart:
                image = Picture()
                mime = 'image/png' if albumart.endswith('png') else 'image/jpeg'
                with open(albumart, 'rb') as f:
                    image.data = f.read()
                audio.add(APIC(encoding=3, mime=mime, type=3, desc=u'front cover',
                    data=image.data))
            audio.save()
            rename_files(
                opts, audio_file, file_counter, fetched_release_info,
                multiple_discs, track_artist, track_position, track_title,
                file_extension
            )
            file_counter += 1
        elif file_extension == "flac":
            track_title, track_artist, track_position, multiple_discs = prepare_tags(
                prepared_tracks, file_counter, fetched_release_info)
            # ==================================================================
            if opts.debug:
                print(">>> DEBUG tag track:", track_title)
                print(">>> DEBUG tag artist:", track_artist)
                print(">>> DEBUG track position:", track_position)
            # ==================================================================
            audio = FLAC(os.path.join(opts.folder, audio_file))
            audio["title"] = track_title
            audio["artist"] = track_artist
            audio["album"] = release.title.strip()

            # Get bitrate information
            file_bitrate = (
                audio.info.bits_per_sample * audio.info.total_samples) \
                / audio.info.length
            bitrates.append(file_bitrate)
            fetched_release_info["bitrate_mode"] = "BitrateMode.VBR"
            total_duration += audio.info.length
            # ==================================================================
            if opts.debug:
                print(">>> DEBUG embedded pictures:", audio.pictures)
            # ==================================================================
            if not audio.pictures:
                albumart = os.path.join(opts.folder, 'folder.jpg')
                # ==============================================================
                if opts.debug:
                    print(">>> DEBUG album art:", albumart)
                # ==============================================================
                if albumart:
                    image = Picture()
                    with open(albumart, 'rb') as f:
                        image.data = f.read()
                    image.mime = 'image/jpeg'
                    image.type = PictureType.COVER_FRONT
                    image.width = 500
                    image.height = 500
                    audio.add_picture(image)
            audio.save()
            # ==================================================================
            if opts.debug:
                print(">>> DEBUG embedded pictures after save:", audio.pictures)
            # ==================================================================
            rename_files(
                opts, audio_file, file_counter, fetched_release_info,
                multiple_discs, track_artist, track_position, track_title,
                file_extension
            )
            file_counter += 1
        elif file_extension == "m4a":
            track_title, track_artist, track_position, multiple_discs = prepare_tags(
                prepared_tracks, file_counter, fetched_release_info)
            # ==================================================================
            if opts.debug:
                print(">>> DEBUG tag track:", track_title)
                print(">>> DEBUG tag artist:", track_artist)
                print(">>> DEBUG track position:", track_position)
            # ==================================================================
            audio = MP4(os.path.join(opts.folder, audio_file))
            audio.tags['\xa9nam'] = [track_title]
            audio.tags['\xa9ART'] = [track_artist]
            audio.tags['aART']    = [track_artist]
            audio.tags['\xa9alb'] = [release.title.strip()]
            audio.tags.update()
            audio.save()
            bitrates.append(audio.info.bitrate)
            fetched_release_info["bitrate_mode"] = "BitrateMode.CBR"
            total_duration += audio.info.length
            rename_files(
                opts, audio_file, file_counter, fetched_release_info,
                multiple_discs, track_artist, track_position, track_title,
                file_extension
            )
            file_counter += 1

    print("tracks processed:       ", file_counter)
    average_bitrate = int(sum(bitrates) / len(bitrates))
    print("average bitrate (bps):  ", average_bitrate)
    
    if fetched_release_info["bitrate_mode"] == "BitrateMode.CBR":
        if average_bitrate in range(319700, 320200):
            folder_name_pattern["media"] = "320"
        elif average_bitrate in range(256000, 256200):
            folder_name_pattern["media"] = "256"
        elif average_bitrate in range(224000, 224200):
            folder_name_pattern["media"] = "224"
        elif average_bitrate in range(192000, 192200):
            folder_name_pattern["media"] = "192"
        elif average_bitrate in range(128000, 128200):
            folder_name_pattern["media"] = "128"
    elif fetched_release_info["bitrate_mode"] == "BitrateMode.VBR":
        if average_bitrate in range(700000, 1200000):
            folder_name_pattern["media"] = "FLAC"    
        else:
            folder_name_pattern["media"] = "VBR"
    elif fetched_release_info["bitrate_mode"] == "BitrateMode.ABR":
        folder_name_pattern["media"] = "ABR"
    elif fetched_release_info["bitrate_mode"] == "BitrateMode.UNKNOWN":
        folder_name_pattern["media"] = "VBR"

    # Collect release options
    folder_name_pattern["type"] = ""
    digital_audio_formats = ["FLAC", "MP3", "WAV", "AIFF", "AAC"]
    physical_media_formats = ["CD", "CDr", "LP"]

    for media_format in release.formats:
        digital_audio_format_present = []

        if media_format["qty"] > "1":
            if media_format["name"] in physical_media_formats:
                folder_name_pattern["type"] += "{}{}, ".format(
                    media_format["qty"], media_format["name"])
            if media_format["name"] == "Vinyl" and "LP" in \
                media_format["descriptions"]:
                folder_name_pattern["type"] += "{}LP, ".format(
                    media_format["qty"])
                media_format["descriptions"].remove("LP")

        if "Album" in media_format["descriptions"]:
            media_format_descriptions = media_format["descriptions"].remove(
                "Album")

        media_format_descriptions = media_format["descriptions"]

        if media_format_descriptions:
            digital_audio_format_present = [x for x in digital_audio_formats \
                if x in media_format_descriptions]
        
        cleansed_descriptions = media_format_descriptions.remove(
            digital_audio_format_present[0]) if digital_audio_format_present \
                else media_format_descriptions
        media_format_name = media_format["name"] if media_format["name"] not in \
            physical_media_formats else ""
        
        if media_format_name:
            folder_name_pattern["type"] += "{}, ".format(media_format_name)
        if cleansed_descriptions:
            folder_name_pattern["type"] += ", ".join(cleansed_descriptions)
            folder_name_pattern["type"] += ", "

    if fnmatch.filter(os.listdir(opts.folder), '*.nfo'):
        folder_name_pattern["type"] += "scene, "
    # ==========================================================================
    if opts.debug:
        print(folder_name_pattern)
    # ==========================================================================

    # Apply the new folder name pattern
    release_title_raw = string.capwords(release.title.strip())
    release_title = release_title_raw.replace("?", "_").replace(":", " -").\
        replace("/", "-")
    type_descriptions = (str(folder_name_pattern["type"])
        .lower().replace("\"", "''").replace("2lp", "2LP")
        .replace("2cd", "2CD") if "type" in folder_name_pattern.keys() else "")
    type_descriptions = re.sub('ep(?!\w+)', 'EP', type_descriptions)
    new_folder_name = "{0} {1} [{2}{3}] @{4}".format(
        release_date,
        strip_accents(release_title),
        type_descriptions if catalogue_number else type_descriptions.strip(', '),
        str(catalogue_number).upper(),
        folder_name_pattern["media"]
    )
    os.rename(opts.folder, new_folder_name)

    # Print release details
    print("processed release title: ", new_folder_name)
    for track in prepared_tracks:
        print(track.position, ' ', track.title, ' ', track.duration)
    print("============ total duration (min):   ", "{:d}:{:d}".format(
          trunc(total_duration / 60.0), trunc(total_duration % 60.0)))
    print("============ folder size (Mb):       ", "{:.2f}".format(
        float(get_folder_size(new_folder_name)) / 1000000.0))


if __name__ == '__main__':
    main()
