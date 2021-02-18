#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import sys
import stat
import shutil
import string
import fnmatch
import logging
import requests
import discogs_client

from optparse import OptionParser
from mutagen.flac import FLAC, Picture
from mutagen.wave import WAVE
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TYER, TRCK
from mutagen.id3 import APIC, PictureType
from PIL import Image

import settings
from utils import *

d = discogs_client.Client('Cat-Tool/0.1', user_token=settings.DISCOGS_USER_TOKEN)
logger = logging.getLogger('renamer')

digital_audio_formats = ['FLAC', 'MP3', 'WAV', 'AIFF', 'AAC', 'ALAC', 'ogg']
physical_media_formats = ['CD', 'CDr', 'LP']
descriptions_to_drop = ['Album', '33 ⅓ RPM', '45 RPM', 'Stereo']
descriptions_for_tags = ["compilation", "single", "maxi-single", "EP", "vinyl",
                         "7''", "12''", "2CD", "3CD", "4CD", "2LP", "3LP", "4LP"]


def prepare_tags(prepared_tracks, file_counter, fetched_release_info):
    # Uppercase the first letter and leave the case of all subsequent letters
    track_title_raw = re.sub('([a-zA-Z])',
        lambda x: x.groups()[0].upper(),
        prepared_tracks[file_counter].title.strip(), 1
    )
    track_title = track_title_raw.replace("(", "[").replace(")", "]") \
        .replace("Remix", "remix").replace("Rmx", "remix") \
        .replace("RMX", "remix").replace("Mix", "mix").replace("Edit", "edit") \
        .replace("Version", "version").replace("Cover", "cover") \
        .replace("Extended", "extended").replace("Single", "single") \
        .replace("Live", "live").replace("Acoustic", "acoustic") \
        .replace("Radio", "radio").replace("Club", "club") \
        .replace("Original", "original").replace("\"", "''")
    track_artist_raw = prepared_tracks[file_counter].artists[0].name.strip() \
        if prepared_tracks[file_counter].artists \
        else fetched_release_info["artist"]
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


def sanitize_descriptions(media_format):
    media_format_descriptions = media_format.get("descriptions")

    if media_format_descriptions:
        to_drop = [
            i for i in descriptions_to_drop \
                if i in media_format_descriptions
        ]
        if to_drop:
            media_format_descriptions = list(filter(
                lambda v: v not in to_drop, media_format_descriptions))
        digital_format_to_drop = [
            x for x in digital_audio_formats \
                if x in media_format_descriptions
        ]
        if digital_format_to_drop:
            media_format_descriptions = list(filter(
                lambda v: v not in digital_format_to_drop,
                media_format_descriptions))

    return media_format_descriptions


def rename_files(opts, audio_file, file_counter, fetched_release_info,
                 multiple_discs, track_artist, track_position, track_title,
                 file_extension):
    # ==========================================================================
    logger.debug("\n    >>> track {} artist: {}".format(
        (file_counter+1), fetched_release_info["artist"]))
    logger.debug("\n    >>> track {} multiple: {}".format(
        (file_counter+1), multiple_discs))
    # ==========================================================================
    if fetched_release_info["artist"] == "Various" \
            or fetched_release_info.get("various"):
        os.rename(
            os.path.join(opts.folder, audio_file),
            os.path.join(
                opts.folder,
                "{disc}{position:02}-{artist}-{title}.{extension}".format(
                    disc=track_position.split('-')[0] if multiple_discs \
                        else "",
                    position=int(
                        re.sub(r'[a-zA-Z]', '', track_position.split('-')[1])
                    ) if multiple_discs else (file_counter+1),
                    artist=strip_accents(
                        track_artist.replace("?", "_").replace("/", "_") \
                            .replace(":", "")
                    ),
                    title=strip_accents(
                        track_title.replace("?", "_").replace("/", "_") \
                            .replace(":", "")
                    ),
                    extension=file_extension
                ).replace(" ", "_")
            )
        )
    else:
        os.rename(
            os.path.join(opts.folder, audio_file),
            os.path.join(
                opts.folder,
                "{artist}-{disc}{position:02}-{title}.{extension}".format(
                    artist=strip_accents(
                        track_artist.replace("?", "_").replace("/", "_") \
                            .replace(":", "")
                    ),
                    disc=track_position.split('-')[0] if multiple_discs else "",
                    position=int(track_position.split('-')[1]) if multiple_discs \
                        else (file_counter+1),
                    title=strip_accents(
                        track_title.replace("?", "_").replace("/", "_") \
                            .replace(":", "")
                    ),
                    extension=file_extension
                ).replace(" ", "_")
            )
        )


def main():
    op = OptionParser(usage=__doc__)
    op.add_option("--folder", help="name of the folder to process")
    op.add_option("--catno", help="release catalogue number to search by")
    op.add_option("--id", help="Discogs release code to search by")
    op.add_option("--list", help="list versions of the release and exit")
    op.add_option("--debug", help="print out the details for debugging")
    opts, args = op.parse_args()

    if opts.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    tracklist = []
    bitrates = []
    file_counter = 0
    total_duration = 0
    image_counter = 0
    fetched_release_info = {}
    folder_name_pattern = {}
    results = None
    calculated_duration = (0, 0, 0)
    calculated_duration_from_audio = (0, 0, 0)

    release_info = re.split(r'[^a-zA-Z\d\s:\!\.\']', opts.folder)
    release_info = filter(None, release_info)
    artist = next(release_info).strip()
    album = next(release_info).strip().title()

    if opts.list:
        list_results = d.search(album, artist=artist, type='release')
        for i in range(list_results.count):
            print_release_version(list_results[i])
        sys.exit()

    folder_files = sorted(os.listdir(opts.folder))
    audio_files, files_count, sample_file_1, sample_file_2 = filter_files(
        folder_files)
    print(f"audio files found:      {files_count}")
    # ==========================================================================
    logger.debug(f"\n    >>> parsed artist: {artist}")
    logger.debug(f"\n    >>> parsed album: {album}")
    logger.debug(f"\n    >>> folder files: {folder_files}")
    logger.debug(f"\n    >>> audio files: {audio_files}")
    logger.debug(f"\n    >>> sample file 1: {sample_file_1}")
    logger.debug(f"\n    >>> sample file 2: {sample_file_2}")
    # ==========================================================================
    
    if opts.id:
        fetched_release_info["id"] = opts.id
        release = d.release(opts.id)
        prepared_tracks = [
            track for track in release.tracklist if track.position \
                or len(track.data.get('sub_tracks', [])) > 0
        ]

        # Handle a rare case of mash-up tracks on mixed compilations
        # listed without durations
        any_duration_absent = any(
            len(track.duration) < 1 for track in prepared_tracks)
        if any_duration_absent and files_count != len(prepared_tracks):
            prepared_tracks = [
                track for track in prepared_tracks if track.duration]

        fetched_release_info["artist"] = release.artists[0].name
        fetched_release_info["tracklist"] = [
            track.title for track in prepared_tracks]
        fetched_release_info["year"] = release.year
        total_artists = len(
            set(track.artists[0].name for track in prepared_tracks))
        multiple_track_artists = any(
            len(track.artists) > 1 for track in prepared_tracks)
        if multiple_track_artists or total_artists > 1:
            fetched_release_info["various"] = True

    if opts.catno:
        results = d.search(opts.catno, type='release')

    if not opts.catno and not opts.id:
        results = d.search(album, artist=artist, type='release')

    if results:
        print(f"release versions found: {results.count}")
        for i in range(results.count):
            prepared_tracks = [
                track for track in results[i].tracklist if track.position \
                    or len(track.data.get('sub_tracks', [])) > 0 \
                    and not re.search('[b-zB-Z]', track.position)
            ]
            if len(prepared_tracks) == files_count:
                picked_id = pick_release_format_id(results[i])
                first_track = prepare_track_title(prepared_tracks[0].title)
                last_track = prepare_track_title(prepared_tracks[-1].title)
                first_titles = list(
                    set(first_track.split()) & set(sample_file_1.split()))
                last_titles = list(
                    set(last_track.split()) & set(sample_file_2.split()))
                # ==============================================================
                logger.debug(f"\n    >>>>>> resulted title: {results[i].title}")
                logger.debug("\n    >>>>>> resulted catalogue number: "
                    f"{results[i].data['catno']}")
                logger.debug("\n    >>>>>> format name: "
                    f"{results[i].formats[0].get('name')}")
                logger.debug("\n    >>>>>> format descriptions: "
                    f"{results[i].formats[0].get('descriptions')}")
                logger.debug(f"\n    >>>>>> picked release ID: {picked_id}")
                logger.debug(f"\n    >>>>>> first track: {first_track}")
                logger.debug("\n    >>>>>> first track split: "
                    f"{first_track.split()}")
                logger.debug(f"\n    >>>>>> last track: {last_track}")
                logger.debug("\n    >>>>>> last track split: "
                    f"{last_track.split()}")
                logger.debug(f"\n    >>>>>> sample file 1: {sample_file_1}")
                logger.debug("\n    >>>>>> sample file 1 split: "
                    f"{sample_file_1.split()}")
                logger.debug(f"\n    >>>>>> sample file 2: {sample_file_2}")
                logger.debug("\n    >>>>>> sample file 2 split: "
                    f"{sample_file_2.split()}")
                logger.debug(f"\n    >>>>>> first titles: {first_titles}")
                logger.debug(f"\n    >>>>>> last titles: {last_titles}")
                # ==============================================================
                if len(first_titles) > 1 and len(last_titles) > 1:
                    fetched_release_info["id"] = picked_id \
                        if results[i].id == picked_id else None
                    fetched_release_info["artist"] = results[i].artists[0].name
                    fetched_release_info["tracklist"] = [
                        track.title for track in prepared_tracks]
                    fetched_release_info["year"] = results[i].year
                    fetched_release_info["various"] = False
                    release = d.release(fetched_release_info["id"])
                    # ==========================================================
                    logger.debug("\n    >>>>>>>>> release ID: "
                        f"{fetched_release_info['id']}")
                    # ==========================================================
                    if fetched_release_info["artist"] == 'Various':
                        fetched_release_info["artists"] = [
                            re.sub(r"\(\d+\)", '',
                            track.artists[0].name).strip() \
                                for track in results[i].tracklist \
                                if track.position
                        ]
                        # ======================================================
                        logger.debug("\n    >>>>>>>>> artists: "
                            f"{fetched_release_info['artists']}")
                        # ======================================================
                        fetched_release_info["various"] = True
                    if fetched_release_info["id"]:
                        break

    # ==========================================================================
    logger.debug(f"\n    >>> release: {release}")
    logger.debug(f"\n    >>> fetched release ID: {fetched_release_info['id']}")
    logger.debug(f"\n    >>> fetched format: "
        f"{release.formats[0].get('descriptions')}")
    # ==========================================================================
    
    # Process images
    if release.images:
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
            # ==================================================================
            logger.debug(f"\n    >>>>>> chosen image: {chosen_image}")
            logger.debug("\n    >>>>>> chosen image size: "
                f"{Image.open(chosen_image).size}")
            # ==================================================================
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
    print(f"fetched artist:         {fetched_release_info['artist']}")
    print(f"fetched tracklist:      {fetched_release_info['tracklist']}")
    print(f"fetched year:           {fetched_release_info['year']}")
    release_date = release.data["released"].replace("-", ".")
    catalogue_number = release.data["labels"][0]["catno"].replace("/", "_")
    if catalogue_number == "none":
        catalogue_number = ""
    print(f"catalogue number:         {catalogue_number}")

    # Collect release options
    folder_name_pattern["type"] = ""

    for media_format in release.formats:
        if media_format["qty"] > "1":
            if media_format["name"] in physical_media_formats:
                folder_name_pattern["type"] += "{}{}, ".format(
                    media_format["qty"], media_format["name"])
            if media_format["name"] == "Vinyl" and "LP" in \
                media_format["descriptions"]:
                    folder_name_pattern["type"] += f"{media_format['qty']}LP, "
                    media_format["descriptions"].remove("LP")

        cleansed_descriptions = sanitize_descriptions(media_format)
        media_format_name = media_format["name"] if media_format["name"] not in \
            physical_media_formats else ""
        
        if media_format_name:
            folder_name_pattern["type"] += f"{media_format_name}, "
        if cleansed_descriptions:
            folder_name_pattern["type"] += ", ".join(cleansed_descriptions)
            folder_name_pattern["type"] += ", "
            
    if fnmatch.filter(os.listdir(opts.folder), '*.nfo'):
        folder_name_pattern["type"] += "scene, "
    # ==========================================================================
    logger.debug(f"\n    >>> folder name pattern: {folder_name_pattern}")
    # ==========================================================================
    release_title_raw = string.capwords(release.title.strip()).title()
    release_title = release_title_raw.replace("?", "_").replace(":", " -") \
        .replace("/", "-")
    type_descriptions = (str(folder_name_pattern["type"]).lower() \
        .replace("\"", "''") if "type" in folder_name_pattern.keys() else "")
    type_descriptions = re.sub(r'ep(?!\w+)', 'EP', type_descriptions)
    type_descriptions = re.sub(r'lp(?!\w+)', 'LP', type_descriptions)
    type_descriptions = re.sub(r'cd(?!\w+)', 'CD', type_descriptions)

    type_descriptions_for_tags = [i.strip() \
        for i in type_descriptions.split(',') if i]
    descriptions_for_tags_found = [i for i in descriptions_for_tags \
        if i in type_descriptions_for_tags]
    if fetched_release_info["artist"] == 'Various':
        type_descriptions = re.sub('compilation', '', type_descriptions)
        # If there's a stray comma in the descriptions, remove it
        type_descriptions = re.sub(r'\s,', '', type_descriptions)
        album_title_for_tags = "V/A: {title} [{type}]".format(
            title=release.title.strip(), type=type_descriptions.strip(', ')) \
            if descriptions_for_tags_found else f"V/A: {release.title.strip()}"
    else:
        album_title_for_tags = "{title} [{type}]".format(
                title=release.title.strip(),
                type=", ".join(descriptions_for_tags_found)
            ) if descriptions_for_tags_found else release.title.strip()
    # ==========================================================================
    logger.debug(f"\n    >>> release title: {release_title}")
    logger.debug(f"\n    >>> album title for tags: {album_title_for_tags}")
    logger.debug(f"\n    >>> type descriptions: {type_descriptions}")
    # ==========================================================================

    # Process audio files
    for audio_file in audio_files:
        is_writeable = os.access(os.path.join(opts.folder, audio_file), os.W_OK)
        if not is_writeable:
            os.chmod(os.path.join(opts.folder, audio_file), stat.S_IWRITE)
        file_extension = os.path.splitext(audio_file)[-1].lower()[1:]
        track_title, track_artist, track_position, multiple_discs = prepare_tags(
            prepared_tracks, file_counter, fetched_release_info)
        track_position_for_tags = track_position.split('-')[1] \
            if multiple_discs else track_position
        if not track_position_for_tags.isdigit():
            track_position_for_tags = str(file_counter+1)
        disc_number = track_position.split('-')[0] if multiple_discs else ""
        if disc_number:
            album_title_for_tags = re.sub(
                r'\d?CD\d?', f'CD{disc_number}', album_title_for_tags)
        albumart = os.path.join(opts.folder, 'folder.jpg')
        # ==================================================================
        logger.debug(f"\n    >>>>>> audio file: {audio_file}")
        logger.debug(f"\n    >>>>>> file extension: {file_extension}")
        logger.debug(f"\n    >>>>>> tag track: {track_title}")
        logger.debug(f"\n    >>>>>> tag artist: {track_artist}")
        logger.debug(f"\n    >>>>>> track position: {track_position}")
        logger.debug(f"\n    >>>>>> disc number: {disc_number}")
        logger.debug(f"\n    >>>>>> is writeable: {is_writeable}")
        logger.debug(f"\n    >>>>>> album art: {albumart}")
        # ==================================================================

        if file_extension == "mp3":            
            audio = MP3(os.path.join(opts.folder, audio_file))
            audio.tags['TIT2'] = TIT2(encoding=3, text=track_title)
            audio.tags['TPE1'] = TPE1(encoding=3, text=track_artist)
            audio.tags['TALB'] = TALB(encoding=3, text=album_title_for_tags)
            audio.tags['TDRC'] = TDRC(encoding=3,
                text=str(fetched_release_info["year"]))
            audio.tags['TRCK'] = TRCK(encoding=3, text=track_position_for_tags)
            audio.tags.update()

            # Get bitrate information
            fetched_release_info["bitrate_mode"] = str(audio.info.bitrate_mode)
            bitrates.append(audio.info.bitrate)
            total_duration += audio.info.length
            # ==================================================================
            logger.debug("\n    >>>>>>>>> bitrate mode: "
                f"{fetched_release_info['bitrate_mode']}")
            logger.debug(f"\n    >>>>>>>>> bitrates: {bitrates}")
            # ==================================================================

            # Embed the artwork
            if os.path.isfile(albumart):
                # ==============================================================
                logger.debug(f"\n    >>>>>>>>>>>> album art in mp3: {albumart}")
                # ==============================================================
                image = Picture()
                mime = 'image/jpeg'
                with open(albumart, 'rb') as f:
                    image.data = f.read()
                audio.tags['APIC:'] = APIC(encoding=3, mime=mime, type=3,
                    desc=u'front cover', data=image.data)
            audio.save()
        elif file_extension == "flac":
            audio = FLAC(os.path.join(opts.folder, audio_file))
            audio["title"] = track_title
            audio["artist"] = track_artist
            audio["album"] = album_title_for_tags

            # Get bitrate information
            file_bitrate = (audio.info.bits_per_sample \
                * audio.info.total_samples) / audio.info.length
            bitrates.append(file_bitrate)
            fetched_release_info["bitrate_mode"] = "BitrateMode.VBR"
            total_duration += audio.info.length
            # ==================================================================
            logger.debug(f"\n    >>>>>>>>> bitrates: {bitrates}")
            logger.debug(f"\n    >>>>>>>>> embedded pictures: {audio.pictures}")
            # ==================================================================
            if not audio.pictures:
                # ==============================================================
                logger.debug(f"\n    >>>>>>>>>>>> album art in flac: {albumart}")
                # ==============================================================
                if os.path.isfile(albumart):
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
            logger.debug(
                f"\n    >>>>>>>>> embedded pictures after save: {audio.pictures}")
            # ==================================================================
        elif file_extension == "m4a":
            audio = MP4(os.path.join(opts.folder, audio_file))
            audio.tags['\xa9nam'] = [track_title]
            audio.tags['\xa9ART'] = [track_artist]
            audio.tags['aART']    = [track_artist]
            audio.tags['\xa9alb'] = [album_title_for_tags]
            audio.tags.update()
            audio.save()
            bitrates.append(audio.info.bitrate)
            # ==================================================================
            logger.debug(f"\n    >>>>>>>>> bitrates: {bitrates}")
            # ==================================================================
            fetched_release_info["bitrate_mode"] = "BitrateMode.CBR"
            total_duration += audio.info.length
        elif file_extension == "wav":
            audio = WAVE(os.path.join(opts.folder, audio_file))
            # Create ID3 tag if not present
            if not audio.tags:
                audio.add_tags()
            audio.tags['TIT2'] = TIT2(encoding=3, text=track_title)
            audio.tags['TPE1'] = TPE1(encoding=3, text=track_artist)
            audio.tags['TALB'] = TALB(encoding=3, text=album_title_for_tags)
            audio.tags['TDRC'] = TDRC(encoding=3,
                text=str(fetched_release_info["year"]))
            audio.tags['TRCK'] = TRCK(encoding=3, text=track_position_for_tags)
            if 'APIC:' not in audio.tags.keys():
                # ==============================================================
                logger.debug(f"\n    >>>>>>>>> album art in wav: {albumart}")
                # ==============================================================
                if os.path.isfile(albumart):
                    image = Picture()
                    with open(albumart, 'rb') as f:
                        image.data = f.read()
                    # ==========================================================
                    logger.debug(
                        f"\n    >>>>>>>>>>>> image mime in wav: {image.mime}")
                    # ==========================================================
                    mime = 'image/jpeg'
                    audio.tags['APIC:'] = APIC(encoding=3, mime=mime, type=3,
                        desc=u'front cover', data=image.data)
            audio.tags.update()
            audio.save()
            bitrates.append(1411200)
            # ==================================================================
            logger.debug(f"\n    >>>>>>>>> bitrates: {bitrates}")
            # ==================================================================
            fetched_release_info["bitrate_mode"] = "BitrateMode.CBR"
            total_duration += audio.info.length
        fetched_release_info["bitrate_kbps"] = int(audio.info.bitrate / 1000)
        fetched_release_info["sample_rate"] = audio.info.sample_rate
        fetched_release_info["bits_per_sample"] = audio.info.bits_per_sample \
            if hasattr(audio.info, 'bits_per_sample') else "no data"
        fetched_release_info["channels"] = audio.info.channels
        rename_files(
            opts, audio_file, file_counter, fetched_release_info,
            multiple_discs, track_artist, track_position, track_title,
            file_extension
        )
        file_counter += 1
        # ==================================================================
        logger.debug(f"\n    >>>>>> total duration: {total_duration}")
        # ==================================================================
    print(f"tracks processed:       {file_counter}")
    average_bitrate = int(sum(bitrates) / len(bitrates))
    print(f"average bitrate (bps):  {average_bitrate}")
    calculated_duration_from_audio = calculate_durations(total_duration)
    
    # Choose a bitrate mode descriptor
    if fetched_release_info["bitrate_mode"] in [
            "BitrateMode.CBR", "BitrateMode.UNKNOWN"]:
        if average_bitrate in range(319700, 320200):
            folder_name_pattern["media"] = "320"
        elif average_bitrate in range(256000, 256200):
            folder_name_pattern["media"] = "256"
        elif average_bitrate in range(224000, 224200):
            folder_name_pattern["media"] = "224"
        elif average_bitrate in range(192000, 192200):
            folder_name_pattern["media"] = "192"
        elif average_bitrate in range(160000, 160200):
            folder_name_pattern["media"] = "160"
        elif average_bitrate in range(128000, 128200):
            folder_name_pattern["media"] = "128"
        elif average_bitrate in range(1300000, 1500000):
            folder_name_pattern["media"] = "WAV"
        else:
            folder_name_pattern["media"] = "_".join(
                str(i)[:3] for i in set(bitrates))
    elif fetched_release_info["bitrate_mode"] == "BitrateMode.VBR":
        if average_bitrate in range(700000, 1200000):
            folder_name_pattern["media"] = "FLAC"    
        else:
            folder_name_pattern["media"] = "VBR"
    elif fetched_release_info["bitrate_mode"] == "BitrateMode.ABR":
        folder_name_pattern["media"] = "ABR"

    # Apply the new folder name pattern
    new_folder_name = "{year} {title} [{type}{catno}] @{media}".format(
        year=release_date,
        title=strip_accents(release_title),
        type=type_descriptions if catalogue_number \
            else type_descriptions.strip(', '),
        catno=str(catalogue_number).upper(),
        media=folder_name_pattern["media"]
    )
    os.rename(opts.folder, new_folder_name)
    calculated_duration = calculate_durations(0, release=release)
    
    # Print release details
    print(f"processed release title: {new_folder_name}\n")
    for track in prepared_tracks:
        print(f"{track.position} {track.title} {track.duration}")
    print("============ total duration (h:m:s): ",
        f"{calculated_duration[0]:02d}:{calculated_duration[1]:02d}"
        f":{calculated_duration[2]:02d}")
    print("==== total duration [audio] (h:m:s): ",
        f"{calculated_duration_from_audio[0]:02d}:"
        f"{calculated_duration_from_audio[1]:02d}:"
        f"{calculated_duration_from_audio[2]:02d}")
    print("================== folder size (Mb): ", "{:.2f}".format(
        float(get_folder_size(new_folder_name)) / 1000000.0).replace(".", ","))
    print("\n================== sample rate (Hz): ",
        fetched_release_info["sample_rate"] \
        if "sample_rate" in fetched_release_info.keys() else "no data")
    print("================== bit depth (bits): ",
        fetched_release_info["bits_per_sample"] \
        if "bits_per_sample" in fetched_release_info.keys() else "no data")
    print("==================== bitrate (kbps): ",
        fetched_release_info["bitrate_kbps"] \
        if "bitrate_kbps" in fetched_release_info.keys() else "no data")
    print("========================== channels: ",
        fetched_release_info["channels"] \
        if "channels" in fetched_release_info.keys() else "no data")


if __name__ == '__main__':
    main()
