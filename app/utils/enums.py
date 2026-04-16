from enum import Enum


class DataFileSource(str, Enum):
    PRIVATE_SUPPLIERS = "private_suppliers"
    SWITCHING_REQUESTS = "switching_requests"
    CONNECTED_FACILITIES = "connected_facilities"
    DISTRIBUTOR_RESPONSES = "distributor_responses"
    IMS_HEAT_LOAD_WEATHER = "ims_heat_load_weather"
