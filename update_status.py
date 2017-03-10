# update Cachethq metric from Uptime Robot monitor(s) via APIs
# from 2016 Axiacore https://github.com/Axiacore/cachet-uptime-robot/
# Downgraded for python 2.7 by Fgth (F.Soyer 2017)
# Other changes :
# - Migrated Uptime Robot API key in config.ini
# - Added "Debug" to display informational messages while configuring
# - Changed the field "custom_uptime_ratio" read from Uptime Robot to update metric on Cachet,
#   for last value of "response_times", more demonstrative IMHO.
# - You can uncomment "verify=False" if your Cachet site as an SSL self-signed certificate (for testing time!)
#   For production, no more reason to not use a Let's Encrypt cert !!
# - Added some informational messages here and there for debug mode. Can be extended.

import configparser
import json
import requests
import sys
import time

debug = False

class UptimeRobot(object):
    """ Intermediate class for setting uptime stats.
    """
    def __init__(self, api_key, base_url):
        self.api_key = api_key
        self.base_url = base_url

    def get_monitors(self, response_times=1, logs=0, uptime_ratio=30):
        """
        Returns status and response payload for all known monitors.
        """
        endpoint = self.base_url
        data = {
                'api_key': format(self.api_key),
                'format': 'json',
                # responseTimes - optional (defines if the response time data of each
                # monitor will be returned. Should be set to 1 for getting them.
                # Default is 0)
                'response_times': format(response_times),
                 # logs - optional (defines if the logs of each monitor will be
                # returned. Should be set to 1 for getting the logs. Default is 0)
                'logs': format(logs),
                # customUptimeRatio - optional (defines the number of days to calculate
                # the uptime ratio(s) for. Ex: customUptimeRatio=7-30-45 to get the
                # uptime ratios for those periods)
                'custom_uptime_ratios': format(uptime_ratio)
            }

        r = requests.post(
            url=endpoint,
            data=data,
            headers={'content-type': "application/x-www-form-urlencoded",'cache-control': "no-cache"},
        )

        if not r.status_code==200:
            print('ERROR ',r.status_code,': No data was returned from UptimeMonitor')

        # Verifying in the response is jsonp in otherwise is error
        j_content = json.loads(r.content)
        if j_content.get('stat'):
            stat = j_content.get('stat')
            if stat == 'ok':
                return True, j_content

        return False, j_content

class CachetHq(object):
    # Uptime Robot status list
    UPTIME_ROBOT_PAUSED = 0
    UPTIME_ROBOT_NOT_CHECKED_YET = 1
    UPTIME_ROBOT_UP = 2
    UPTIME_ROBOT_SEEMS_DOWN = 8
    UPTIME_ROBOT_DOWN = 9

    # Cachet status list
    CACHET_OPERATIONAL = 1
    CACHET_PERFORMANCE_ISSUES = 2
    CACHET_SEEMS_DOWN = 3
    CACHET_DOWN = 4

    def __init__(self, cachet_api_key, cachet_url):
        self.cachet_api_key = cachet_api_key
        self.cachet_url = cachet_url

    def update_component(self, id_component=1, status=None):
        component_status = None

        # Not Checked yet and Up
        if status in [self.UPTIME_ROBOT_NOT_CHECKED_YET, self.UPTIME_ROBOT_UP]:
            component_status = self.CACHET_OPERATIONAL

        # Seems down
        elif status == self.UPTIME_ROBOT_SEEMS_DOWN:
            component_status = self.CACHET_SEEMS_DOWN

        # Down
        elif status == self.UPTIME_ROBOT_DOWN:
            component_status = self.CACHET_DOWN

        if component_status:
            url = '{0}/api/v1/{1}/{2}'.format(
                self.cachet_url,
                'components',
                id_component
            )
            data = {
                'status': component_status,
            }
            req = requests.put(
                url=url,
#                verify=False,
                data=data,
                headers={'X-Cachet-Token': self.cachet_api_key},
            )
            return req.content

    def set_data_metrics(self, value, status, timestamp, id_metric=1):
        url = '{0}/api/v1/metrics/{1}/points'.format(
            self.cachet_url,
            id_metric
        )

        # Default to 100ms
        if value == 0 and status == 2:
            value = 100

        data = {
            'value': value,
            'timestamp': timestamp,
        }
        req = requests.post(
            url,
            data=data,
#            verify=False,
            headers={'X-Cachet-Token': self.cachet_api_key},
        )
        return json.loads(req.content)

    def get_last_metric_point(self, id_metric):
        url = '{0}/api/v1/metrics/{1}/points'.format(
            self.cachet_url,
            id_metric
        )

        req = requests.get(
            url=url,
#            verify=False,
            headers={'X-Cachet-Token': self.cachet_api_key}
        )
        content = req.content

        last_page = json.loads(
            content
        ).get('meta').get('pagination').get('total_pages')

        url = '{0}/api/v1/metrics/{1}/points?page={2}'.format(
            self.cachet_url,
            id_metric,
            last_page
        )

        req = requests.get(
            url=url,
#            verify=False,
            headers={'X-Cachet-Token': self.cachet_api_key},
        )
        content = req.content

        if json.loads(content).get('data'):
            data = json.loads(content).get('data')[0]
        else:
            data = {
                'created_at': datetime.now().date().strftime(
                    '%Y-%m-%d %H:%M:%S'
                )
            }

        return data

class Monitor(object):
    def __init__(self, monitor_list, api_key, base_url):
        self.monitor_list = monitor_list
        self.api_key = api_key
        self.base_url = base_url

    def send_data_to_catchet(self, monitor):
        """ Posts data to Cachet API.
            Data sent is the value of last `Uptime`.
        """
        try:
            website_config = self.monitor_list[monitor.get('url')]
        except KeyError:
            print('ERROR: monitor is not valid')
            sys.exit(1)

        cachet = CachetHq(
            cachet_api_key=website_config['cachet_api_key'],
            cachet_url=website_config['cachet_url'],
        )

        if 'component_id' in website_config:
            cachet.update_component(
                website_config['component_id'],
                int(monitor.get('status'))
            )

        list_resp=monitor.get('response_times')
        metric = cachet.set_data_metrics(
            list_resp[0]['value'],
            monitor.get('status'),
            int(time.time()),
            website_config['metric_id']
        )
        if debug:
            print('Metric created: {0}'.format(metric))

    def update(self):
        """ Update all monitors uptime and status.
        """
        uptime_robot = UptimeRobot(self.api_key,self.base_url)
        success, response = uptime_robot.get_monitors()
        if success and debug:
            monitors = response.get('monitors')
            for monitor in monitors:
                if monitor['url'] in self.monitor_list:
                    if debug:
                        print('Updating monitor {0}. URL: {1}. ID: {2}. STATUS: {3}'.format(
                            monitor['friendly_name'],
                            monitor['url'],
                            monitor['id'],
                            monitor['status'],
                        ))
                    self.send_data_to_catchet(monitor)
        if not success:
            print('ERROR: No data was returned from UptimeMonitor')


if __name__ == "__main__":
    CONFIG = configparser.ConfigParser()
    CONFIG.read(sys.argv[1])
    SECTIONS = CONFIG.sections()

    if not SECTIONS:
        print('ERROR: File path is not valid')
        sys.exit(1)

    UPTIME_ROBOT_API_KEY = None
    MONITOR_DICT = {}
    for element in SECTIONS:
        if element == 'uptimeRobot':
            uptime_robot_api_key = CONFIG[element]['UptimeRobotMainApiKey']
            uptime_robot_url = CONFIG[element]['UptimeRobotUrl']
        else:
            MONITOR_DICT[element] = {
                'cachet_api_key': CONFIG[element]['CachetApiKey'],
                'cachet_url': CONFIG[element]['CachetUrl'],
                'metric_id': CONFIG[element]['MetricId'],
            }
            if 'ComponentId' in CONFIG[element]:
                MONITOR_DICT[element].update({
                    'component_id': CONFIG[element]['ComponentId'],
                })
#        print MONITOR_DICT
    MONITOR = Monitor(monitor_list=MONITOR_DICT, api_key=uptime_robot_api_key, base_url=uptime_robot_url)
    MONITOR.update()
