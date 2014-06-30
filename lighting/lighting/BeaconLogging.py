import logging, logging.handlers
import sys, traceback

# To do - proper override of logging

class BeaconLogging:
        
    system = None
    module = None
    logFile = None
    fileLevel = None
    consoleLevel = None
    logger = None
    loggerName = None
    errorCallback = None
    errorCount = 0 
    
    def __init__(self, system, module, filename, fileLevel=logging.DEBUG, consoleLevel=logging.DEBUG, errorCallback=None):
        self.system = system
        self.module = module
        self.logFile = filename
        self.fileLevel = fileLevel
        self.consoleLevel = consoleLevel
        self.errorCallback = errorCallback        
        self.setup()
    
    def setup(self):
        #log to file
        self.loggerName = "%s.%s" % (self.system, self.module)
        self.logger = logging.getLogger(self.loggerName)
        logging.basicConfig(
                     format='%(asctime)s %(levelname)s\t%(message)s',
                     datefmt='%y-%m-%d %H%M',
                     level=logging.DEBUG,
                     filename='/dev/null', filemode='a')  # hack?
        if (self.fileLevel!=None):
            fileh = logging.handlers.RotatingFileHandler(self.logFile,'a',10485760,10)
            formatter = logging.Formatter('%(asctime)s %(levelname)s\t%(message)s')
            fileh.setFormatter(formatter)
            fileh.setLevel(self.fileLevel)
            self.logger.addHandler(fileh)
            
        # log to console
        if (self.consoleLevel!=None):
            console = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s %(levelname)s\t%(message)s')
            console.setFormatter(formatter)
            console.setLevel(self.consoleLevel)
            self.logger.addHandler(console)
        
    def log(self, level, routine, message, exception=None, stacktrace=False, noCount=False):        
        tb = ""
        excstr = ""
        if (exception!=None):
            excinfo = sys.exc_info()
            excstr = "\n\t\t\t\t%s: %s" % (excinfo[0].__name__, str(excinfo[1]).rstrip())
            stacktrace = True   # for now, always stack trace on exceptions
            S = traceback.extract_tb(excinfo[2])
        elif (stacktrace):
            S = traceback.extract_stack()        
        if (stacktrace):
            for i in range(0, len(S)):
                tb = tb + "\n\t\t\t\tLine %d of '%s' in %s: %s" % (S[i][1], S[i][2], S[i][0], str(S[i][3]).rstrip())                 
        self.logger.log(level, "[%s.%s] %s %s %s" % ( self.module, routine, message, excstr, tb ) )      
        if (level > logging.WARNING): 
            self.errorCount = self.errorCount+1
            if (self.errorCallback != None) and (noCount==False):   #noCount prevents recursion
                self.errorCallback.incrError(self.module, self.errorCount, "Last error logged from [%s.%s]" % ( self.module, routine ))
    
    def addErrorCallback(self, callback):
        self.errorCallback = callback
        self.errorCallback.incrError(self.module, self.errorCount, "")
    