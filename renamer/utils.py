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
    text = text.decode("utf-8")
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


def filter_files(folder_files):
    mp3_files = fnmatch.filter(folder_files, '*.mp3')
    flac_files = fnmatch.filter(folder_files, '*.flac')
    m4a_files = fnmatch.filter(folder_files, '*.m4a')
    if mp3_files:
        files_count = len(mp3_files)
        sample_file = mp3_files[0]
    if flac_files:
        files_count = len(flac_files)
        sample_file = flac_files[0]
    if m4a_files:
        files_count = len(m4a_files)
        sample_file = m4a_files[0]
    sample_file = strip_accents(sample_file.replace("_", " ")
        .replace(".", " ").replace("-", " ")).lower()
    return files_count, sample_file
