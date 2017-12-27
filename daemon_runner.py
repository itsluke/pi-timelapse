from daemon import Daemon
from timelapse import Timelapse

class MyDaemon(Daemon):
    daemonised_process = None
    def start(self):
        # Or simply merge your code with MyDaemon.
        daemonised_process = Timelapse('growwLight', 'config.yml')
        daemonised_process.start()

    def stop(self):
        daemonised_process.stop()
        daemonised_process = None

    def restart(self):
        daemonised_process.stop()
        daemonised_process.start()


if __name__ == "__main__":
    daemon = MyDaemon('/tmp/daemon-example.pid')
    if len(sys.argv) == 2:
        if 'start' == sys.argv[1]:
            daemon.start()
        elif 'stop' == sys.argv[1]:
            daemon.stop()
        elif 'restart' == sys.argv[1]:
            daemon.restart()
        else:
            print "Unknown command"
            sys.exit(2)
        sys.exit(0)
    else:
        print "usage: %s start|stop|restart" % sys.argv[0]
        sys.exit(2)