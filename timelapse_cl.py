# from picamera import PiCamera
import errno
import os
import re
import sys
import threading
import Queue
from datetime import datetime, timedelta
from time import sleep
import yaml


def dev_stub(s_time=2):
    # dev
    print 'dev sleep {} sec'.format(s_time)
    sleep(s_time)


class Timelapse(object):

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

            if options != None:
                # set name
                if 'name' in options:
                    self.name = options['name']
                if 'output_dir' in options:
                    self.output = options['output_dir']


        def __create_dir(self, dir):
            if (self.name and self.output) != None:
                os.path.join(sys.path[0], folder, name)
                try:
                    os.makedirs(dir)
                except OSError as e:
                    if e.errno != errno.EEXIST:
                        raise


        def setup_output(self, options):
            """
            set output options
            >>> setup_output(options)
            retuns true if all options set correctly
            """


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
            if options != None:
                if 'flags' in options:
                    self.flags = options['flags']
                if 'gif_encode_base64' in options:
                    self.base64 = options['gif_encode_base64']


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


    #################################################
    #################################################
    #################################################


    class Email(Export):
        """
        class for timelapse Gif creation and exporting
        """

        export_type = None
        attrs = {}

        def __init__(self, timelapse, type, options=None):
            super(timelapse.Video, self).__init__(timelapse, options)

            self.export_type = type

            if options:
                try:
                    self.setup(options)
                except AttributeError,e:
                    print 'Invalid attributes. Email not setup, please try again'


        def setup(self, options):

            req = ['address', 'password', 'to_address']

            for k in req:
                if k in options:
                    self.attrs[k] = options[k]

            if any(k not in self.attrs for k in req):
               raise AttributeError(
                "please supply an 'address', 'password' and 'to_address")


    #################################################
    #################################################
    #################################################

    name = None
    mode = None
    interval = None

    run_first = None
    run_last = None
    run_count = None

    camera = None
    image_dir = None
    image_count = None
    
    exports = None


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
        else:
            self.name = 'series'
        
        # set output directory
        if 'output_dir' in config:
            self.image_dir = config['output_dir']
        else:
            self.image_dir = '/home/pi/pi-timelapse/'

        # set image name
        if 'output_image_name' in config:
            self.image_filename = config['output_image_name']
        else:
            self.image_filename = 'image'

        if config['create_gif'] == True:
            if config['gif'] != {}:
                self.setup_export('gif', config['gif'])
            else: self.setup_export('gif')

        if config['create_video'] == True:
            if config['video'] != {}:
                self.setup_export('video', config['video'])
            else: self.setup_export('video')

        if config['export_email'] == True and config['email'] != {}:
            print 'setting up email export'
            self.setup_export('email', config['email'])

        self.__pretty_print_info()

                
    def __valid_filename(self, string):
        """
        Return the given string converted to a string that can be used for a clean
        filename. Remove leading and trailing spaces; convert other spaces to
        underscores; and remove anything that is not an alphanumeric, dash,
        underscore, or dot.
        >>> __valid_filename("i hope my plants are ok.jpg")
        'i_hope_my_plants_are_ok.jpg'
        """
        s = str(s).strip().replace(' ', '_')
        return re.sub(r'(?u)[^-\w.]', '', s)


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
        msg += "Mode: {0} | Interval: {1}s | Image Count: {2}\n"
        msg += "Output Dir: {3}\n"
        msg += "Last Run: {4}\n"
        
        msg = msg.format(
            self.mode, self.interval, self.image_count,
            self.image_dir , self.run_last
        )

        for x in self.exports:
            x_info = "\nExport --------------------------------------\n"
            x_info += "Type: {0} | Name: {1}\n"
            
            x_info = x_info.format(x.__class__.__name__, x.name)
            msg += x_info

        msg = msg + "\n============================================="

        print msg        


    def __with_wait_animation(method, method_args=(), msg='working', sec=0.5):
        """
        Adds a wait animation to a long running method.
        >>> __with_wait_animation(encode, ('gif'), 'encoding', 0.5)
        encoding............
        """
        s = '.'
        t = threading.Thread(target=method, args=method_args)
        t.start()
        sys.stdout.write( msg )
        while t.is_alive():
            sys.stdout.write( s )
            sys.stdout.flush()
            sleep(sec)


    def __add_export(self, export):
        if self.exports == None:
            self.exports = []
        self.exports.append( export )


    def setup_camera(self, options):
        """
        set camera options.
        >>> setup_camera(options)
        retuns true if all options set correctly
        """
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

        self.camera = camera


    def setup_output(self, options):
        """
        set output options
        >>> setup_output(options)
        retuns true if all options set correctly
        """


    def setup_export(self, type, options=None):
        """
        set export options
        >>> setup_export(options)
        retuns true if all options set correctly
        """
        if type == 'gif':
            # check if any default values have been overwritten
            if options and any(k in options for k in ('gif_name', 'gif_output_dir', 'gif_flags')):
                dev_stub()
            else:
                # self.exports['gif'] = new Gif()
                new_gif = self.Gif(self)
                self.__add_export(new_gif)

        elif type == 'video':
            # check if any default values have been overwritten
            if options and any(k in options for k in (
                'mp4_name', 'mp4_output_dir', 'mp4_flags')):
                dev_stub()
            else:
                # self.exports['video'] = new Video()
                new_video = self.Video(self)
                self.__add_export(new_video)

        elif type == 'email':
            # check if any default values have been overwritten
            if all(k in options for k in (
                'address', 'password')):
                dev_stub()
            else:
                raise AttributeError(
                    'missing email configuirations. \nPlease update config.yml or supply options')


    def start(self):
        """
        start timelapse
        >>> start()
        """
            # if camera setup
            # if timings setup
            # if output setup


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

# /home/pi/pi-timelapse/<timelapse_name>/date_time/*{.jpg,.mp4,.gif}


tl = Timelapse( 'plane-test' )

