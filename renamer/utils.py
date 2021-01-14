#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import fnmatch
import unicodedata


def get_folder_size(folder):
    total_size = os.path.getsize(folder)
    for item in os.listdir(folder):
        itempath = os.path.join(folder, item)
        if os.path.isfile(itempath):
            total_size += os.path.getsize(itempath)
        elif os.path.isdir(itempath):
            total_size += getFolderSize(itempath)
    return total_size


def strip_accents(text):
    text = unicodedata.normalize('NFD', text)
    text = text.encode('ascii', 'ignore')
    text = text.decode('utf-8')
    return str(text)


def pick_release_format_id(release):
    for release_format in release.formats:
        if "CD" in release_format["name"]:
            return release.id
        elif "Vinyl" in release_format["name"]:
            return release.id
        elif "File" in release_format["name"]:
            return release.id
        else:
            return release.id


def is_audio_file(filename, extensions=['.mp3', '.flac', '.m4a', '.wav']):
    return any(filename.lower().endswith(e) for e in extensions)


def prepare_sample_file(sample_file):
    return strip_accents(
        sample_file.replace("_", " ").replace(".", " ").replace("-", " ")
    ).lower()


def prepare_track_title(track):
    return strip_accents(track).lower().replace("/", " ").replace("(", "") \
        .replace(")", "")


def filter_files(folder_files):
    audio_files = [filename for filename in filter(is_audio_file, folder_files)]
    sample_file_1 = prepare_sample_file(audio_files[0])
    sample_file_2 = prepare_sample_file(audio_files[-1])
    files_count = len(audio_files)
    return audio_files, files_count, sample_file_1, sample_file_2


def calculate_durations(total_seconds, release=None):
    if release:
        durations = [track.duration for track in release.tracklist \
            if track.duration]
        minutes_from_durations = sum([int(i.split(':')[0]) for i in durations])
        seconds_from_durations = sum([int(i.split(':')[1]) for i in durations])
        total_seconds = minutes_from_durations * 60 + seconds_from_durations

    hours = int(total_seconds / 3600)
    total_seconds %= 3600
    minutes = int(total_seconds / 60)
    total_seconds %= 60
    seconds = int(total_seconds)

    return (hours, minutes, seconds)


def print_release_version(release):
    artist = release.artists[0].name
    title = release.title
    label = release.labels[0].name
    catno = release.data.get('catno')
    format_details = ', '.join(f"{v}" for k, v in release.formats[0].items())
    country = release.country
    released_date = release.data.get('released_formatted')
    genre = ', '.join(release.genres)
    styles = ', '.join(release.styles)
    discogs_id = release.id
    print(
        f"{artist} - {title}\n\n"
        f"Label:      {label} - {catno}\n"
        f"Format:     {format_details}\n"
        f"Country:    {country}\n"
        f"Released:   {released_date}\n"
        f"Discogs ID: {discogs_id}\n\n"
        "Tracklist"
    )
    print("-" * 75)
    for track in release.tracklist:
        print(f"{track.position:<5} {track.title:<60} {track.duration:<10}")
    print("=" * 75)
