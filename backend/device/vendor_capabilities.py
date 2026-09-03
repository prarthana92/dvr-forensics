VENDOR_CAPABILITIES = {

    "HIKVISION": {
        "driver": "hikvision",
        "primary_protocol": "HCNetSDK",
        "fallback_protocol": "ONVIF",
        "live_stream": "RTSP",
        "historical_playback": "HCNetSDK",
        "event_ingest": "HTTP / SDK",
        "cloud_p2p": True,
    },

    "DAHUA": {
        "driver": "dahua",
        "primary_protocol": "NetSDK",
        "fallback_protocol": "ONVIF",
        "live_stream": "RTSP",
        "historical_playback": "NetSDK",
        "event_ingest": "HTTP / SDK",
        "cloud_p2p": True,
    },

    "CP_PLUS": {
        "driver": "dahua",
        "primary_protocol": "NetSDK-compatible / model-dependent",
        "fallback_protocol": "ONVIF",
        "live_stream": "RTSP",
        "historical_playback": "Model-dependent",
        "event_ingest": "Model-dependent",
        "cloud_p2p": True,
    },

    "UNIVIEW": {
        "driver": "onvif",
        "primary_protocol": "ONVIF",
        "fallback_protocol": "RTSP",
        "live_stream": "RTSP",
        "historical_playback": "ONVIF Profile G / model-dependent",
        "event_ingest": "ONVIF Events / model-dependent",
        "cloud_p2p": True,
    },

    "MATRIX": {
        "driver": "onvif",
        "primary_protocol": "ONVIF / REST",
        "fallback_protocol": "RTSP",
        "live_stream": "RTSP",
        "historical_playback": "ONVIF / model-dependent",
        "event_ingest": "REST / ONVIF",
        "cloud_p2p": False,
    },

    "HONEYWELL": {
        "driver": "onvif",
        "primary_protocol": "Model-dependent",
        "fallback_protocol": "ONVIF",
        "live_stream": "RTSP",
        "historical_playback": "Model-dependent",
        "event_ingest": "Model-dependent",
        "cloud_p2p": True,
    },

    "TP_LINK": {
        "driver": "onvif",
        "primary_protocol": "ONVIF",
        "fallback_protocol": "RTSP",
        "live_stream": "RTSP",
        "historical_playback": "Model-dependent",
        "event_ingest": "ONVIF / polling",
        "cloud_p2p": True,
    },

    "GODREJ": {
        "driver": "onvif",
        "primary_protocol": "ONVIF",
        "fallback_protocol": "RTSP",
        "live_stream": "RTSP",
        "historical_playback": "Model-dependent",
        "event_ingest": "ONVIF / polling",
        "cloud_p2p": True,
    },
}


SUPPORTED_VENDORS = list(VENDOR_CAPABILITIES.keys())


def get_vendor_capabilities(vendor):
    """
    Return capability information for a vendor.
    """
    return VENDOR_CAPABILITIES.get(vendor)


def is_supported_vendor(vendor):
    """
    Check whether TraceX supports the vendor.
    """
    return vendor in VENDOR_CAPABILITIES
if __name__ == "__main__":
    print("vendor_capabilities.py loaded successfully")