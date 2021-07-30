import numpy as np
import pandas as pd
import xml.etree.ElementTree as ET
import json

def process_results_xml(filepath):
    tree = ET.parse(filepath)
    root = tree.getroot()
    results = parse_results(root)
    scores = parse_summary(root.find('run-data/summary'))
    return merge(results, scores)

def parse_results(root_el):
    results = {}
    for workload in root_el.findall('run-data/workload'):
        workload_type = workload.get('name')
        results[workload_type] = parse_worklets(workload)

    return results

def parse_worklets(workload_el):
    result = {}
    for worklet in workload_el.findall('worklet'):
        benchmark =  worklet.get('name')
        result[benchmark] = parse_test(worklet)
    return result

def parse_test(worklet_el):
    worklet_result = {}
    for phase in worklet_el.iter('phase'):

        if phase.get('type') == 'measurement':
            for test in phase.findall('sequence/interval'):
                interval = test.attrib['name']
                worklet_result[interval] = parse_metrics(test.find('result'))
                #worklet_result[interval]['score'] = parse_score(test.find('result'))
        elif phase.get('type') == 'calibration':
            for calibration in phase.findall('calibrationResult'):
                worklet_result['calibration'] = calibration.find('transactionsPerSecond').text

    return worklet_result


def parse_score(test_el):
    return test_el.find('score').text

def parse_metrics(test_el):
    metrics = {}
    for m in test_el.find('metrics').iter('provider'):
        for m_type in m:
            if m_type.tag == 'power-analyzer':
                metrics['power'] = {}
                for t in m_type.find('measurement').find('watts').iter():
                    if t.tag != 'watts':
                        metrics['power'][t.tag] = t.text
            elif m_type.tag == 'timing':
                metrics['timing'] = {}
                for t in m_type.find('interval').iter():
                        if t.tag != 'interval':
                            metrics['timing'][t.tag] = t.text
            elif m_type.tag == 'temperature-sensor':
                metrics['temperature'] = {}
                for t in  m_type.find('measurement').find('temperature'):
                    if t.tag != 'temperature':
                        metrics['temperature'][t.tag] = t.text
            
    return metrics

def parse_summary(summary_el):
    results = {}
    for workload in summary_el.findall('workload'):
        results[workload.get('name')] = parse_worklet_summary(workload)
        results[workload.get('name')]['workload-efficiency'] = workload.find('score').text
    return results

def parse_worklet_summary(workload_el):
    result = {}
    for worklet in workload_el.findall('worklet'):
        name = worklet.get('name')
        result[name] = parse_test_summary(worklet)
        result[name]['ref-score'] = worklet.find('reference-performance').text
        result[name]['worklet-efficiency'] = worklet.find('score').text
    return result

def parse_test_summary(worklet_el):
    scores_all = {}
    for load in worklet_el.findall('loadLevel'):
        scores = {}
        for t in load.iter():
            if not t.text.isspace():
                scores[t.tag] = t.text
        scores_all[load.get('name')] = scores
    return scores_all

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
        
