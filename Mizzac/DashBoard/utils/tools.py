import logging, os

from logging.handlers import RotatingFileHandler

class Logger:
    """
    Logger class for creating modular logs with the Python logging module.
    """
    
    # Define the log directory
    log_dir = "data/logs/"

    def __init__(self):
        """
        Initialize the Logger instance, setting up the default log directory.
        """
        
        # Create the log directory if it does not exist
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

    def log(self, level, message, log_file="server.log", filename=None):
        """
        Log a message with the given level into a specified log file.

        Parameters:
            level: 
                Level of the log. Can be DEBUG, INFO, WARNING, ERROR, CRITICAL.
            message: 
                Log message string.
            log_file: 
                Name of the log file.
            filename: 
                Name of the file where the log is being written from.
                In the case where you don't want to use the correct filename in log.
        """

        if not isinstance(level, int):
            raise ValueError(f"Log level must be an integer, not {type(level)}.")

        if not logging.getLevelName(level) in logging._nameToLevel:
            raise ValueError(f"Invalid log level: {level}")

        # Configure logger to write to the specified log file
        logger = logging.getLogger(log_file)

        # Avoid adding multiple handlers to the same logger
        if not logger.hasHandlers():
            # Set to the lowest level to capture all messages
            logger.setLevel(logging.DEBUG)  
            # Create log_path with log_dir and log_file
            log_path = os.path.join(self.log_dir, log_file)

            # Create a handler for writing log messages to a file
            handler = RotatingFileHandler(
                log_path,
                maxBytes=5242880,  # 5MB
                backupCount=5
            )

            # Create a formatter that includes time, level, filename and message
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - [%(filename)s] - %(message)s', 
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        # Add filename information if not provided
        if filename is None:
            # Extracts filename where logging was called
            filename = os.path.basename(logging.Logger.manager.loggerDict[log_file].findCaller()[0])

        # Log the message
        logger.log(level, f'[{filename}] - {message}')