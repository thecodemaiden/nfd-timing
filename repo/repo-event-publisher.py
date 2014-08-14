#!/usr/bin/python

#
# This is the data publisher - it starts an insert to the repo,
# published the requested data, then check the insertion status
#

#TODO: track timeouts

from pyndn.security import KeyChain
from pyndn import Name,  Data, Interest, ThreadsafeFace
from repo_command_pb2 import RepoCommandParameterMessage
from repo_response_pb2 import RepoCommandResponseMessage
from pyndn.encoding import ProtobufTlv

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


#logger = logging.getLogger('RepoPublisher')
#logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
sh.setLevel(logging.DEBUG)
#fh = logging.FileHandler('repo_push.log')
#fh.setLevel(logging.DEBUG)
#logger.addHandler(sh)
#logger.addHandler(fh)
#
logging.getLogger('trollius').addHandler(sh)
#logger = Mock()

shouldCollectStats = True
if shouldCollectStats:
    stats = StatsCollector()
else:
    stats = Mock()

class RepoPublisher:
    def __init__(self, repoPrefix, dataPrefix, dataSuffix, keychain=None):
        self.currentInsertion = -1
        self.currentStatus = -1
        self.face = None
        self.loop = None
        self.repoPrefix = Name(repoPrefix)
        self.dataName = Name(dataPrefix).append(dataSuffix)
        self.dataPrefix = Name(dataPrefix)

        if keychain is not None:
            self.keychain = keychain
        else:
            self.keychain = KeyChain()

        self.certificateName = self.keychain.getDefaultCertificateName()

        self.failureCount = 0
        self.successCount = 0

        self.processIdToVersion = {}

    def onRegisterFailed(self):
        logger.error("Could not register data publishing face!")
        self.stop()

    def versionFromCommandMessage(self, component):
        command = RepoCommandParameterMessage()
        try:
            ProtobufTlv.decode(command, component.getValue())
        except Exception as e:
            logger.warn(e)

        # last component of name to insert is version
        versionStr = command.repo_command_parameter.name.component[-1]

        return versionStr

    def stop(self):
        self.loop.close()
        self.face.shutdown()

    def onPublishInterest(self, prefix, interest, transport, pxID):
        '''
           For publishing face
        '''
        # just make up some data and return it
        interestName = interest.getName()
        logger.info("Interest for " + interestName.toUri())

        ## CURRENTLY ASSUMES THERE'S A VERSION+SEGMENT SUFFIX!
        dataName = Name(interestName)
        ts = (time.time())
        segmentId = 0
        #try:
        #   segmentId = interestName.get(-1).toSegment()
        #except:
            #logger.debug("Could not find segment id!")
            #dataName.appendSegment(segmentId)
        versionStr = str(interestName.get(-2).getValue())
        logger.debug('Publishing ' + versionStr + ' @ ' + str(ts))

        d = Data(dataName)
        content = "(" + str(ts) +  ") Data named " + dataName.toUri()
        d.setContent(content)
        d.getMetaInfo().setFinalBlockID(segmentId)
        d.getMetaInfo().setFreshnessPeriod(1000)
        self.keychain.sign(d, self.certificateName)

        encodedData = d.wireEncode()

        stats.insertDataForVersion(versionStr, {'publish_time': time.time()})
        transport.send(encodedData.toBuffer())
        #yield from asyncio.sleep()

    def generateVersionedName(self):
        fullName = Name(self.dataName)
        # currently we need to provide the version ourselves when we
        # poke the repo
        ts = int(time.time()*1000)
        fullName.appendVersion(int(ts))
        return fullName

    def onTimeout(self, prefix):
        logger.warn('Timeout waiting for '+prefix.toUri())

    
    def start(self):
        self.loop = asyncio.new_event_loop()
        self.face = ThreadsafeFace(self.loop, "")

        asyncio.set_event_loop(self.loop)
        self.face.setCommandSigningInfo(self.keychain, self.certificateName)
        self.face.registerPrefix(self.dataPrefix,self.onPublishInterest, self.onRegisterFailed)
        try:
            self.loop.call_soon(self.kickRepo)
            self.loop.run_forever()
        finally:
           self.stop() 


    def kickRepo(self):
        # command the repo to insert a new bit of data
        fullName = self.generateVersionedName()
        versionStr = str(fullName.get(-1).getValue())
        command = self.createInsertInterest(fullName)

        logger.debug('inserting: ' + versionStr)

        self.face.makeCommandInterest(command)
        def timeoutLoop(interest):
            logger.warn('Timed out on ' + interest.toUri())
            self.face.expressInterest(command, self.onCommandData, self.onTimeout)

        self.face.expressInterest(command, self.onCommandData, timeoutLoop)
        stats.insertDataForVersion(versionStr, {'insert_request':time.time()})

    def checkInsertion(self, versionStr, processID):
        fullName = Name(self.dataName).append(Name.fromEscapedString(versionStr))
        checkCommand = self.createCheckInterest(fullName, processID)
        self.face.makeCommandInterest(checkCommand)
        def timeoutLoop(interest):
            logger.warn('Timed out waiting on: '+interest.toUri())
            self.face.expressInterest(checkCommand, self.onCommandData, self.onTimeout)
        self.face.expressInterest(checkCommand, self.onCommandData, timeoutLoop)

    def createInsertInterest(self, fullName):
        '''
            For poking the repo
        '''
        # we have to do the versioning before we poke the repo
        interestName = Name(fullName)
        logger.debug('Creating insert interest for: '+interestName.toUri())
        
        insertionName = Name(self.repoPrefix).append('insert')
        commandParams = RepoCommandParameterMessage()

        for i in range(interestName.size()):
            commandParams.repo_command_parameter.name.component.append(interestName.get(i).getValue().toRawStr())

        commandParams.repo_command_parameter.start_block_id = 0
        commandParams.repo_command_parameter.end_block_id = 0

        commandName = insertionName.append(ProtobufTlv.encode(commandParams))
        interest = Interest(commandName)

        interest.setInterestLifetimeMilliseconds(2000)

        return interest

    def createCheckInterest(self, fullName, checkNum):
        insertionName = Name(self.repoPrefix).append('insert check')
        commandParams = RepoCommandParameterMessage()
        interestName = Name(fullName)

        commandParams.repo_command_parameter.process_id = checkNum
        for i in range(interestName.size()):
            commandParams.repo_command_parameter.name.component.append(str(interestName.get(i).getValue()))

        commandName = insertionName.append(ProtobufTlv.encode(commandParams))
        interest = Interest(commandName)

        return interest

    def onCommandData(self, interest, data):
        # assume it's a command response
        now = time.time()
        response = RepoCommandResponseMessage()
        ProtobufTlv.decode(response, data.getContent())


        self.currentStatus = response.repo_command_response.status_code
        self.currentInsertion =  response.repo_command_response.process_id
        logger.debug("Response status code: " + str(self.currentStatus) + ", process id: " + str(self.currentInsertion) + ", insert #" + str(response.repo_command_response.insert_num))

        command_idx = self.repoPrefix.size()
        # we also need to keep track of the mapping from version to processID for stats
        commandName = interest.getName().get(command_idx).getValue().toRawStr()
        if commandName == 'insert check':
            try:
                versionStr = self.processIdToVersion[self.currentInsertion]
                if self.currentStatus == 200:
                    stats.insertDataForVersion(versionStr, {'insert_complete': now})
                    self.loop.call_soon(self.kickRepo)
                elif self.currentStatus >= 400:
                    self.failureCount += 1
                    self.loop.call_soon(self.kickRepo)
                else:
                    self.loop.call_soon(self.checkInsertion, versionStr, self.currentInserion)
            except:
                logger.warn('Missing version for process ID {}'.format(self.currentInsertion))
        elif commandName == 'insert':
            if self.currentStatus == 100:
                versionStr = self.versionFromCommandMessage(interest.getName().get(command_idx+1))
                self.processIdToVersion[self.currentInsertion] = versionStr
                stats.insertDataForVersion(versionStr, {'insert_begin': now})
                self.loop.call_soon(self.checkInsertion, versionStr, self.currentInsertion)
            else:
                self.failureCount += 1
                self.loop.call_soon(self.kickRepo)

        
if __name__ == '__main__':
    tb = None
    config = RawConfigParser()
    config.read('config.cfg')
    data_prefix = config.get('Data', 'prefix')
    data_suffix = config.get('Data', 'suffix')

    repo_prefix = config.get('Repo', 'prefix')

    repoPublisher = RepoPublisher(repo_prefix, data_prefix, data_suffix)

    try:
        repoPublisher.start()
    except KeyboardInterrupt:
        repoPublisher.stop()
    else:
        traceback.print_stack()
    stats.displayStats()
    
    
