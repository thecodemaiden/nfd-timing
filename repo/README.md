Repository Tests
================

This tests publishing, aggregating and requesting data from different repository types. Currently there are tests with repo-ng and with MemoryContentCache.

Make sure set up the forward to route the data prefix correctly (default is /repotest/data) if you run the publisher and consumer on different Pis.

The data prefix and data name can be changed in (config.cfg).

The consumer polls the repo prefix for the newest data. After the first response, it excludes all data older (smaller in NDN canonical ordering) than any previous response.  


Repo Test
---------
Make sure you are running ndn-repo-ng in the background, preferably with the supplied configuration file, e.g.
>    ndn-repo-ng -c repo-ng.conf &

The publisher contains two threads, one which issues command interests to kick the repo, and the other that supplies the requested data.  


MemoryContentCache Test
-----------------------
No extra setup should be needed.  

The publisher puts data directly into the content cache instead of sending interests out to another process/face.  Note that repo-ng can use long-lived interests to pick up data that becomes available later, whereas MemoryContentCache will call the onDataMissing callback right away.  
 
