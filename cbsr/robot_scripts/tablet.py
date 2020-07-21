from os import system
from threading import Thread

PAN_CENTER = 0.0
FULL_VOLUME = 1.0


class Tablet(object):
    """
    Tablet module to communicate with Pepper's tablet.
    Only used as an import.
    """

    def __init__(self, session, server_ip, server_port=8000):
        self.server_ip = server_ip
        self.server_port = server_port
        self.service = session.service('ALTabletService')
        self.service.resetTablet()
        self.service.enableWifi()

        self._audio = session.service('ALAudioPlayer')
        self._audio.stopAll()
        self._audio_thread = None
        self._audio.setPanorama(PAN_CENTER)
        self.set_volume(FULL_VOLUME)

    def _play_audio_thread(self, url):
        try:
            self._audio.playWebStream(url, self._audio.getMasterVolume(), PAN_CENTER)
        except RuntimeError:
            print('Invalid url: ' + url)

    @staticmethod
    def settings():
        """Open the tablet settings GUI"""
        # There is no API call for this so the qicli utility has to be used
        # directly.
        system('qicli call ALTabletService._openSettings')

    def url_for(self, resource, res_type):
        """Create a URL for a static resource"""
        if not resource.startswith('https'):
            resource = 'https://{}:{}/{}/{}'.format(self.server_ip, self.server_port, res_type, resource)
        return resource

    def set_volume(self, value):
        """Set the tablet's master volume"""
        if not 0 <= value <= 1:
            raise ValueError('Volume must be between 0 and 100%')
        self._audio.setMasterVolume(value)

    def audio_is_playing(self):
        """Check if there is audio playing"""
        try:
            return self._audio_thread.is_alive()
        except AttributeError:
            return self._audio_thread is not None

    def play_audio(self, url):
        """Play audio through the robot's speakers"""
        if not self.audio_is_playing():
            url = self.url_for(url, 'audio')
            self._audio_thread = Thread(target=self._play_audio_thread, args=(url,))
            self._audio_thread.daemon = True
            self._audio_thread.start()

    def stop_audio(self):
        """Stop any currently playing audio"""
        if self.audio_is_playing():
            self._audio.stopAll()
            self._audio_thread.join()
            self._audio_thread = None

    def open_url(self, url=''):
        """
        Show the browser and load the supplied URL. If no URL is passed to
        the function, the last shown URL is loaded.
        """
        if not url:
            self.service.showWebview()
        else:
            self.service.showWebview(url)

    def show_image(self, url, bg_color='#FFFFFF'):
        """Load an image from a given URL"""
        if not url:
            print('Image URL cannot be empty')
        else:
            url = self.url_for(url, 'img')
            self.service.setBackgroundColor(bg_color)
            self.service.showImage(url)
            print('Showing ', url)

    def play_video(self, url):
        """Play video on the tablet"""
        if not url:
            print('Video URL cannot be empty')
        else:
            url = self.url_for(url, 'video')
            self.service.playVideo(url)
            print('Playing ', url)

    def reload(self):
        """Reload the current page"""
        # 'True' means to bypass local cache
        self.service.reloadPage(True)

    def hide(self):
        """Hide the web browser"""
        self.service.hide()
        print('Hiding view')
