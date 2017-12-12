from picamera import PiCamera
import errno
import os
import re
import sys
import threading
import Queue
from datetime import datetime, timedelta
from time import sleep
import yaml

config = yaml.safe_load(open(os.path.join(sys.path[0], 'config.yml')))

# defaults
series_name = 'series'
output_dir = sys.path[0]
date_string = '%Y-%m-%d'
time_string = '%H:%M:%S'

image_number = 0
total_images = 0
mode = {}

gif_location = ''
mp4_location = ''

# custom
if 'series_name' in config:
    series_name = config['series_name']
if 'output_dir' in config:
    output_dir = config['output_dir']
if 'time_string' in config:
    time_string = config['time_string']
if 'date_string' in config:
    date_string = config['date_string']


email = {}
if 'email_address' in config:
    email['email_address'] = config['email_address']
if 'email_password' in config:
    email['email_password'] = config['email_password']
if 'email_to_address' in config:
    email['email_to_address'] = config['email_to_address']

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
    if all(k in config for k in ('start_time', 'end_time')):
        now_date_str = now.strftime(date_string)

        # setup Daily attributes
        mode['type'] = 'Daily'
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
            # or is in the middle of Daily run
            image_number = ((now - mode['start_time']) / config['interval']).seconds
    else:
        mode['type'] = 'Once'
        total_images = config['total_images']
        dir_slug = valid_filename('{}-{}_{}'.format(
                series_name, now.strftime(date_string), now.strftime(time_string)
            ))
        mode['dir'] = os.path.join(
            output_dir,
            dir_slug
        )


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


def show_progress(action, action_args=(), msg='working', sec=0.5):
    s = '.'
    t = threading.Thread(target=action, args=action_args)
    t.start()
    sys.stdout.write( msg )
    while t.is_alive():
        sys.stdout.write( s )
        sys.stdout.flush()
        sleep(sec)


def make_gif():
    global gif_location
    # ImageMagick Setup, for more options see
    # https://www.imagemagick.org/script/command-line-options.php
    envs = ['MAGICK_THREAD_LIMIT=1', 'MAGICK_THROTTLE=50']
    flags = ['-delay 10', '-loop 0' ]
    output_dir = mode['dir']
    gif_name = 'timelapse.gif'
    
    if 'gif_flags' in config:
        flags.insert(len(flags),config['gif_flags'])
        
    if 'gif_output_dir' in config:
        output_dir = config['gif_output_dir']
        
    if 'gif_name' in config:
        gif_name = config['gif_name']

    gif_path = os.path.join(mode['dir'], gif_name)
    g_input = mode['dir'] + '/image*.jpg'

    # build command line string
    cmd = [envs, ['convert'], flags, [g_input, gif_path]]
    cmd = ' '.join(str(r) for v in cmd for r in v)

    # run the system command
    os.system(cmd)


def make_video():
    mp4_name = 'timelapse.mp4'
    if 'mp4_name' in config:
        mp4_name = config['mp4_name']

    mp4_path = os.path.join(mode['dir'], mp4_name)

    os.system('avconv -framerate 20 -i ' + mode['dir'] + '/image%05d.jpg -vf format=yuv420p ' + mp4_path)


def export_timelapse(type):
    if type == 'gif':
        export_func = make_gif
        namespace = 'GIF:'
        export_name = 'timelapse.gif'
        if 'gif_name' in config:
            export_name = config['gif_name']
    elif type == 'mp4':
        export_func = make_video
        namespace = 'VIDEO:'
        export_name = 'timelapse.mp4'
        if 'mp4_name' in config:
            export_name = config['mp4_name']
    try:
        start_t = datetime.now()
        show_progress(
            export_func, 
            msg='{} converting'.format(namespace), 
            sec=1
        )
        export_path = os.path.join(mode['dir'], export_name)
        print '{} {}'.format(namespace, export_path)
    except KeyboardInterrupt, SystemExit:
        print '{} convertion stopped.'.format(namespace)
    finally:
        elapsed_s = abs((datetime.now() - start_t).seconds)
        print '{} completed in {} seconds'.format(namespace, elapsed_s)

    if config['export_email'] == True:
        email_export(export_path)


def email_export(file_path):
    import smtplib
    from email.MIMEMultipart import MIMEMultipart
    from email.MIMEText import MIMEText
    from email.MIMEBase import MIMEBase
    from email import encoders

    fromaddr = email['email_address']
    toaddr = email['email_to_address']

    msg = MIMEMultipart()

    msg['From'] = fromaddr
    msg['To'] = toaddr
    now = datetime.now()

    msg['Subject'] = 'Todays {} update | {}'.format(
        series_name, now.strftime(date_string))
    
    body = 'Enjoy you {} update for the day.'.format(series_name)
    msg.attach(MIMEText(body, 'plain'))
     
    filename = os.path.basename(os.path.normpath(file_path))
    attachment = open(file_path, 'rb')

    part = MIMEBase('application', 'octet-stream')
    part.set_payload((attachment).read())
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', 'attachment; filename= %s' % filename)
     
    msg.attach(part)

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(fromaddr, email['email_password'])
    text = msg.as_string()
    server.sendmail(fromaddr, toaddr, text)
    server.quit()


def finish_capture():
    print 'Finishing capture!\n'

    # Create an animated gif (Requires ImageMagick).
    if config['create_gif']:
        export_timelapse('gif')

    # Create a video (Requires avconv - which is basically ffmpeg).
    if config['create_video']:
        export_timelapse('mp4')

    # exit or schedule script
    if mode['type'] == 'Once':
        print 'Time-lapse capture complete!'
        sys.exit()

    elif mode['type'] == 'Daily':

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
    if mode['type'] == 'Daily' and now < mode['start_time']:
        # schedule start_capture to run at start_time
        delay = abs((mode['start_time'] - now).seconds)
        if delay > 0:
            print 'Capture will start in {}s'.format(delay)
            print 'at {}\n'.format(mode['start_time'].strftime(FMT))
            thread = threading.Timer(delay, capture_image).start()
    # if after finish time wait
    elif mode['type'] == 'Daily' and now > mode['end_time']:
        finish_capture()
    # capture images
    else:
        print 'Starting capture!\n'
        capture_image()


def start_capture():
    # config mode
    config_mode()
    # print starting message
    pretty_print()
    # create the directory
    create_timestamped_dir(mode['dir'])
    # wait or capture images
    wait_or_capture_image()


# sets capture mode and starts capture
start_capture()
