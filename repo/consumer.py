#!/usr/bin/python

from pyndn import Name, Face, Interest, Data, Exclude
import time
import sys
import re
from numpy import mean

import logging

class RepoConsumer:
    TIMEOUT = 50
    def __init__(self, dataPrefix, lastVersion=None, start=True):
        self.prefix = Name(dataPrefix)
        
        #used in the exclude to make sure we get new data only
        self.lastVersion = lastVersion

        self.face = Face()
        self.dataFormat = re.compile("\((\d+\.?\d*)\)") # data should start with a timestamp in 
        logFormat = '%(asctime)-10s %(message)s'
        self.logger = logging.getLogger('RepoConsumer')
        self.logger.setLevel(logging.DEBUG)
        #self.logger.addHandler(logging.StreamHandler())
        fh = logging.FileHandler('repo_consumer.log', mode='w')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(logFormat))
        self.logger.addHandler(fh)
        self.timing = []

    def onData(self, interest, data):
        now = time.time()
        # for now, assume there is a version appended to the interest
        nameLength = interest.getName().size()
        dataStr = data.getContent().toRawStr()
        try:
            self.lastVersion = data.getName().get(nameLength)
            self.logger.debug(interest.getName().toUri() + ": version " + self.lastVersion.toEscapedString())
            match = self.dataFormat.match(data.getContent().toRawStr())
            ts = float(match.group(1))
            self.timing.append(now-ts)
            self.logger.debug("Created: " + str(ts) +  ", received: " + str(now))
        except Exception as  e:
            self.logger.exception(str(e))
        self.reissueInterest()
        print ".",
        sys.stdout.flush()

    def onTimeout(self, interest):
        self.logger.debug("timeout")
        self.reissueInterest()
        print "x",
        sys.stdout.flush()

    def reissueInterest(self):
        interest = Interest(Name(self.prefix))
        interest.setInterestLifetimeMilliseconds(RepoConsumer.TIMEOUT) 
        interest.setMustBeFresh(False)
        if self.lastVersion is not None:
            e = Exclude()
            e.appendAny()
            e.appendComponent(self.lastVersion)
            interest.setExclude(e)
        interest.setChildSelector(1) #rightmost == freshest
        self.face.expressInterest(interest, self.onData, self.onTimeout)
            

if __name__ == '__main__':
    consumer = RepoConsumer("/repotest/data/2")
    consumer.reissueInterest()
    try:
        while True:
            consumer.face.processEvents()
            time.sleep(0.01)
    except KeyboardInterrupt:
        consumer.face.shutdown()

    # the first value may have been sitting in the repo forever, so ignore the first time
    timing = consumer.timing[1:]
    print 
    if len(timing) > 0:
        print ('{1:3.2f}/{2:3.2f}/{3:3.2f} min/mean/max delay'.format(len(timing), min(timing), mean(timing), max(timing)))
        print ('{} data requests made'.format(len(timing)))
         
        
