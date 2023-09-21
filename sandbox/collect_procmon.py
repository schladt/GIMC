import xml.etree.ElementTree as ET
from collections import defaultdict
import json 
import argparse
import csv

def etree_to_dict(t):
    """Convert an ElementTree or Element into a dictionary."""
    d = {t.tag: {} if t.attrib else None}
    children = list(t)
    if children:
        dd = defaultdict(list)
        for dc in map(etree_to_dict, children):
            for k, v in dc.items():
                dd[k].append(v)
        d = {t.tag: {k: v[0] if len(v) == 1 else v for k, v in dd.items()}}
    if t.attrib:
        d[t.tag].update(('@' + k, v) for k, v in t.attrib.items())
    if t.text:
        text = t.text.strip()
        if children or t.attrib:
            if text:
                d[t.tag]['#text'] = text
        else:
            d[t.tag] = text
    return d

def collect_events_full(target_process_name, xml_file):
    """Collects events from raw xml file with full stack tace and return as python dict.

    Args:
    - target_process_name (str): target process name
    - xml_file (str): raw xml file
    
    Returns:
    - dict: event dict
    """

    tree = ET.parse(xml_file)
    root = tree.getroot()

    # find the test process
    root_pid = None
    process_list = root[0]
    for process in process_list:
        process_name = process[11].text
        if target_process_name in process_name:
            root_pid = process[1].text.strip()
            for sub_element in process:
                print(sub_element.tag, ": ", sub_element.text)

    if root_pid is None:
        print("No process found with name: ", target_process_name)
        return None

    # find all process spawned by root_pid
    prev_len = 0
    target_pids = set()
    target_pids.add(root_pid)
    while len(target_pids) != prev_len:
        prev_len = len(target_pids)
        for process in process_list:
            if process[2].text.strip() in target_pids:
                target_pids.add(process[1].text.strip())

    # events with pid in target_pids
    events = root[1]
    target_events = ET.Element('root')
    for child in events:
        pid = child[3].text.strip()
        if pid in target_pids:
            target_events.append(child)
  
    return etree_to_dict(target_events)

def collect_events(target_process_name, csv_file):
    """Collects events from raw csv file and return as python dict. Deos not include full stack trace.

    Args:
    - target_process_name (str): target process name
    - csv_file (str): raw csv file
    
    Returns:
    - dict: event dict
    """

    # read csv file
    raw_data = None
    with open(csv_file, mode='r', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file)
        raw_data = [row for row in reader]

    if raw_data is None:
        print("Failed to read csv file")
        return None
    
    # filter process events by target process name
    target_data = [row for row in raw_data if target_process_name.lower() in row['Process Name'].lower()]

    return target_data


if __name__ == "__main__":
    # parser with arguments for raw report file and target process name
    parser = argparse.ArgumentParser(description='Parse raw xml file.')
    parser.add_argument('report_file', type=str, help='raw report file')
    parser.add_argument('process_name', type=str, help='target process name')
    parser.add_argument('--output', type=str, help='output json file', default='procmon_report.json')
    parser.add_argument('--full', action='store_true', help='Collect full stack traces for each event', default=False)
    args = parser.parse_args()

    # collect events from raw xml file and save them to json file

    event_dict = None
    if args.full:
        event_dict = collect_events_full(args.process_name, args.report_file)
    else:
        event_dict = collect_events(args.process_name, args.report_file)

    # save event dict to json file
    if event_dict is None:
        print("No events found")
    else:
        with open( args.output, 'w') as outfile:
            json.dump(event_dict, outfile, indent=4)