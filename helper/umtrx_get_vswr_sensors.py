#!/usr/bin/env python
# -*- coding: utf-8 -*-

from umtrx_property_tree import umtrx_property_tree

##########################
# Functions
##########################


def avg(l):
    return reduce(lambda x, y: x + y, l) / len(l)


##########################
# Query sensors
##########################

NUM_AVG = 5

s = umtrx_property_tree()
s.connect()

sensors_path = "/mboards/0/sensors"
res = s.list_path_raw(sensors_path)
sensors_list = res.get('result', [])

for num in [1, 2]:
    vpr_name = 'voltagePR' + str(num)
    vpf_name = 'voltagePF' + str(num)
    if vpr_name in sensors_list and vpf_name in sensors_list:
        vpr = []
        vpf = []
        for i in range(NUM_AVG):
            vpr.append(float(s.query_sensor_value(
                sensors_path + '/' + vpr_name)))
            vpf.append(float(s.query_sensor_value(
                sensors_path + '/' + vpf_name)))
        print "%5.2f" % avg(vpf)
        print "%5.2f" % avg(vpr)

s.close()
