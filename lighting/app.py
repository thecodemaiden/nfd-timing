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
def waitForResponse(face, interest, timeout=None):
    global timeouts
    onData = Mock()
    onTimeout = Mock()
  
    if shouldSign:
        face.makeCommandInterest(interest)
    face.expressInterest(interest, onData, onTimeout)
    start = time.time()
    while (onData.call_count == 0 and onTimeout.call_count == 0):
        face.processEvents()
        #time.sleep(0.001)
        if timeout is not None and time.time() >= start+timeout:
            break

    done = time.time()
    
    if onTimeout.call_count > 0:
        timeouts +=1
    else:
        timing.append(done-start)


if __name__ == '__main__':
    face = Face()
    if shouldSign:
        face.setCommandSigningInfo(keychain, certName)
    input = None
    N = 0
    toggle = False
    try:
        while True:
            byteVal = (N)&0xff
            if toggle:
                byteVal = 255 - byteVal
            toggle = not toggle
            color = (0,0,0)
            selector = (N/256)%0x3
            if selector == 1:
                color = (byteVal, 0, 0)
            elif selector == 2:
                color = (0, byteVal, 0)
            elif selector == 0:
                color = (0, 0, byteVal)

            interest = createCommandInterest(color=color)
            waitForResponse(face, interest, None)
            N += 5
    except KeyboardInterrupt:
        pass
    face.shutdown()
    print "Response time: {:3.2f}/{:3.2f}/{:3.2f}s min/mean/max".format(min(timing), mean(timing), max(timing))
    print str(timeouts) + " timeouts"
