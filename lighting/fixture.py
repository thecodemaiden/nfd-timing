from lighting.KinetSender import KinetSender
import logging
import time
import sys

from pyndn import Name, Face, Interest, Data
from pyndn import Sha256WithRsaSignature
from pyndn.security import KeyChain

from pyndn.encoding import ProtobufTlv
from light_command_pb2 import LightCommandMessage

class LightController():
    shouldSign = False
    COLORS_PER_LIGHT = 3
    STRAND_SIZE = 50
    def __init__(self, nStrands=1, myIP="192.168.1.1", lightIP="192.168.1.50", prefix="/testlight"):
        self.log = logging.getLogger("LightController")
        self.log.setLevel(logging.DEBUG)
        sh = logging.StreamHandler()
        sh.setLevel(logging.WARNING)
        self.log.addHandler(sh)
        fh = logging.FileHandler("LightController.log")
        fh.setLevel(logging.INFO)
        self.log.addHandler(fh)

        self.payloadBuffer = [[0]*self.STRAND_SIZE*self.COLORS_PER_LIGHT for n in range(nStrands)]

        self.kinetsender = KinetSender(myIP, lightIP, nStrands, self.STRAND_SIZE*self.COLORS_PER_LIGHT)
        self.registerFailed = False
        self.done = False
        self.prefix = Name(prefix)
        self.keychain = KeyChain()
        self.certificateName = self.keychain.getDefaultCertificateName()

    # XXX: we should get a thread for this or something!
    def start(self):
        self.face = Face()
        self.face.setCommandSigningInfo(self.keychain, self.certificateName)
        self.face.registerPrefix(self.prefix, self.onLightingCommand, self.onRegisterFailed)
        while self.face is not None:
            self.face.processEvents()
            if self.registerFailed:
                self.stop()
                break
            #time.sleep(0.001)


    def stop(self):
        self.kinetsender.stop = True
        self.kinetsender.complete.wait()         
        self.face.shutdown()
        self.face = None

    def signData(self, data):
        if LightController.shouldSign:
            self.keychain.sign(data, self.certificateName)
        else:
            data.setSignature(Sha256WithRsaSignature())

    def setPayloadColor(self, strand, color):
        # will expand this to allow the repeats, etc
        self.payloadBuffer[strand] = [int(color.r)&0xff, int(color.g)&0xff, int(color.b)&0xff]*self.STRAND_SIZE

    def onLightingCommand(self, prefix, interest, transport, prefixId):
        interestName = Name(interest.getName())
        #d = Data(interest.getName().getPrefix(prefix.size()+1))
        d = Data(interest.getName())
        # get the command parameters from the name
        try:
            commandComponent = interest.getName().get(prefix.size())
            commandParams = interest.getName().get(prefix.size()+1)

            lightingCommand = LightCommandMessage()
            ProtobufTlv.decode(lightingCommand, commandParams.getValue())
            self.log.info("Command: " + commandComponent.toEscapedString())
            requestedColor = lightingCommand.command.pattern.colors[0] 
            colorStr = str((requestedColor.r, requestedColor.g, requestedColor.b))
            self.log.info("Requested color: " + colorStr)
            self.setPayloadColor(0, requestedColor)
            self.sendLightPayload(1)
            d.setContent("Gotcha: " + colorStr+ "\n")
        except Exception as e:
            print e
            d.setContent("Bad command\n")
        finally:
            d.getMetaInfo().setFinalBlockID(0)
            self.signData(d)

        encodedData = d.wireEncode()
        transport.send(encodedData.toBuffer())

    def onRegisterFailed(self, prefix):
        self.log.error("Could not register " + prefix.toUri())
        print "Register failed!"
        self.registerFailed = True

    def sendLightPayload(self, port):
        self.kinetsender.setPayload(port, self.payloadBuffer[port-1])

done = False
if __name__ == '__main__':
    N=0 

    l = LightController()
    # set up a face to listen for lighting commands
    try:
        l.start()
    except KeyboardInterrupt:
        l.stop()


            
	
