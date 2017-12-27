import errno
import os
import re
import sys
import threading
# import Queue
import base64
import smtplib
import yaml

from subprocess import PIPE, Popen
from string import Template

from email.mime import multipart as MIMEMultipart
from email.mime import base as MIMEBase
from email.mime import text as MIMEText
from email import encoders as Encoders

from datetime import datetime, timedelta
from time import sleep

from picamera import PiCamera

#################################################
#################################################
#################################################

def get_cpu_temperature():
    process = Popen(['vcgencmd', 'measure_temp'], stdout=PIPE)
    output, _error = process.communicate()
    return float(output[output.index('=') + 1:output.rindex("'")])

#################################################
#################################################
#################################################


def with_wait_animation(
        method,
        method_args=(),
        msg='working',
        sec=0.5):
    """
    Adds a wait animation to a long running method.
    >>> with_wait_animation(encode, ('gif'), 'encoding', 0.5)
    encoding............
    """
    animation = '.'
    thr = threading.Thread(target=method, args=method_args)
    thr.start()
    sys.stdout.write(msg)
    while thr.is_alive():
        sys.stdout.write(animation)
        sys.stdout.flush()
        sleep(sec)

    print '\nfinished\n'


def valid_filename(string):
    """
    Return the given string converted to a string that can be used for a clean
    filename. Remove leading and trailing spaces; convert other spaces to
    underscores; and remove anything that is not an alphanumeric, dash,
    underscore, or dot.
    >>> valid_filename("i hope my plants are ok.jpg")
    'i_hope_my_plants_are_ok.jpg'
    """
    string = str(string).strip().replace(' ', '_')
    return re.sub(r'(?u)[^-\w.]', '', string)


def run_at(action, start_time=None, interval_in_s=None):
    now = datetime.now()

    if not interval_in_s:
        if not start_time:
            raise Exception("please set a start time or interval")
        if now > start_time:
            print 'start: {}, now : {}'.format(
                start_time.strftime('%H:%M:%S %Y-%m-%d '),
                now.strftime('%H:%M:%S %Y-%m-%d'))
            raise Exception("start time is in the past")
        else:
            interval_in_s = (start_time - now).seconds
            print 'starting action at {}'.format(
                start_time.strftime('%H:%M:%S %Y-%m-%d '))
            print '{} seconds from {}'.format(
                interval_in_s,
                now.strftime('%H:%M:%S %Y-%m-%d'))

    thread = threading.Timer(interval_in_s, action)
    thread.start()


def setup_camera(camera, options=None):
    """
    sets any custom options and returns the camera
    >>> set_camera(options)
    """
    if 'resolution' in options:
        camera.resolution = (
            options['resolution']['width'],
            options['resolution']['height']
        )

    if 'iso' in options:
        camera.iso = options['iso']

    if 'shutter_speed' in options:
        camera.shutter_speed = options['shutter_speed']
        # Sleep to allow the shutter speed to take effect correctly.
        sleep(1)
        camera.exposure_mode = 'off'

    # Set white balance.
    if 'white_balance' in options:
        camera.awb_mode = 'off'
        camera.awb_gains = (
            options['white_balance']['red_gain'],
            options['white_balance']['blue_gain']
        )

    # Set camera rotation
    if 'rotation' in options:
        camera.rotation = options['rotation']


class Timelapse(object):
    """Creates a new timelapse to be run on the pi"""
    LOCAL_DEV = False

    #################################################

    class Export(object):
        """class for timelapse Gif creation and exporting"""

        name = None
        output = None
        input = None
        latest = None
        last_run = None
        count = None

        def __init__(self, options=None):
            super(Timelapse.Export, self).__init__()

            if options is not None:
                self.set_output(options)

        def set_output(self, options):
            """
            set output options
            """
            if 'name' in options:
                self.name = options['name']

            if 'output_dir' in options:
                if self.output is None:
                    self.output = options['output_dir']
                elif options['overwrite']:
                    self.output = options['output_dir']

            if 'input' in options:
                self.input = options['input']
            else:
                self.input = self.output

        def create(self):
            """
            run export's .run function with
            animated wait timer.
            """
            with_wait_animation(self.run)

        def run(self):
            """
            all actions required to process export
            """
            print 'no export function availible for {}'.format(self.__class__.__name__)

    #################################################

    class Gif(Export):
        """
        class for timelapse Gif creation and exporting
        """
        name = 'timelapse.gif'
        base64 = None

        base64_file = None
        file = None

        envs = ['MAGICK_THREAD_LIMIT=1', 'MAGICK_THROTTLE=50']
        flags = ['-delay 10', '-loop 0']

        def __init__(self, options=None):
            super(Timelapse.Gif, self).__init__(options)
            if options is not None:

                if 'flags' in options:
                    self.flags.insert(
                        len(self.flags), options['flags'])

                if 'encode_base64' in options:
                    self.base64 = options['encode_base64']

        def __gif(self):
            self.file = os.path.join(
                self.output,
                self.name
            )

            # assemble config options
            cmd = [
                self.envs,
                ['convert'],
                self.flags,
                [self.input, os.path.join(self.output, self.name)]
            ]
            cmd = ' '.join(str(r) for v in cmd for r in v)
            print 'cmd: {}'.format(cmd)
            # run command
            os.system(cmd)

        def __base64(self):
            base64_file = self.file + '_base64.txt'

            if Timelapse.LOCAL_DEV:
                print '\nDEV making base64 file: {}'.format(base64_file)
                sleep(10)
                return

            with open(self.file, "rb") as image_file:
                txt_file = open(base64_file, 'w')
                txt_file.write(
                    base64.b64encode(image_file.read())
                )
                txt_file.close()

            self.base64_file = base64_file

        def run(self):
            # create export
            self.__gif()
            if self.base64:
                self.__base64()

    #################################################

    class Video(Export):
        """
        class for timelapse Gif creation and exporting
        """
        name = 'timelapse.mp4'
        file = None
        envs = []
        flags = ['-framerate 20', '-vf format=yuv420p']

        def __init__(self, options=None):
            super(Timelapse.Video, self).__init__(options)

            if options is not None:
                if 'flags' in options:
                    self.flags.insert(
                        len(self.flags), options['flags'])

        def __video(self):
            self.input = self.input.replace('*', '%05d')

            cmd = [
                self.envs,
                ['avconv'],
                self.flags,
                ['-i', self.input, self.output + self.name]
            ]
            cmd = ' '.join(str(r) for v in cmd for r in v)

            if Timelapse.LOCAL_DEV:
                print 'DEV: {}'.format(cmd)
                sleep(20)
                return

            # run command
            os.system(cmd)

        def run(self):
            # create export
            self.__video()

    #################################################

    class Email(Export):
        """
        class for timelapse Gif creation and exporting
        """
        name = 'email'
        export_type = None
        attrs = {}
        message = None

        def __init__(self, options=None):
            super(Timelapse.Email, self).__init__(options)

            self.export_gif = options['send_gif']

            if options:
                try:
                    self.setup(options)
                except AttributeError:
                    print 'Invalid attributes. Email not setup, please try again'

        def setup(self, options):

            req = ['address', 'password', 'to_address']

            for k in req:
                if k in options:
                    self.attrs[k] = options[k]

            if any(k not in self.attrs for k in req):
                raise AttributeError(
                    "please supply an 'address', 'password' and 'to_address")
            else:
                msg = MIMEMultipart('related')
                msg['From'] = self.attrs['address']
                msg['To'] = self.attrs['to_address']
                msg.preamble = 'Your daily {} email.'.format(
                    Timelapse.info['name'])

                self.message = msg

        def __root(self):
            # msg = MIMEMultipart()
            now = datetime.now()
            self.message['Subject'] = 'Todays {} update | {}'.format(
                Timelapse.info['name'],
                now.strftime(Timelapse.date_str)
            )

        def __text(self):
            body_text = 'Enjoy your {} update for the day.\n'.format(
                Timelapse.info['name']
            )

            return MIMEText(body_text, 'plain')

        def __html(self):
            with open('html_boilerplate.txt', 'r') as mailer:
                boilerplate = Template(mailer.read())
            now = datetime.now()
            body_html = boilerplate.safe_substitute(
                html_bp_PREHEADER='Your daily groww light email',
                html_bp_MAIN_HEADER='Enjoy your {0} report'.format(Timelapse.info['name']),
                html_bp_MAIN_SUB=now.strftime(Timelapse.date_str),
                html_bp_MAIN_BODY='Here\'s your daily update on the fisheys.',
                html_bp_second_HEADER='Info on the setup',
                html_bp_second_SUB='Temp: {} | Light Hours: {} | Humity: {}'.format(
                    getCPUtemperature(),
                    '?',
                    '?'
                ),
                html_bp_second_BODY='Sed nisl augue, laoreet ut dictum in, cursus in risus. Nam egestas dignissim erat ac iaculis.'
            )

            return MIMEText(body_html, 'html')

        def __image(self):
            encoded_attachment = None
            attachment = None

            print 'looking in {}'.format(self.output)
            for found_file in os.listdir(self.output):
                # if base64 found_file
                if found_file.endswith(".txt"):
                    encoded_attachment = open(
                        os.path.join(self.output, found_file), 'rb')
                elif found_file.endswith(".gif"):
                    print 'found gif: {}'.format(found_file)
                    filename = os.path.basename(
                        os.path.normpath(found_file))
                    original = os.path.join(
                        self.output, found_file)
                    print 'original: {}'.format(original)
                    sleep(1)

            part = MIMEBase('application', 'octet-stream')

            if encoded_attachment:
                part.set_payload(encoded_attachment.read())
                part.add_header('Content-Transfer-Encoding', 'base64')

            if attachment:
                part.set_payload((attachment).read())
                Encoders.encode_base64(part)

            if not attachment:
                attachment = open(original, 'rb')
                part.set_payload((attachment).read())
                Encoders.encode_base64(part)

            part.add_header(
                'Content-Disposition',
                'attachment; filename= %s' %
                filename)

            part.add_header('Content-ID', '<image1>')

            self.message.attach(part)

        def __send(self):
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(self.attrs['address'], self.attrs['password'])

            server.sendmail(
                self.attrs['address'],
                self.attrs['to_address'],
                self.message.as_string())

            server.quit()

        def __email(self):

            # msg = MIMEMultipart()
            self.__root()

            msg_alternative = MIMEMultipart('alternative')
            self.message.attach(msg_alternative)

            # msg.attach(MIMEText(body_text, 'plain'))
            msg_alternative.attach(self.__text())
            msg_alternative.attach(self.__html())

            if self.export_gif:
                self.__image()

            self.__send()

        def run(self):
            # create export
            print 'DEV waiting {}'.format(self.name)
            self.__email()

            # wrap this function in 'loader'

    #################################################

    name = 'series'

    info = {
        'name': 'series',
        'path': '/home/pi/timelapse_photos',
        'filename': 'image'
    }

    __ran = {
        'first': None,
        'last': None,
        'count': None
    }

    __schedule = {
        'repeat': None,
        'start': None,
        'end': None,
        'interval': None,
        'total_images': None,
        'current_image': None,
        'current_image_dir': None
    }

    __camera_options = None

    date_str = '%Y-%m-%d'
    time_str = '%H:%M:%S'
    d_t_str = '{}_{}'.format(date_str, time_str)

    __camera = None
    __exports = None

    config = None

    def __init__(self, name=None, config_path='config.yml'):
        """
        init class with a name for timelapse
        e.g. fish-monitor
        optionaly pass a config .yml file
        """
        super(Timelapse, self).__init__()

        # load yml config
        self.config = yaml.safe_load(
            open(os.path.join(sys.path[0], config_path)))

        # set name
        if name:
            self.info['name'] = name
        elif 'series_name' in self.config:
            self.info['name'] = self.config['series_name']

        if 'interval' in self.config:
            self.__schedule['interval'] = self.config['interval']

        # setup output
        self.setup('timings', self.config)

        # setup output
        self.setup('output', self.config)

        # setup output
        self.setup('camera', self.config)

        # setup gif export
        if self.config['create_gif']:
            if self.config['gif'] != {}:
                self.setup_export('gif', self.config['gif'])
            else:
                self.setup_export('gif')

        # setup video export
        if self.config['create_video']:
            if self.config['video'] != {}:
                self.setup_export('video', self.config['video'])
            else:
                self.setup_export('video')

        # setup email export
        if self.config['export_email'] and self.config['email'] != {}:
            print 'setting up email export'
            self.setup_export('email', self.config['email'])

    def __pretty_print_info(self):
        """
        Pretty prints timelapse info.
        >>> __pretty_print_info()
        ------------ timelapse.py -------------
        Mode: Once | Interval: 3s | Image Count: 15
        Output Dir: here-fishy-fishy-171206_211431/
        Last Run: 06 Dec 2017 @ 21:14
        ------------------------------------------
        """
        msg = "\n=============== timelapse.py ================\n\n"
        msg += "Type: {0} | Interval: {1}s | Image Count: {2}\n"
        msg += "Output Dir: {3}\n"
        msg += "Last Run: {4}\n"

        msg = msg.format(
            self.__schedule['repeat'],
            self.__schedule['interval'],
            self.__schedule['total_images'],
            self.info['path'],
            self.__ran['last']
        )

        for ex in self.__exports:
            info = "Export --------------------------------------\n"
            info += "Type: {0} | Name: {1}\n"

            info = info.format(ex.__class__.__name__, ex.name)
            msg += info

        msg = msg + "\n=============================================\n"

        print msg

    def __add_export(self, export):
        if self.__exports is None:
            self.__exports = []
        self.__exports.append(export)

    def __create_current_dir(self):
        if not self.info['path']:
            self.info['path'] = '/home/pi/timelapse_photos/'

        if not self.name:
            self.name = 'series'

        if not self.__schedule['start']:
            raise Exception(
                "Timings not setup. Please re-run '.setup('timings')'")

        # build current dir path
        # inc valid filename check
        current_dir = os.path.join(
            self.info['path'],
            self.name,
            valid_filename(
                self.__schedule['start'].strftime(self.d_t_str)
            )
        )

        try:
            os.makedirs(current_dir)
            self.__schedule['current_image_dir'] = current_dir

            # update exports
            for export in self.__exports:

                options = {
                    'output_dir': current_dir,
                    'overwrite': True}

                options['input'] = os.path.join(
                    current_dir,
                    self.info['filename'] + '*.jpg')

                export.set_output(options)

        except OSError as err:
            if err.errno != errno.EEXIST:
                raise

    def __all_clear(self):
        if self.__camera_options is None:
            raise Exception(
                "Camera is not setup. Please re-run '.setup('camera')")

        if self.info['path'] is None:
            raise Exception(
                "Output is not setup. Please re-run '.setup('output')")

        if self.__schedule['current_image_dir'] is None:
            # create current image dir
            self.__create_current_dir()

    def __take_image(self):
        self.__all_clear()
        try:
            camera = PiCamera()
            setup_camera(camera, self.__camera_options)

            camera.capture(
                '{0}/{1}_{2:05d}.jpg'.format(
                    self.__schedule['current_image_dir'],
                    self.info['filename'],
                    self.__schedule['current_image']
                )
            )
            camera.close()

            self.__schedule['current_image'] += 1
        except BaseException:
            sleep(1)
            print 'Camera capture did not complete'

    def __setup_timings(self, options):
        """
        set timing options
        >>> set_timings(options)
        """
        now = datetime.now()
        now_date_str = now.strftime(self.date_str)

        # Set start time for capture
        if 'start_time' in options:
            start_at = datetime.strptime('{}_{}'.format(
                now_date_str,
                options['start_time']
            ), self.d_t_str)
        else:
            start_at = now

        self.__schedule['start'] = start_at

        # Set end time for capture
        if 'end_time' in options:
            end_at = datetime.strptime('{}_{}'.format(
                now_date_str,
                options['end_time']
            ), self.d_t_str)

            # check if end time move it to the next day
            if end_at < start_at:
                end_at += timedelta(days=1)

            # set end time
            self.__schedule['end'] = end_at

            # set total images
            duration = end_at - start_at
            self.__schedule['total_images'] = (
                duration / self.__schedule['interval']).seconds
        else:
            self.__schedule['total_images'] = options['total_images']

        if now > start_at:
            # set current image number if script restarts
            # or is in the middle of Daily run
            self.__schedule['current_image'] = (
                (now - start_at) / self.__schedule['interval']).seconds

        if 'every_days' in options:
            self.__schedule['repeat'] = options['repeat']

    def __setup_output(self, options=None):
        """
        set output options
        >>> set_output(options)
        retuns true if all options set correctly
        """
        if options:
            # set output directory
            if 'output_dir' in options:
                self.info['path'] = options['output_dir']

            # set image name
            if 'output_image_name' in options:
                self.info['filename'] = options['output_image_name']

    def __capture(self):
        """
        start timelapse
        >>> start()
        """
        try:
            self.__all_clear()
            c_img = self.__schedule['current_image']
            t_img = self.__schedule['total_images']

            # check if images still needing to be taken
            if c_img < t_img:
                # cue up next image
                # TODO: place this thread in a single queue
                #
                run_at(
                    self.__capture,
                    None,
                    self.__schedule['interval'])

            c_img_name = '{0}/{1}_{2:05d}.jpg'.format(
                self.__schedule['current_image_dir'],
                self.info['filename'],
                self.__schedule['current_image']
            )

            # take the current image
            camera = PiCamera()
            setup_camera(camera, self.__camera_options)
            camera.capture(c_img_name)
            camera.close()

            print 'Taken image {}/{}'.format(c_img + 1, t_img)

            try:
                os.symlink(c_img_name, '{}/latest.jpg'.format(
                    self.__schedule['current_image_dir']))
            except Exception as err:
                raise err
            else:
                print 'unable to create symlink'

            # check if images still needing to be taken
            if c_img < t_img:
                self.__schedule['current_image'] += 1
            else:
                # make this a "cleanup schedule action"
                self.__schedule['current_image'] = 0
                # run finishing up actions
                self.__finish_capture()

        # catch out of camera resources error
        except PiCameraMMALError:
            if self.__schedule['interval'] <= 60:
                incr = self.__schedule['interval']
            else:
                incr = 30

            print 'PiCameraMMALError: increasing interval to {}'.format(incr)
            self.__schedule['interval'] += incr

        except KeyboardInterrupt:
            # TODO: Need to remove thread on exit
            print '\nTime-lapse capture cancelled.\n'
            sys.exit()

    def __finish_capture(self):
        print '\nCapture finished\n'
        # loop through exports
        # TODO: add to a queue
        for export in self.__exports:
            print 'exporting {}'.format(export.__class__.__name__)
            export.create()

        if not self.__ran['count']:
            self.__ran['count'] = 0

        if not self.__ran['first']:
            self.__ran['first'] = self.__schedule['start']

        self.__ran['last'] = self.__schedule['start']

        self.__ran['count'] += 0

        if self.__schedule['repeat'] > 0:
            repeat = timedelta(
                days=self.__schedule['repeat'],
                microseconds=-100)
            # schedule repeat
            self.__schedule['start'] += repeat
            self.__schedule['end'] += repeat
            # setup output
            new_times = {
                'start_time': self.__schedule['start'],
                'end_time': self.__schedule['end']
            }

            if self.__schedule['repeat']:
                new_times['repeat'] = self.__schedule['repeat']

            self.setup('timings', )
            # schedule run time
            run_at(
                self.start,
                self.__schedule['start'])
        else:
            print 'Time-lapse capture complete!'
            sys.exit()

    #################################################
    # PUBLIC

    def setup(self, subject, options=None):
        print 'setting up: {}'.format(subject)
        if subject == 'camera':
            self.__camera_options = options

        if subject == 'timings':
            self.__setup_timings(options)

        if subject == 'output':
            self.__setup_output(options)

    def setup_export(self, export_type, options=None):
        """
        set export options
        >>> setup_export(options)
        retuns true if all options set correctly
        """
        if export_type == 'gif':
            # check if any default values have been overwritten
            if options:
                new_gif = self.Gif(options)
            else:
                new_gif = self.Gif()

            self.__add_export(new_gif)

        elif export_type == 'video':
            # check if any default values have been overwritten
            if options:
                # ('mp4_name', 'mp4_output_dir', 'mp4_flags')
                new_video = self.Video(options)
            else:
                new_video = self.Video()

            self.__add_export(new_video)

        elif export_type == 'email':
            # check if any default values have been overwritten
            if ('address' and 'password') in options:

                if options['send_gif']:
                    new_email = self.Email(options)
                    self.__add_export(new_email)

            else:
                raise AttributeError(
                    'missing email configuirations. \nPlease update config.yml or supply options')

    def start(self):
        """
        starts timelapse capture
        """
        self.__all_clear()
        self.__create_current_dir()
        self.__schedule['current_image'] = 0
        self.__pretty_print_info()
        run_at(
            self.__capture,
            self.__schedule['start'])

    def stop(self, exit=True):
        """
        stop timelapse
        Sends out signal to stop all timelapse
        methods gracefully
        >>> stop()
        """
        # rename directory
        os.rename(
            self.__schedule['current_image_dir'],
            '_' + self.__schedule['current_image_dir']
        )
        # close thread
        print 'Time-lapse {} stopping!'.format(self.name)
        if exit:
            sys.exit()

    def restart(self):
        """
        Stops timelapse gracefully, cleans up and
        restarts timelapse.
        >>> restart()
        """
        self.stop(False)
        print 'Time-lapse {} restarting'.format(self.name)
        self.start()