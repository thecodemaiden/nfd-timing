#!/usr/bin/python

from pyndn import Name, Face, Interest, Data, Exclude
import time
import sys
import re
from numpy import mean

import logging

class RepoConsumer:
    TIMEOUT = 100.0
    def __init__(self, dataPrefix, lastVersion=None, start=True):
        self.prefix = Name(dataPrefix)
        
        #used in the exclude to make sure we get new data only
        self.lastVersion = lastVersion

        self.face = Face()
        self.dataFormat = re.compile("\((\d+\.?\d*)\)") # data should start with a timestamp in 
        logFormat = '%(asctime)-10s %(message)s'
        self.logger = logging.getLogger('RepoConsumer')
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(logging.StreamHandler())
        fh = logging.FileHandler('repo_consumer.log', mode='w')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(logFormat))
        self.logger.addHandler(fh)
        self.timing = []
        self.timeouts = 0
        self.notReady = 0

        self.nextIssue = None

    def onData(self, interest, data):
        now = time.time()
        # for now, assume there is a version appended to the interest
        nameLength = interest.getName().size()
        dataStr = data.getContent().toRawStr()
        try:
            lastComponent = data.getName().get(-1).toEscapedString()
            print lastComponent
            if str(lastComponent) == 'MISSING':
                self.notReady += 1
                logger.info('repo not ready')
                self.waitThenReissue()
                return

            self.lastVersion = data.getName().get(nameLength)
            self.logger.debug(interest.getName().toUri() + ": version " + self.lastVersion.toEscapedString())
            match = self.dataFormat.match(data.getContent().toRawStr())
            ts = float(match.group(1))
            self.timing.append(now-ts)
            self.logger.debug("Created: " + str(ts) +  ", received: " + str(now))
        except Exception as  e:
            self.logger.exception(str(e))
        self.reissueInterest()

    def waitThenReissue(self):
        if self.nextIssue is not None:
            now = time.clock()
            if self.nextIssue > now:
                time.sleep(self.nextIssue-now)
        self.reissueInterest()

    def onTimeout(self, interest):
        self.logger.debug("timeout")
        self.timeouts += 1
        self.waitThenReissue()

    def reissueInterest(self):
        interest = Interest(Name(self.prefix))
        interest.setInterestLifetimeMilliseconds(self.TIMEOUT) 
        #interest.setMustBeFresh(False)
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
        timing = self.timing
        self.logger.info('***** Statistics ***** ')
        if len(timing) > 1:
            self.logger.info('{1:3.2f}/{2:3.2f}/{3:3.2f} min/mean/max delay'.format(len(timing), min(timing), mean(timing), max(timing)))
            self.logger.info('{} data requests satisfied'.format(len(timing)))
        self.logger.info('{} timeouts'.format(consumer.timeouts))
        self.logger.info('{} not ready responses'.format(consumer.notReady))
        self.logger.info('*'*22)

if __name__ == '__main__':
    consumer = RepoConsumer("/repotest/data/3")
    consumer.reissueInterest()
    try:
        while True:
            consumer.face.processEvents()
            time.sleep(0.01)
    except KeyboardInterrupt:
        consumer.face.shutdown()
    consumer.printStats()

        
         
        
