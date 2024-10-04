import logging


class ExcludeSpecificLogMessageFilter(logging.Filter):
    def filter(self, record):
        # Check if the log message is the specific one you want to exclude
        return 'GET /notifications/' not in record.getMessage()