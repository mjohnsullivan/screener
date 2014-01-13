"""
A DCI media server emulator
"""
from twisted.internet import protocol, reactor
import logging, json

import klv

from screener import cfg
from screener.lib import config as config_handler
from screener.util import int_to_bytes, bytes_to_str
from screener.system import system_time
from screener.playback import Playback
from screener.content import Content
from screener.schedule import Schedule


# See SMPTE ST-336-2007 for details on the header format
HEADER = [0x06, 0x0e, 0x2b, 0x34, 0x02, 0x04, 0x01] + ([0x00] * 9)


class Screener(protocol.Protocol):
    def __init__(self, factory):
        logging.info('Instantiating Screener()')
        self.factory = factory

    def dataReceived(self, data):
        return_data = self.factory.process_klv(data)
        self.transport.write(str(return_data))


class ScreenerFactory(protocol.Factory):
    def __init__(self):
        logging.info('Instantiating ScreenerFactory()')
        self.content = Content()
        self.playback = Playback()
        self.schedule = Schedule()

        self.handlers = {
                0x00 : self.playback.play,
                0x01 : self.playback.stop,
                0x02 : self.playback.status,
                0x03 : system_time,
                0x04 : self.content.get_cpl_uuids,
                0x05 : self.playback.pause,
                0x06 : self.content.ingest,
                0x07 : self.content.get_ingests_info,
                0x08 : self.content.get_ingest_info
            }

    def buildProtocol(self, addr):
        return Screener(self)

    def process_klv(self, msg):
        """
        Processes a KLV message by extracting JSON string from msg
        and passing it to the appropriate handlers
        """
        k, v = klv.decode(msg, 16)
        handler = self.handlers[k[15]]

        decoded_val = json.loads(bytes_to_str(v))
        result = handler(**decoded_val) or ''

        return klv.encode(HEADER, json.dumps(result))

    def reset(self):
        self.__init__()


def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter("%(asctime)s - %(threadName)s - %(levelname)s - %(message)s")
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logging.getLogger('screener')


if __name__ == '__main__':
    config_handler.read(cfg.config_file())
    config_handler.save()
    setup_logging()

    logging.info('Setting up Screener')
    reactor.listenTCP(cfg.screener_port(), ScreenerFactory(), interface=cfg.screener_host())

    logging.info('Serving on localhost:{0}'.format(cfg.screener_port()))
    reactor.run()
