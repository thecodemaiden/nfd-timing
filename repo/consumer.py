#!/usr/bin/python

from pyndn import Name, ThreadsafeFace, Interest, Data, Exclude
import time
import sys
import re
from numpy import mean

try:
    import asyncio
except ImportError:
    import trollius as asyncio

import logging
from ConfigParser import RawConfigParser


class InterestTimer:
    """
        This encapsulates the express-data/timeout path for one interest
        for better timing
    """
    def __init__(self, face, interest):
        self.startTime = None
        self.endTime = None
        self.interest = Interest(interest)
        self.face = face
        self.didTimeout = False
        
    def onDataReceived(self, interest, data):
        self.endTime = time.clock()

    def onTimeout(self, interest):
        self.didTimeout = True

    @asyncio.coroutine
    def submit(self):
        self.face.expressInterest(self.interest, onDataReceived, onTimeout)
        self.startTime = time.clock()
        raise Return()

class RepoConsumer:
    TIMEOUT = 100
    def __init__(self, dataPrefix, interestLifetime=100, lastVersion=None, start=True):
        self.prefix = Name(dataPrefix)
        
        #used in the exclude to make sure we get new data only
        self.lastVersion = lastVersion

        self.face = None
        self.dataFormat = re.compile("\((\d+\.?\d*)\)") # data should start with a timestamp in 
        logFormat = '%(asctime)-10s %(message)s'
        self.logger = logging.getLogger('RepoConsumer')
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(logging.StreamHandler())
        fh = logging.FileHandler('repo_consumer.log', mode='w')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(logFormat))
        self.logger.addHandler(fh)
        self.createTiming = []
        self.receiveTiming = []
        self.timeouts = 0
        self.notReady = 0

        self.lastReceivedTime = 0
        self.lastCreatedTime = 0
        self.backoffCounter = 0
        
        self.interestLifetime = interestLifetime

        self.nextIssue = None
        self.loop = None

        self.isCancelled = False

    def start(self):
        self.loop =  asyncio.get_event_loop()
        self.face = ThreadsafeFace(self.loop, "")
        self.face.stopWhen(lambda:self.isCancelled)
        self.reissueInterest()
        self.loop.run_forever()

    def stop(self):
        self.loop.close()
        self.face.shutdown()
        self.loop = None
        self.face = None

    def onData(self, interest, data):
        now = time.time()
        # for now, assume there is a version appended to the interest
        nameLength = interest.getName().size()
        dataStr = data.getContent().toRawStr()
        try:
            lastComponent = data.getName().get(-1).toEscapedString()
            if str(lastComponent) == 'MISSING':
                self.notReady += 1
                #self.backoffCounter += 1
                logger.info('repo not ready')
                self.reissueInterest()
                return

            self.lastVersion = data.getName().get(nameLength)
            self.logger.debug(interest.getName().toUri() + ": version " + self.lastVersion.toEscapedString())
            match = self.dataFormat.match(data.getContent().toRawStr())
            ts = float(match.group(1))
            if self.lastReceivedTime != 0 and self.lastCreatedTime != 0:
                self.createTiming.append(now-self.lastReceivedTime)
                self.receiveTiming.append(now-self.lastCreatedTime)

            self.lastReceivedTime = now
            self.lastCreatedTime = ts
            self.logger.debug("Created: " + str(ts) +  ", received: " + str(now))
        except Exception as  e:
            self.logger.exception(str(e))
        #self.backoffCounter -= 1
        self.reissueInterest()

    def onTimeout(self, interest):
        self.logger.debug("timeout")
        self.timeouts += 1
        #self.backoffCounter += 1
        self.reissueInterest()

    def reissueInterest(self):
        BACKOFF_THRESHOLD = 10
        if self.backoffCounter > BACKOFF_THRESHOLD:
            self.TIMEOUT += 50
            self.backoffCounter = 0
            self.logger.debug('Backing off interval to ' + str(self.TIMEOUT))
        if self.backoffCounter < -BACKOFF_THRESHOLD:
            self.TIMEOUT -= 50
            self.backoffCounter = 0
            self.logger.debug('Reducing backoff interval to ' + str(self.TIMEOUT))
        if self.nextIssue is not None:
            now = time.clock()
            if self.nextIssue > now:
                pass
               # time.sleep(self.nextIssue-now)
        interest = Interest(Name(self.prefix))
        interest.setInterestLifetimeMilliseconds(self.interestLifetime)
        interest.setMustBeFresh(False)
        if self.lastVersion is not None:
            e = Exclude()
            e.appendAny()
            e.appendComponent(self.lastVersion)
            interest.setExclude(e)
        interest.setChildSelector(1) #rightmost == freshest
        self.face.expressInterest(interest, self.onData, self.onTimeout)
        self.nextIssue = time.clock()+self.TIMEOUT/2000

    def printStats(self):
        # the first value may have been sitting in the repo forever, so ignore the first time
        timing = self.createTiming
        self.logger.info('***** Statistics ***** ')
        if len(timing) > 1:
            self.logger.info('{1:3.2f}/{2:3.2f}/{3:3.2f} min/mean/max delay(creation)'.format(len(timing), min(timing), mean(timing), max(timing)))
        timing = self.receiveTiming
        if len(timing) > 1:
            self.logger.info('{1:3.2f}/{2:3.2f}/{3:3.2f} min/mean/max delay(receipt)'.format(len(timing), min(timing), mean(timing), max(timing)))
            self.logger.info('{} data requests satisfied'.format(len(timing)))
        self.logger.info('{} timeouts'.format(self.timeouts))
        self.logger.info('{} not ready responses'.format(self.notReady))
        self.logger.info('*'*22)

if __name__ == '__main__':
    config = RawConfigParser()
    config.read('config.cfg')
    prefix = config.get('Data', 'prefix')
    suffix = config.get('Data', 'suffix')

    interestLifetime = config.get('Publisher', 'interestLifetime')

    fullName = Name(prefix).append(suffix)
    consumer = RepoConsumer(fullName, interestLifetime=interestLifetime)
    try:
        consumer.start()
    except KeyboardInterrupt:
        consumer.stop()
    consumer.printStats()

        
         
        
