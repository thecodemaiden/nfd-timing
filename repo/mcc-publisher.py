#!/usr/bin/python

#
# This is the data publisher using MemoryContentCache
#

# TODO - put command prefix into variable/config

from pyndn import Name, Face, Interest, Data
from pyndn.security import KeyChain
from repo_command_pb2 import RepoCommandParameterMessage
from repo_response_pb2 import RepoCommandResponseMessage
from pyndn.encoding import ProtobufTlv
from pyndn.util.memory_content_cache import MemoryContentCache

from threading import Thread
from random import randint, uniform
from mock import Mock
from numpy import mean

import time
import traceback
import logging
import sys


keychain = KeyChain()
certName = keychain.getDefaultCertificateName()

N = 4

# version, insert request time, data publish time, insert begin time, insert finish time
insertTable = []

def getInfoForVersion(version):
    found = None
    matches = [x for x in insertTable if x['version'] == version]
    # should only be 1 match
    if len(matches) > 0:
        found = matches[0]
    return found


logFormat = '%(asctime)-10s %(message)s'
logging.basicConfig(format=logFormat)

logger = logging.getLogger('RepoPublisher')
logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
sh.setLevel(logging.INFO)
fh = logging.FileHandler('mcc_push.log')
fh.setLevel(logging.DEBUG)
fh.setFormatter(logging.Formatter(logFormat))
#logger.addHandler(sh)
logger.addHandler(fh)

def generateData(baseName):
    '''
       This appends the segment number to the data name
    '''
    # just make up some data and return it
    ts = (time.time())
    segmentId = 0 # compatible with repo-ng test: may change to test segmented data

    versionComponent = baseName.get(-1) # should have a ts
    dataName = Name(baseName)
    dataName.appendSegment(segmentId)

    d = Data(dataName)
    content = "(" + str(ts) +  ") Data named " + dataName.toUri()
    d.setContent(content)
    d.getMetaInfo().setFinalBlockID(segmentId)
    d.getMetaInfo().setFreshnessPeriod(1000)
    keychain.sign(d, certName)

    info = getInfoForVersion(versionComponent.toEscapedString())
    if info is not None:
        info['publish_time'] = ts

    return d

def formatStats(name, values, unit='s'):
    return '{0: <25} {1:9.1f}/{2:9.1f}/{3:9.1f}{4} min/mean/max'.format(name, min(values), mean(values), max(values), unit)

def collectStats(data):
    """
        After we're done running, gather stats
    """
    insert_to_publish = []
    round_trip_time = []

    logger.info('')
    logger.info('****Statistics****')
    for x in data:
        try:
            round_trip_time.append(x['insert_complete'] - x['insert_request'])
        except KeyError:
            pass # don't include unfinished messages

        try:
            insert_to_publish.append(x['publish_time'] - x['insert_request'])
        except KeyError:
            pass

    try:
        logger.info(formatStats("Publisher reaction time: ",  insert_to_publish))
    except:
        pass
    try:
        logger.info(formatStats("Round trip time: ", round_trip_time))
    except:
        pass
    logger.info('{} packets created. '.format(len(data)))
    logger.info('*'*10)


def onDataMissing(prefix, interest, transport):
    logger.debug("Data missing for interest: " + interest.toUri())

if __name__ == '__main__':
    tb = None
    data_prefix = Name("/repotest/data")

    done = False
    # start publisher face
    registerFail = Mock()
    def publisher_loop(face):
       global done
       while not done:   
           face.processEvents()
           if registerFail.call_count > 0:
               logger.error("Registration failed!")
               done = True
           time.sleep(0.01)
       face.shutdown()

    publisher_face = Face("localhost")
    publisher_face.setCommandSigningInfo(keychain, certName)

    dataCache = MemoryContentCache(publisher_face, -1)
    dataCache.registerPrefix(data_prefix,  registerFail, onDataMissing)

    publisher = Thread(target=publisher_loop, name="Data publisher", args=(publisher_face,))    
    publisher.start()


    lastVersion = None
    try:
        # sleep a second, like the repo-ng test
        time.sleep(1)
        while not done:
            #pick a random data name
            data_part = "2"# str(randint(0,N))

            fullName = Name(data_prefix).append(Name(data_part))

            # currently we need to provide the version ourselves when we
            # poke the repo
            ts = int(time.time()*1000)
            fullName.appendVersion(int(ts))
            versionComponent = fullName.get(-1)
            versionStr = versionComponent.toEscapedString()
            logger.info('inserting: ' + versionStr)
            if lastVersion is not None:
                comp = Name().append(versionComponent).compare(Name().append(lastVersion))
                logger.debug("Version comparison (new.compare(old)) = " + str(comp))

            insertTable.append({'version':versionStr, 'insert_request':time.time()})
            data = generateData(fullName)
            dataCache.add(data)
            info = getInfoForVersion(versionStr)
            if info is not None:
                info['insert_complete'] = time.time()
            #time.sleep(0.5)
            lastVersion = versionComponent
    except Exception as e:
        print e
        tb = traceback.format_exc()
    except KeyboardInterrupt:
        pass
    else:
        pass
    finally:
        done = True
        time.sleep(0.5)
        if tb is not None:
            print tb
        collectStats(insertTable)
        logging.disable(logging.CRITICAL)
    
    