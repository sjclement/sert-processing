import numpy as np
import pandas as pd
import xml.etree.ElementTree as ET
import json
import datetime

def process_results_xml(filepath):
    tree = ET.parse(filepath)
    root = tree.getroot()
    metrics = parse_results(root)
    scores = parse_summary(root.find('run-data/summary'))
    env = parse_test_environment(root)
    return metrics, scores, env

def parse_results(root_el):
    results = []
    for workload in root_el.findall('run-data/workload'):
        workload_type = workload.get('name')
        worklet_results = parse_worklets(workload)
        for r in worklet_results:
            r.update( {'workload': workload_type} )
        results.extend(worklet_results)

    return results

def parse_worklets(workload_el):
    result = []
    for worklet in workload_el.findall('worklet'):
        benchmark =  worklet.get('name')
        result.extend(parse_test(worklet))
    return result

def parse_test(worklet_el):
    worklet_result = []
    for phase in worklet_el.iter('phase'):
        if phase.get('type') == 'measurement':
            for test in phase.findall('sequence/interval'):
                test_results = {}
                interval = test.attrib['name']
                metrics = parse_metrics(interval, test.find('result'))
                metrics['score'] = parse_score(test.find('result'))
                metrics['loadlevel'] = interval
                metrics['worklet'] = worklet_el.get('name')
                worklet_result.append(metrics)
        elif phase.get('type') == 'calibration':
            worklet_result.append({'loadlevel': 'calibration', 
                                   'worklet': worklet_el.get('name'),
                                   'score': float(phase.find('calibrationResult/transactionsPerSecond').text)})

    return worklet_result


def parse_score(test_el):
    return float(test_el.find('score').text)

def parse_metrics(loadlevel, test_el):
    metrics = {}
    for m in test_el.find('metrics').iter('provider'):
        for m_type in m:
            if m_type.tag == 'timing':
                # SERT time format not consistent
                try:
                    metrics["start"] = datetime.datetime.strptime(m_type.find('interval/started').text, '%Y-%m-%dT%H:%M:%S.%f%z')
                except ValueError:
                    metrics["start"] = datetime.datetime.strptime(m_type.find('interval/started').text, '%Y-%m-%dT%H:%M:%S%z')

                try:
                    metrics["end"] = datetime.datetime.strptime(m_type.find('interval/ending').text, '%Y-%m-%dT%H:%M:%S.%f%z')
                except ValueError:
                    metrics["end"] = datetime.datetime.strptime(m_type.find('interval/ending').text, '%Y-%m-%dT%H:%M:%S%z')
            elif m_type.tag == 'temperature-sensor':
                metrics["temp-min"] = float(m_type.find('measurement/temperature/minimum').text)
                metrics["temp-max"] = float(m_type.find('measurement/temperature/maximum').text)
                metrics["temp-avg"] = float(m_type.find('measurement/temperature/average').text)
            elif m_type.tag == 'power-analyzer':
                metrics["watts-min"] = float(m_type.find('measurement/watts/minimum').text)
                metrics["watts-max"] = float(m_type.find('measurement/watts/maximum').text)
                metrics["watts-avg"] = float(m_type.find('measurement/watts/average').text)
            
    return metrics

def parse_summary(summary_el):
    results = []
    for workload in summary_el.findall('workload'):
        results += parse_worklet_summary(workload)
        results.append({'workload': workload.get('name'), 'efficiency-score': float(workload.find('score').text)})
    results.append({'workload': 'All', 'efficiency-score': float(summary_el.find('score').text)})
    return results

def parse_worklet_summary(workload_el):
    result = []
    for worklet in workload_el.findall('worklet'):
        result += parse_test_summary(worklet, workload_el.get('name'))
        result.append({'workload': workload_el.get('name'), 'worklet': worklet.get('name'), 'efficiency-score':float(worklet.find('score').text)})
    return result

def parse_test_summary(worklet_el, workload_name):
    scores = []
    for load in worklet_el.findall('loadLevel'):
        scores.append({
            'workload': workload_name,
            'worklet': worklet_el.get('name'),
            'loadlevel': load.get('name'),
            'score': float(load.find('performance-score').text),
            'norm-score': float(load.find('normalized-performance').text),
            'watts-avg': float(load.find('average-watts').text),
            'ref-score': float(worklet_el.find('reference-performance').text),
            'efficiency-score': 1000 * float(load.find('normalized-performance').text) / float(load.find('average-watts').text)
        })
    return scores

def parse_test_environment(root_el):
    env = {}
    hardware_el = root_el.find('{http://spec.org/test-environment}TestEnvironment/{http://spec.org/test-environment}SystemUnderTest/{http://spec.org/test-environment}Node/{http://spec.org/test-environment}Hardware')
    if hardware_el:
        env['vendor'] = hardware_el.find('{http://spec.org/test-environment}Vendor').text
        env['model'] = hardware_el.find('{http://spec.org/test-environment}Model').text
        env['cpu'] = hardware_el.find('{http://spec.org/test-environment}Cpu/{http://spec.org/test-environment}Name').text
        env['dimms'] = int(hardware_el.find('{http://spec.org/test-environment}Memory/{http://spec.org/test-environment}Dimms/{http://spec.org/test-environment}Quantity').text)
        env['dimm_size_mb'] = hardware_el.find('{http://spec.org/test-environment}Memory/{http://spec.org/test-environment}Dimms/{http://spec.org/test-environment}DimmSizeMB').text
        env['psu'] = hardware_el.find('{http://spec.org/test-environment}PowerSupplies/{http://spec.org/test-environment}PowerSupply/{http://spec.org/test-environment}RatingInWatts').text
        env['ref'] = root_el.find('{http://spec.org/test-environment}TestEnvironment/{http://spec.org/test-environment}TestInformation/{http://spec.org/test-environment}InternalReference').text
    
    host_el = root_el.find('run-data/host')
    if host_el:
        env['hostname'] = host_el.get('id')
        env['logical_cores'] = int(host_el.find('cpu-info/logical-core-count').text)
        env['physical_cores'] = int(host_el.find('cpu-info/physical-core-count').text)
        env['numa_nodes'] = int(host_el.find('cpu-info/numa-node-count').text)
        
    return env

def merge(a, b, path=None):
    "merges b into a"
    if path is None: path = []
    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                merge(a[key], b[key], path + [str(key)])
            elif a[key] == b[key]:
                pass # same leaf value
            else:
                raise Exception('Conflict at %s' % '.'.join(path + [str(key)]))
        else:
            a[key] = b[key]
    return a






def test_time_period(filepath):
    tree = ET.parse(filepath)
    root = tree.getroot()
    test_periods = {}
    
    for m in root.find('run-data/metrics').iter('provider'):
        if m.get('id') == 'timing':
            for t in m.find('timing').find('suite').iter():
                if t.tag != 'suite':
                    test_periods[t.tag] = t.text
    
    return test_periods['starting'], test_periods['ending']
    
def get_run_configuration(filepath):
    tree = ET.parse(filepath)
    root = tree.getroot()
    
    conf = {}
    for c in root.findall('run-data/powns:configuration/powns:suite/powns:client-configuration', namespaces={'powns':'http://spec.org/power_chauffeur'}):
        conf['client'] = c.get('id')
    
    os = ''
    for e in root.findall('envns:TestEnvironment/envns:SystemUnderTest/envns:Node/envns:Software/envns:OperatingSystem/envns:Name', namespaces={'envns': 'http://spec.org/test-environment'}):
        conf['os'] = e.text
    
    jvm = ''
    for e in root.findall('envns:TestEnvironment/envns:SystemUnderTest/envns:Node/envns:Software/envns:JVM/envns:Version', namespaces={'envns': 'http://spec.org/test-environment'}):
        conf['jvm'] = e.text
        
    return conf


if __name__ == '__main__':

    
    results = process_results_xml('results/sert-0007-roomtemp/results.xml')    

    with open('out.json', 'w') as fd:
        json.dump(results, fd)
        
