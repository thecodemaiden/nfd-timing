#!/usr/bin/python

#
# This  publisher uses MemoryContentCache
#

#TODO: track timeouts, implement onDataMissing

from pyndn import Name, ThreadsafeFace, Interest, Data
from pyndn.security import KeyChain
from repo_command_pb2 import RepoCommandParameterMessage
from repo_response_pb2 import RepoCommandResponseMessage
from pyndn.util.memory_content_cache import MemoryContentCache
from pyndn.encoding import ProtobufTlv
from pyndn.security import Sha256WithRsaSignature

from threading import Thread
from mock import Mock
from ConfigParser import RawConfigParser
from data_stats import StatsCollector

import time
import traceback
import logging
import sys

#for ThreadsafeFace
try:
    import asyncio
except ImportError:
    import trollius as asyncio
    from trollius import From, Return

# version, insert request time, data publish time, insert begin time, insert finish time


logger = logging.getLogger('RepoPublisher')
logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
sh.setLevel(logging.DEBUG)
fh = logging.FileHandler('repo_push.log')
fh.setLevel(logging.DEBUG)
logger.addHandler(sh)
logger.addHandler(fh)

logging.getLogger('trollius').addHandler(sh)

shouldCollectStats = False
shouldSign = True
if shouldCollectStats:
    stats = StatsCollector()
else:
    stats = Mock()

class MCCPublisher:
    def __init__(self, dataPrefix, dataSuffix, keychain=None):
        self.currentInsertion = -1
        self.currentStatus = -1
        self.face = None
        self.loop = None
        self.dataName = Name(dataPrefix).append(dataSuffix)
        self.dataPrefix = Name(dataPrefix)

        if keychain is not None:
            self.keychain = keychain
        else:
            self.keychain = KeyChain()

        self.certificateName = self.keychain.getDefaultCertificateName()

        self.fakeSignature = Sha256WithRsaSignature()

        self.failureCount = 0
        self.successCount = 0

        self.dataCache = None

    def onRegisterFailed(self):
        logger.error("Could not register data publishing face!")
        self.stop()

    def stop(self):
        self.loop.close()
        self.face.shutdown()

    def generateVersionedName(self):
        fullName = Name(self.dataName)
        # currently we need to provide the version ourselves when we
        # poke the repo
        ts = int(time.time()*1000)
        fullName.appendVersion(int(ts))
        return fullName

    def generateData(self, baseName):
        '''
           This appends the segment number to the data name, since repo-ng tends to expect it
        '''
        # just make up some data and return it
        ts = (time.time())
        segmentId = 0 # compatible with repo-ng test: may change to test segmented data

        versionStr = baseName.get(-1).toEscapedString()
        dataName = Name(baseName)
        dataName.appendSegment(segmentId)

        d = Data(dataName)
        content = "(" + str(ts) +  ") Data named " + dataName.toUri()
        d.setContent(content)
        d.getMetaInfo().setFinalBlockID(segmentId)
        d.getMetaInfo().setFreshnessPeriod(-1)
        if shouldSign:
            self.keychain.sign(d, self.certificateName)
        else:
            d.setSignature(self.fakeSignature)

        stats.insertDataForVersion(versionStr, {'publish_time':time.time()})
        logger.debug('Publishing: '+d.getName().toUri())
        return d

    def onTimeout(self, prefix):
        logger.warn('Timeout waiting for '+prefix.toUri())

    @asyncio.coroutine
    def insertNewVersion(self, interval=20):
        #while True:
            newVersion = self.generateVersionedName()
            versionStr = newVersion.get(-1).toEscapedString()
            logger.info('Inserting: '+versionStr)
            stats.insertDataForVersion(versionStr, {'insert_request':time.time()})

            newData = self.generateData(newVersion)

            self.dataCache.add(newData)
            stats.insertDataForVersion(versionStr, {'insert_complete':time.time()})
            yield From (self.insertNewVersion())

    def start(self):
        self.loop = asyncio.new_event_loop()
        self.face = ThreadsafeFace(self.loop, "")
        self.dataCache = MemoryContentCache(self.face, 100)

        asyncio.set_event_loop(self.loop)
        self.face.setCommandSigningInfo(self.keychain, self.certificateName)

        self.dataCache.registerPrefix(self.dataPrefix, self.onRegisterFailed)
        self.loop.run_until_complete(self.insertNewVersion())

        
if __name__ == '__main__':
    tb = None
    config = RawConfigParser()
    config.read('config.cfg')
    data_prefix = config.get('Data', 'prefix')
    data_suffix = config.get('Data', 'suffix')

    mccPublisher = MCCPublisher(data_prefix, data_suffix)

    try:
        mccPublisher.start()
    except KeyboardInterrupt:
        mccPublisher.stop()
    else:
        traceback.print_stack()
    stats.displayStats()
    
