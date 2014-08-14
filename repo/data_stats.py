fconsumerrom numpy import mean
class StatsCollector:
    def __init__(self):
        self.insertTable = {}


    def getInfoForVersion(self, version):
        found = None
        if version in self.insertTable:
            found = self.insertTable[version]
        return found

    def insertDataForVersion(self, version, dataDict):
        info = self.getInfoForVersion(version)
        if info is None:
            self.insertTable[version] = dataDict
        else:
            info.update(dataDict)

    def formatStats(self, name, values, unit='s'):
        return '{0: <25} {1:9.1f}/{2:9.1f}/{3:9.1f}{4} min/mean/max'.format(name, min(values), mean(values), max(values), unit)

    def displayStats(self):
        """
            After we're done running, gather stats
        """
        insert_to_publish = []
        round_trip_time = []

        for x in self.insertTable:
            dataPoint = self.insertTable[x]
            try:
                round_trip_time.append(dataPoint['insert_complete'] - dataPoint['insert_request'])
            except KeyError:
                pass # don't include unfinished messages

            try:
                insert_to_publish.append(dataPoint['publish_time'] - dataPoint['insert_request'])
            except KeyError:
                pass

        print
        print '='*80
        print self.formatStats("Round trip time: ", round_trip_time)
        print self.formatStats("Publisher reaction time: ",  insert_to_publish)
        print '='*80
        print '{} packets created. '.format(len(self.insertTable)) 
