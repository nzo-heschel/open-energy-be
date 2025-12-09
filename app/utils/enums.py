from enum import Enum


class DataFileSource(str, Enum):
    PRIVATE_SUPPLIERS = "private_suppliers"
    SWITCHING_REQUESTS = "switching_requests"
