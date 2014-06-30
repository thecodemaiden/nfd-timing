#!/usr/bin/python

#
# This is the data publisher - it pokes ther repo every
# so often to insert a new version under 1 of N names
#

# TODO - put command prefix into variable/config

from pyndn import Name, Face, Interest, Data
from pyndn.security import KeyChain
from repo_command_pb2 import RepoCommandParameterMessage
from repo_response_pb2 import RepoCommandResponseMessage
from pyndn.encoding import ProtobufTlv

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


logger = logging.getLogger('RepoPublisher')
logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
sh.setLevel(logging.WARNING)
fh = logging.FileHandler('repo_push.log')
fh.setLevel(logging.INFO)
logger.addHandler(sh)
logger.addHandler(fh)

def onDataInterest(prefix, interest, transport, pxID):
    '''
       For publishing face
    '''
    # just make up some data and return it
    interestName = interest.getName()
    logger.info("Interest for " + interestName.toUri())

    ## CURRENTLY ASSUMES THERE'S A VERSION/SEGMENT SUFFIX!
    dataName = Name(interestName.getPrefix(-1))
    ts = (time.time())
    segmentId = 0
    try:
       segmentId = interestName().get(-1).toSegment()
    except:
        logger.debug("Could not find segment id!")
    dataName.appendSegment(segmentId)

    versionStr = interestName.get(-2).getValue().toRawStr()
    logger.debug('publishing ' + versionStr)
    info = getInfoForVersion(versionStr)

    d = Data(dataName)
    content = "(" + str(ts) +  ") Data named " + dataName.toUri()
    d.setContent(content)
    d.getMetaInfo().setFinalBlockID(segmentId)
    keychain.sign(d, certName)

    encodedData = d.wireEncode()
    now = time.time()

    if info is not None:
        info['publish_time'] = now
    transport.send(encodedData.toBuffer())

'''
    For poking the repo
'''

def createInsertInterest(fullName):
    global lastName
    # we have to do the versioning when we poke the repo
    interestName = Name(fullName)
    
    insertionName = Name("/repotest/repo/insert")
    commandParams = RepoCommandParameterMessage()

    for i in range(interestName.size()):
        commandParams.repo_command_parameter.name.component.append(interestName.get(i).toEscapedString())

    commandParams.repo_command_parameter.start_block_id = 0
    commandParams.repo_command_parameter.end_block_id = 0

    commandName = insertionName.append(ProtobufTlv.encode(commandParams))
    interest = Interest(commandName)

    return interest

def createCheckInterest(fullName, checkNum):
    insertionName = Name("/repotest/repo/insert check")
    commandParams = RepoCommandParameterMessage()
    interestName = Name(fullName)

    commandParams.repo_command_parameter.process_id = checkNum
    for i in range(interestName.size()):
        commandParams.repo_command_parameter.name.component.append(interestName.get(i).toEscapedString())

    commandName = insertionName.append(ProtobufTlv.encode(commandParams))
    interest = Interest(commandName)

    return interest


current_insertion = -1
current_status = 404

def onCommandData(interest, data):
    global current_insertion # 
    global current_status
    now = time.time()
    # assume it's a command response
    response = RepoCommandResponseMessage()

    ProtobufTlv.decode(response, data.getContent())

    current_status = response.repo_command_response.status_code
    current_insertion =  response.repo_command_response.process_id
    logger.debug("Response status code: " + str(current_status) + ", process id: " + str(current_insertion) + ", insert #" + str(response.repo_command_response.insert_num))


def formatStats(name, values, unit='s'):
    return '{0: <25} {1:9.1f}/{2:9.1f}/{3:9.1f}{4} min/mean/max'.format(name, min(values), mean(values), max(values), unit)

def collectStats(data):
    """
        After we're done running, gather stats
    """
    insert_to_publish = []
    round_trip_time = []
    #insert_time = [x['insert_complete'] - x['insert_begin'] for x in data]
    #publish_to_ack = [x['insert_begin'] - x['publish_time'] for x in data]

    for x in data:
        try:
            round_trip_time.append(x['insert_complete'] - x['insert_request'])
        except KeyError:
            pass # don't include unfinished messages

        try:
            insert_to_publish.append(x['publish_time'] - x['insert_request'])
        except KeyError:
            pass

    print
    print '='*80
    print formatStats("Round trip time: ", round_trip_time)
    print formatStats("Publisher reaction time: ",  insert_to_publish)
    print '='*80
    print '{} packets created. '.format(len(data)) 


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
           time.sleep(0.1)
       face.shutdown()

    publisher_face = Face("localhost")
    publisher_face.setCommandSigningInfo(keychain, certName)
    publisher_face.registerPrefix(data_prefix, onDataInterest, registerFail)
    publisher = Thread(target=publisher_loop, name="Data publisher", args=(publisher_face,))    
    publisher.start()

    # and the face that pokes the repo - these could have been separate programs instead
    repo_face = Face("localhost")
    repo_face.setCommandSigningInfo(keychain, certName)
 
    success = Mock(side_effect=onCommandData)
    failure = Mock()
    try:
        # sleep a second, then tell the repo we want to insert some data
        time.sleep(1)
        while not done:
            #pick a random data name
            data_part = "2"# str(randint(0,N))

            fullName = Name(data_prefix).append(Name(data_part))

            # currently we need to provide the version ourselves when we
            # poke the repo
            ts = int(time.time()*1000)
            fullName.appendVersion(int(ts))
            command = createInsertInterest(fullName)

            versionStr = fullName.get(-1).toEscapedString()
            logger.debug('inserting: ' + versionStr)

            repo_face.makeCommandInterest(command)
            lastFailCount = failure.call_count
            lastSuccessCount = success.call_count

            repo_face.expressInterest(command, success, failure)
            insertTable.append({'version':versionStr, 'insert_request':time.time()})
            while success.call_count == lastSuccessCount and failure.call_count == lastFailCount:
                repo_face.processEvents()
                time.sleep(0.1)

            # only expecting to insert one segment (<1k) for each request         
            # check on the insert status
            # TODO: kick off a greenlet instead of setting global variable?
            if success.call_count > lastSuccessCount and current_insertion >= 0:
                lastFailCount = failure.call_count
                lastSuccessCount = success.call_count
                info = getInfoForVersion(versionStr)

                logger.debug("Checking on: " + str(current_insertion))
                if current_status == 100:
                   # just began inserting
                   info['insert_begin'] = time.time()
                while (current_status != 200 and current_status < 400):
                    checkCommand = createCheckInterest(fullName, current_insertion)
                    repo_face.makeCommandInterest(checkCommand)

                    checkSuccess = Mock(side_effect=onCommandData)
                    checkFailure = Mock()
                    repo_face.expressInterest(checkCommand, checkSuccess, checkFailure)
                    while checkSuccess.call_count == 0 and checkFailure.call_count == 0:
                        repo_face.processEvents()
                        time.sleep(0.1)

                if current_status == 200:
                    # done inserting
                    info['insert_complete'] = time.time()
            logger.info(' ')
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
        if failure.call_count > 0:
           print("Failed "+str(failure.call_count)+" times.")
        repo_face.shutdown()
        publisher_face.shutdown()
        collectStats(insertTable)
    
    
