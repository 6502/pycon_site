#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os
import os.path
import logging
import sys
import ConfigParser
from optparse import OptionParser
from PIL import Image

parser = OptionParser(usage = '%prog [-v] [-a] [work_dir]')
parser.add_option('-v', '--verbose',
    dest = 'verbose', action = 'store_true', default = False)
parser.add_option('-a', '--all',
    dest = 'all', action = 'store_true', default = False,
    help = 'processa tutte le immagini, non solo quelle modificate')

(options, args) = parser.parse_args()
if len(args) > 1:
    parser.error("incorrect number of arguments")
else:
    try:
        work_dir = args[0]
    except IndexError:
        work_dir = '.'

logging.basicConfig()
log = logging.getLogger('p3')
if options.verbose:
    log.setLevel(logging.DEBUG)
else:
    log.setLevel(logging.WARNING)

def inspect():
    for root, subdirs, files in os.walk(work_dir):
        if 'resize.ini' not in files:
            continue
        yield os.path.join(root, 'resize.ini')

def parseConfigFile(fpath):
    parser = ConfigParser.SafeConfigParser()
    good = parser.read(fpath)
    if not good:
        raise ValueError('invalid file')
    try:
        rule = parser.get('resize', 'rule')
    except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
        raise ValueError('value resize/rule not found')
    actions = [ r.split('=', 1) for r in rule.split(';') ]
    return [(a[0], a[1].split(',')) for a in actions]

class Resize(object):
    def __init__(self, cfg):
        self.cfg = cfg

    def __call__(self, src, dst):
        img = Image.open(src)
        if img.mode not in ('RGB', 'RGBA'):
            img = img.convert('RGBA')
        for action, params in self.cfg:
            try:
                img = getattr(self, action)(img, *params)
            except AttributeError:
                raise ValueError('invalid action: %s' % action)
            except TypeError:
                raise ValueError('invalid params for action: %s' % action)
        img.save(dst, 'JPEG', quality=90)

    def box(self, img, size):
        size = map(float, size.split('x'))
        iw, ih = img.size
        if iw > ih:
            nw = size[0]
            nh = ih * nw / iw
        else:
            nh = size[1]
            nw = iw * nh / ih
        return img.resize((int(nw), int(nh)), Image.ANTIALIAS)

    def canvas(self, img, size, bg):
        size = map(int, size.split('x'))
        i = Image.new('RGB', size, bg)
        paste_point = []
        for d1, d2 in zip(size, img.size):
            if d1 < d2:
                paste_point.append(0)
            else:
                paste_point.append((d1 - d2) / 2)
        if img.mode == 'RGBA':
            i.paste(img, tuple(paste_point), img)
        else:
            i.paste(img, tuple(paste_point))
        return i

def resize_dir(cfg, src, dst):
    count = 0
    resizer = Resize(cfg)
    for fname in os.listdir(src):
        if fname == 'resize.ini' or fname[0] == '.':
            continue
        spath = os.path.join(src, fname)
        if not os.path.isfile(spath):
            continue
        dpath = os.path.join(dst, os.path.splitext(fname)[0] + '.jpg')
        if not options.all:
            if os.path.isfile(dpath):
                sstat = os.stat(spath)
                dstat = os.stat(dpath)
                if dstat.st_mtime > sstat.st_mtime:
                    continue
        try:
            resizer(spath, dpath)
        except IOError:
            log.info('invalid image: %s', spath)
            continue
        count += 1
    return count

log.info('inspecting %s', work_dir)
for cpath in inspect():
    log.info('config file found: %s', cpath)
    try:
        cfg = parseConfigFile(cpath)
    except ValueError, e:
        log.warn('skipping config file: %s', e)
        continue
    src_dir = os.path.dirname(cpath)
    dst_dir = os.path.join(src_dir, 'resized')
    if not os.path.isdir(dst_dir):
        log.info('mkdirs %s', dst_dir)
        os.makedirs(dst_dir)
    try:
        count = resize_dir(cfg, src_dir, dst_dir)
    except ValueError, e:
        log.warn('aborting: %s', e)
        sys.exit(1)
    log.info('resized %d files', count)
