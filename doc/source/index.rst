.. gringotts documentation master file, created by
   sphinx-quickstart on Mon Dec  2 11:38:24 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to gringotts's documentation!
=====================================

Gringotts is an extensible, realtime and accurate billing solution for OpenStack.

* For realtime, it consumes the notifications sent out by OpenStack services to decide when to start bill, when to change bill, and when to stop bill.
* For accurate, it can charge the bill to second, which dramatically avoids wasting of resources.
* For extensible, it can hold millions of bills accross multipule regions.


Getting Startted
================
.. toctree::
   :maxdepth: 2

   installation

API
===
.. toctree::
   :maxdepth: 1

   webapi/index


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

