import errno
import os
import re
import sys
import threading
import Queue
from datetime import datetime, timedelta
from time import sleep
import yaml

# from picamera import PiCamera

#################################################
#################################################
#################################################


def __with_wait_animation(
        method,
        method_args=(),
        msg='working',
        sec=0.5):
    """
    Adds a wait animation to a long running method.
    >>> __with_wait_animation(encode, ('gif'), 'encoding', 0.5)
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


def __valid_filename(string):
    """
    Return the given string converted to a string that can be used for a clean
    filename. Remove leading and trailing spaces; convert other spaces to
    underscores; and remove anything that is not an alphanumeric, dash,
    underscore, or dot.
    >>> __valid_filename("i hope my plants are ok.jpg")
    'i_hope_my_plants_are_ok.jpg'
    """
    string = str(string).strip().replace(' ', '_')
    return re.sub(r'(?u)[^-\w.]', '', string)


class Timelapse(object):
    """Creates a new timelapse to be run on the pi"""
    LOCAL_DEV = True

    #################################################
    #################################################
    #################################################

    class Export(object):
        """
        class for timelapse Gif creation and exporting
        """

        timelapse = None

        name = None
        output_dir = None
        folder = None
        latest = None
        last_run = None
        count = None

        """docstring for Export"""

        def __init__(self, timelapse, options=None):
            super(timelapse.Export, self).__init__()
            self.timelapse = timelapse

            if options is not None:
                # set name
                if 'name' in options:
                    self.name = options['name']
                if 'output_dir' in options:
                    self.output = options['output_dir']

        def set_output(self, options):
            """
            set output options
            >>> set_output(options)
            retuns true if all options set correctly
            """

        def create(self):
            # create export
            print 'DEV waiting'
            sleep(1)
            __with_wait_animation(self.run)


        def run(self):
            print 'no export function availible for {}'.format(self.__class__.__name__)


    #################################################
    #################################################
    #################################################

    class Gif(Export):
        """
        class for timelapse Gif creation and exporting
        """

        name = 'timelapse.gif'

        def __init__(self, timelapse, options=None):
            super(timelapse.Gif, self).__init__(timelapse, options)
            if options is not None:
                if 'flags' in options:
                    self.flags = options['flags']
                if 'gif_encode_base64' in options:
                    self.base64 = options['gif_encode_base64']

        def run(self):
            # create export
            print 'DEV waiting {}'.format(self.name)
            sleep(1)

    #################################################
    #################################################
    #################################################

    class Video(Export):
        """
        class for timelapse Gif creation and exporting
        """

        name = 'timelapse.mp4'

        def __init__(self, timelapse, options=None):
            super(timelapse.Video, self).__init__(timelapse, options)

        def run(self):
            # create export
            print 'DEV waiting {}'.format(self.name)
            sleep(1)

    #################################################
    #################################################
    #################################################

    class Email(Export):
        """
        class for timelapse Gif creation and exporting
        """

        export_type = None
        attrs = {}

        def __init__(self, timelapse, export_type, options=None):
            super(timelapse.Video, self).__init__(timelapse, options)

            self.export_type = export_type

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

        def run(self):
            # create export
            print 'DEV waiting {}'.format(self.name)
            sleep(1)

            # any specific attributes

            # wrap this function in 'loader'

    #################################################
    #################################################
    #################################################

    name = 'series'
    image_dir = '/home/pi/pi-timelapse/'
    image_filename = 'image'

    run_first = None
    run_last = None
    run_count = None

    __schedule = {
        'type': None,
        'start': None,
        'end': None,
        'interval': None,
        'total_images': None,
        'current_image': None,
        'current_image_dir': None
    }

    __date_str = '%Y-%m-%d'
    __time_str = '%H_%M'
    __d_t_str = '{}_{}'.format(__date_str, __time_str)

    __camera = None
    __exports = None

    def __init__(self, name=None, config_path='config.yml'):
        """
        init class with a name for timelapse
        e.g. fish-monitor
        optionaly pass a config .yml file
        """
        super(Timelapse, self).__init__()

        # load yml config
        config = yaml.safe_load(
            open(os.path.join(sys.path[0], config_path)))

        # set name
        if name:
            self.name = name
        elif 'series_name' in config:
            self.name = config['series_name']

        # setup output
        self.set('timings', config)

        # setup output
        self.set('output', config)

        # setup output
        self.set('camera', config)

        # setup gif export
        if config['create_gif']:
            if config['gif'] != {}:
                self.setup_export('gif', config['gif'])
            else:
                self.setup_export('gif')

        # setup video export
        if config['create_video']:
            if config['video'] != {}:
                self.setup_export('video', config['video'])
            else:
                self.setup_export('video')

        # setup email export
        if config['export_email'] and config['email'] != {}:
            print 'setting up email export'
            self.setup_export('email', config['email'])

        self.__pretty_print_info()


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
        msg = "=============== timelapse.py ================\n\n"
        msg += "Type: {0} | Interval: {1}s | Image Count: {2}\n"
        msg += "Output Dir: {3}\n"
        msg += "Last Run: {4}\n"

        msg = msg.format(
            self.__schedule['type'],
            self.__schedule['interval'],
            self.__schedule['total_images'],
            self.image_dir,
            self.run_last
        )

        for ex in self.__exports:
            info = "\nExport --------------------------------------\n"
            info += "Type: {0} | Name: {1}\n"

            info = info.format(ex.__class__.__name__, ex.name)
            msg += info

        msg = msg + "\n============================================="

        print msg

    def __add_export(self, export):
        if self.__exports is None:
            self.__exports = []
        self.__exports.append(export)

    def __create_current_dir(self):
        if not self.image_dir:
            self.image_dir = '/home/pi/pi-timelapse/'
        if not self.name:
            self.name = 'series'

        current_dir = os.path.join(
            self.image_dir, 
            self.name,
            self.__schedule['start_time'].strftime(self.__d_t_str)
            )

        try:
            os.makedirs(current_dir)
        except OSError as err:
            if err.errno != errno.EEXIST:
                raise

    def __all_clear(self):
        if self.__camera is None:
            raise Exception("Camera is not setup. Please re-run '.set_camera'")

        if self.image_dir is None:
            raise Exception("Output is not setup. Please re-run '.set_output'")

        if self.__schedule['current_image_dir'] is None:
            # create current image dir
            self.__create_current_dir()

    def __take_image(self):
        self.__all_clear()
        try:
            self.__camera.capture(
                self.__schedule['current_image_dir'] +
                self.image_filename + '{0:05d}.jpg'.format(self.__schedule['current_image'])
            )
            self.__schedule['current_image'] += 1
        # else:
        #     sleep(1)
            print 'Camera capture did not complete'
        finally:
            self.__camera.close()

    def __setup_camera(self, options=None):
        """
        sets any custom options and returns the camera
        >>> set_camera(options)
        """
        if self.LOCAL_DEV:
            return None

        camera = PiCamera()

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

        self.__camera = camera

    def __setup_timings(self, options):
        """
        set timing options
        >>> set_timings(options)
        """
        now = datetime.now()
        now_date_str = now.strftime(self.__date_str)
        if 'start_time' in options:
            start = datetime.strptime('{} {}'.format(
                now_date_str, 
                options['start_time']
            ), self.__d_t_str)
        else:
            start = now

        self.__schedule['start_time'] = start

    def __setup_output(self, options=None):
        """
        set output options
        >>> set_output(options)
        retuns true if all options set correctly
        """
        if options:
            # set output directory
            if 'output_dir' in options:
                self.image_dir = options['output_dir']

            # set image name
            if 'output_image_name' in options:
                self.image_filename = options['output_image_name']

    #################################################
    # PUBLIC

    def set(self, type, options=None):
        if type == 'camera':
            self.__setup_camera(options)

        if type == 'timings':
            self.__setup_timings(options)

        if type == 'output':
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
                print 'DEV waiting'
                sleep(1)
            else:
                new_gif = self.Gif(self)
                self.__add_export(new_gif)

        elif export_type == 'video':
            # check if any default values have been overwritten
            if options:
                # ('mp4_name', 'mp4_output_dir', 'mp4_flags')
                print 'DEV waiting'
                sleep(1)
            else:
                new_video = self.Video(self)
                self.__add_export(new_video)

        elif export_type == 'email':
            # check if any default values have been overwritten
            if ('address' and 'password') in options:
                print 'DEV waiting'
                sleep(1)
            else:
                raise AttributeError(
                    'missing email configuirations. \nPlease update config.yml or supply options')

    def __capture(self):
        """
        start timelapse
        >>> start()
        """
        try:
            self.__all_clear()
            c_img = self.__schedule['current_image']
            t_img = self.__schedule['total_images'] - 1

            # check if images still needing to be taken
            if c_img < t_img:
                # cue up next image
                # TODO:
                # place this thread in a single queue
                threading.Timer(self.__schedule['interval'], self.__capture).start()
                # take the current image
                self.__take_image()
            else:
                # make this a "cleanup schedule action"
                self.__schedule['current_image'] = 0
                # run finishing up actions

        except KeyboardInterrupt as SystemExit:
            # TODO:
            # Need to remove thread from ""
            print '\nTime-lapse capture cancelled.\n'

    def start(self):
        """
        starts timelapse capture
        """
        # check todays dir
        self.__create_current_dir()
        # reset current image number

        self.__schedule['current_image'] = 0
        self.__capture()

    def stop(self):
        """
        stop timelapse
        Sends out signal to stop all timelapse
        methods gracefully
        >>> stop()
        """

    def restart(self):
        """
        Stops timelapse gracefully, cleans up and
        restarts timelapse.
        >>> restart()
        """

    def export(self):
        """
        exports timelapse to various formats
        >>> export(export_type)
        returns file path for exported timelapse
        """

    def get_video(self):
        """
        >>> video()
        returns path to latest video.
        """

    def get_gif(self):
        """
        >>> gif()
        returns path to latest gif.
        """

    def email(self):
        """
        email timelapse
        >>> email(email_address(s), export_type)
        returns file path for exported timelapse
        """

my_timelapse = Timelapse('plane-test')
