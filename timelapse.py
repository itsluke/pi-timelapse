from picamera import PiCamera
import errno
import os
import re
import sys
import threading
from datetime import datetime, timedelta
from time import sleep
import yaml

config = yaml.safe_load(open(os.path.join(sys.path[0], "config.yml")))

# defaults
series_name = 'series'
output_dir = sys.path[0]
date_string = '%Y-%m-%d'
time_string = '%H:%M:%S'

image_number = 0
total_images = 0
mode = {}

# custom
if 'series_name' in config:
    series_name = config['series_name']
if 'output_dir' in config:
    output_dir = config['output_dir']
if 'time_string' in config:
    time_string = config['time_string']
if 'date_string' in config:
    date_string = config['date_string']

FMT = '{} {}'.format(date_string, time_string)


def create_timestamped_dir(dir):
    try:
        os.makedirs(dir)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise


def set_camera_options(camera):
    # Set camera resolution.
    if config['resolution']:
        camera.resolution = (
            config['resolution']['width'],
            config['resolution']['height']
        )

    # Set ISO.
    if config['iso']:
        camera.iso = config['iso']

    # Set shutter speed.
    if config['shutter_speed']:
        camera.shutter_speed = config['shutter_speed']
        # Sleep to allow the shutter speed to take effect correctly.
        sleep(1)
        camera.exposure_mode = 'off'

    # Set white balance.
    if config['white_balance']:
        camera.awb_mode = 'off'
        camera.awb_gains = (
            config['white_balance']['red_gain'],
            config['white_balance']['blue_gain']
        )

    # Set camera rotation
    if config['rotation']:
        camera.rotation = config['rotation']

    return camera


def config_mode():
    global image_number
    global total_images
    global mode
    now = datetime.now()

    # check if start and end time are present
    if all(k in config for k in ("start_time", "end_time")):
        now_date_str = now.strftime(date_string)

        # setup daily attributes
        mode['type'] = 'daily'
        mode['start_time'] = datetime.strptime('{} {}'.format(
            now_date_str, config['start_time']), FMT)
        mode['end_time'] = datetime.strptime('{} {}'.format(
            now_date_str, config['end_time']), FMT)

        duration = mode['end_time'] - mode['start_time']
        total_images = (duration/config['interval']).seconds

        # set todays dir
        mode['dir'] = os.path.join(
            output_dir,
            valid_filename(series_name),
            valid_filename(now_date_str)
        )

        # TODO: need to account for start/end times
        # that bridge midnight
        if (now > mode['start_time']):
            # set current image number if script restarts
            # or is in the middle of daily run
            image_number = ((now - mode['start_time']) / config['interval']).seconds
    else:
        total_images = config['total_images']
        mode['type'] = 'Once'
        dir_slug = valid_filename('{}-{}_{}'.format(
                series_name, now.strftime(date_string), now.strftime(time_string)
            ))
        mode['dir'] = os.path.join(
            output_dir,
            dir_slug
        )

    pretty_print()


def pretty_print():
    print '------------', 'timelapse.py', '-------------'
    if mode['type'] == 'Once':
        print 'Mode: {} | Interval: {}s | Image Count: {}'.format(
            mode['type'], config['interval'], total_images)

        print 'Output Dir: {}/'.format(os.path.basename(mode['dir']))
    else:
        print 'Mode: {} | Interval: {}s | Daily Count: {}'.format(
                mode['type'], config['interval'], total_images)
        print 'timelapse from: {} to: {}'.format(
            mode['start_time'].strftime(time_string),
            mode['end_time'].strftime(time_string)
        )
        print 'Output Dir: {}/{}'.format(
            series_name, os.path.basename(mode['dir'])
        )

    print '------------------------------------------'


def valid_filename(s):
    """
    Return the given string converted to a string that can be used for a clean
    filename. Remove leading and trailing spaces; convert other spaces to
    underscores; and remove anything that is not an alphanumeric, dash,
    underscore, or dot.
    >>> get_valid_filename("john's portrait in 2004.jpg")
    'johns_portrait_in_2004.jpg'
    """
    s = str(s).strip().replace(' ', '_')
    return re.sub(r'(?u)[^-\w.]', '', s)


def capture_image():
    try:
        global image_number

        # Set a timer to take another picture at the proper interval after this
        # picture is taken.
        if (image_number < (total_images - 1)):
            thread = threading.Timer(config['interval'], capture_image).start()

        # Start up the camera.
        camera = PiCamera()
        set_camera_options(camera)

        # Capture a picture.
        camera.capture(mode['dir'] + '/image{0:05d}.jpg'.format(image_number))
        camera.close()

        print 'Taking image {}/{}'.format(image_number + 1, total_images)

        if (image_number < (total_images - 1)):
            image_number += 1
        else:
            finish_capture()

    except KeyboardInterrupt, SystemExit:
        print '\nTime-lapse capture cancelled.\n'


def create_gif():
    # ImageMagick Setup, for more options see
    # https://www.imagemagick.org/script/command-line-options.php

    envs = ['MAGICK_THREAD_LIMIT=1', 'MAGICK_THROTTLE=50']
    flags = ['-delay 10', '-loop 0', '-resize 50' ]
    output = mode['dir'] + '-timelapse.gif'

    # build command line string
    cmd = [envs, ['convert'], flags, ['/image*.jpg', output ]]
    cmd = ' '.join(str(r) for v in cmd for r in v)

    try:
        print 'GIF: {}'.format(output)
        print 'GIF: starting gif convertion'
        start_t = datetime.now()
        os.system(' '.join(str(r) for v in convert_cmd for r in v) )
    except KeyboardInterrupt, SystemExit:
        print 'GIF: convertion stopped.'
    else:
        print 'GIF: convertion failed.'
    finally:
        elapsed_s = abs((datetime.now() - start_t).seconds)
        print 'GIF: {}'.format(output)
        print 'GIF: completed in {} seconds'.format(elapsed_s)


def finish_capture():
    print 'Finishing capture!\n'
    # Create an animated gif (Requires ImageMagick).
    if config['create_gif']:
        create_gif()

    # Create a video (Requires avconv - which is basically ffmpeg).
    if config['create_video']:
        print 'Creating video.'
        os.system('avconv -framerate 20 -i ' + mode['dir'] + '/image%05d.jpg -vf format=yuv420p ' + mode['dir'] + '/timelapse.mp4')  # noqa

    # exit or schedule script
    if mode['type'] == 'Once':
        print 'Time-lapse capture complete!'
        sys.exit()

    elif mode['type'] == 'daily':
        now = datetime.now()

        # calculate time till tomorrows start
        eod = datetime(now.year, now.month, now.day) + timedelta(days=1, microseconds=-1)
        sod = eod + timedelta(microseconds=1)
        start_tomorrow = ((eod - now)+(mode['start_time'] - sod)).seconds

        print 'Capture complete for today. Starting tomorrow @ {}'.format(
            mode['start_time'].strftime(time_string))

        # schedule start_capture to run again at start_time
        thread = threading.Timer(start_tomorrow, start_capture).start()


def wait_or_capture_image():
    # get time now
    now = datetime.now()

    # if before start time wait
    if mode['type'] == 'daily' and now < mode['start_time']:
        # schedule start_capture to run at start_time
        delay = (mode['start_time'] - now).total_seconds()
        if delay > 1:
            print '\nWaiting till:', mode['start_time'].strftime(FMT), '\n'
            thread = threading.Timer(delay, capture_image).start()
        else:
            sleep(delay)
    # if after finish time wait
    elif mode['type'] == 'daily' and now > mode['end_time']:
        finish_capture()
    # capture images
    else:
        print 'Starting capture!\n'
        capture_image()


def start_capture():
    # config mode
    config_mode()
    # create the directory
    create_timestamped_dir(mode['dir'])
    # wait or capture images
    wait_or_capture_image()

# sets capture mode and starts capture
start_capture()
