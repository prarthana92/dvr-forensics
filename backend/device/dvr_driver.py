from abc import ABC, abstractmethod


class DVRDriver(ABC):
    """
    Common interface for all DVR/NVR vendors.

    Every vendor driver in TraceX should follow this interface.
    """

    vendor_name = "UNKNOWN"

    def __init__(self, host, username=None, password=None, port=None):
        self.host = host
        self.username = username
        self.password = password
        self.port = port

    @abstractmethod
    def connect(self):
        """
        Establish connection with the DVR/NVR.
        """
        pass

    @abstractmethod
    def disconnect(self):
        """
        Close the connection with the DVR/NVR.
        """
        pass

    @abstractmethod
    def get_device_info(self):
        """
        Return basic device information.
        """
        pass

    @abstractmethod
    def get_live_stream_url(self, channel):
        """
        Return the RTSP/live-stream URL for a channel.
        """
        pass

    def get_recordings(self, channel, start_time, end_time):
        """
        Find historical recordings.

        Not every vendor/protocol supports this in the same way,
        so the default implementation reports that it is unsupported.
        """
        return {
            "supported": False,
            "vendor": self.vendor_name,
            "message": "Historical playback is not implemented by this driver."
        }

    def download_recording(self, recording):
        """
        Download/export a historical recording.

        Vendor-specific drivers can override this.
        """
        return {
            "supported": False,
            "vendor": self.vendor_name,
            "message": "Recording download is not implemented by this driver."
        }

    def get_events(self, start_time, end_time):
        """
        Retrieve device events/alerts.
        """
        return {
            "supported": False,
            "vendor": self.vendor_name,
            "message": "Event retrieval is not implemented by this driver."
        }

    def capabilities(self):
        """
        Describe what this driver supports.
        """
        return {
            "vendor": self.vendor_name,
            "live_stream": True,
            "historical_playback": False,
            "recording_download": False,
            "events": False,
            "ptz": False,
            "onvif": False,
            "proprietary_sdk": False
        }
    if __name__ == "__main__":
     print("dvr_driver.py loaded successfully")