import xml.etree.ElementTree as ET
from collections import defaultdict
import json 
import argparse

def main():
    # parser with arguments for raw xml file and target process name
    parser = argparse.ArgumentParser(description='Parse raw xml file.')
    parser.add_argument('xml_file', type=str, help='raw xml file')
    parser.add_argument('process_name', type=str, help='target process name')
    args = parser.parse_args()

    tree = ET.parse(args.xml_file)
    root = tree.getroot()

    # find the test process
    root_pid = None
    process_list = root[0]
    for process in process_list:
        process_name = process[11].text
        if args.process_name in process_name:
            root_pid = process[1].text.strip()
            for sub_element in process:
                print(sub_element.tag, ": ", sub_element.text)

    if root_pid is None:
        print("No process found with name: ", args.process_name)
        return

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
  
    event_dict = etree_to_dict(target_events)

    # save event dict to json file
    with open('events.json', 'w') as outfile:
        json.dump(event_dict, outfile, indent=4)

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

if __name__ == "__main__":
    main()