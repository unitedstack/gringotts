#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# vim: tabstop=4 shiftwidth=4 softtabstop=4

"""The simple http server"""

import logging
import sys

from oslo.config import cfg
from wsgiref import simple_server

from gringotts import service
from gringotts.api import app
from gringotts.openstack.common import log

CONF = cfg.CONF
LOG = log.getLogger(__name__)


def main():
    # Pase config file and command line options, then start logging
    service.prepare_service(sys.argv)

    # Build and start the WSGI app
    host = CONF.api.host
    port = CONF.api.port
    wsgi = simple_server.make_server(host,
                                     port,
                                     app.VersionSelectorApplication())

    LOG.info("Serving on http://%s:%s" % (host, port))
    LOG.info("Configuration:")
    CONF.log_opt_values(LOG, logging.INFO)

    try:
        wsgi.serve_forever()
    except KeyboardInterrupt:
        pass
