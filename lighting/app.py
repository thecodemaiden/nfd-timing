from  light_command_pb2 import LightCommandMessage
from pyndn.encoding import ProtobufTlv
from pyndn import Name, Face, Interest, Data
from pyndn.security import KeyChain

from mock import Mock
from random import randrange
from numpy import mean

import time

def createCommandInterest(prefix="/testlight/setRGB", color=(255,0,128)):
    interestName = Name(prefix)
    commandParams = LightCommandMessage()
    
    messageColor = commandParams.command.pattern.colors.add()
    messageColor.r = color[0]
    messageColor.g = color[1]
    messageColor.b = color[2]

    commandName = interestName.append(ProtobufTlv.encode(commandParams))
    interest = Interest(commandName)
    interest.setInterestLifetimeMilliseconds(2000)

    return interest

timing = []
timeouts = 0

shouldSign = False
keychain = KeyChain()
certName = keychain.getDefaultCertificateName()
def waitForResponse(face, interest):
    global timeouts
    onData = Mock()
    onTimeout = Mock()
  
    if shouldSign:
        face.makeCommandInterest(interest)
    face.expressInterest(interest, onData, onTimeout)
    start = time.time()
    while (onData.call_count == 0 and onTimeout.call_count == 0):
        face.processEvents()
        time.sleep(0.01)

    done = time.time()
    
    if onData.call_count > 0:
        timing.append(done-start)
    if onTimeout.call_count > 0:
        timeouts +=1


if __name__ == '__main__':
    face = Face()
    if shouldSign:
        face.setCommandSigningInfo(keychain, certName)
    input = None
    try:
        while True:
            r = randrange(256)
            g = randrange(256)
            b = randrange(256)
            interest = createCommandInterest(color=(r,g,b))
            waitForResponse(face, interest)
    except KeyboardInterrupt:
        pass
    face.shutdown()
    print "Response time: {:3.2f}/{:3.2f}/{:3.2f}s min/mean/max".format(min(timing), mean(timing), max(timing))
    print str(timeouts) + " timeouts"
