Repo Test
==========
Make sure you are running ndn-repo-ng in the background, preferably with the supplied configuration file, e.g.
>    ndn-repo-ng -c repo-ng.conf


The consumer polls the repo prefix for the newest data. After the first response, it excludes all data older (smaller in NDN canonical ordering) than any previous response.  


The publisher contains two threads, one which issues command interests to kick the repo, and the other that supplies the requested data.  
