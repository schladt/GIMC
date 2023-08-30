"""
Script to collect logs form windows system with sysmon installed
"""
import win32evtlog
import json
import xml.etree.ElementTree as ET

def eventlog_to_dict(logtype='Application', computer='.'):
    logs = []
    flags = win32evtlog.EvtQueryChannelPath | win32evtlog.EvtQueryForwardDirection
    handle = win32evtlog.EvtQuery(logtype, flags)
    
    while True:
        events = win32evtlog.EvtNext(handle, 10)  # Retrieve 10 events at a time
        if len(events) == 0:
            break
        for event in events:
            xml_content = win32evtlog.EvtRender(event, win32evtlog.EvtRenderEventXml)
            event_data = xml_to_dict(xml_content)
            logs.append(event_data)
    return logs

def xml_to_dict(xml_content):
    """Convert XML content to a Python dictionary."""
    ns = '{http://schemas.microsoft.com/win/2004/08/events/event}'
    xml = ET.fromstring(xml_content)

    def element_to_dict(element):
        """Recursively convert an XML element to a dictionary."""
        # For elements with text, just return the text
        if element.text and element.text.strip():
            return element.text.strip()

        # For elements with children, convert each child and add to dictionary
        child_dict = {}
        for child in element:
            child_name = child.tag.replace(ns, '')  # Remove the namespace

            # Special handling for Sysmon logs: use the "Name" attribute as the dictionary key for <Data> elements
            if child_name == 'Data' and 'Name' in child.attrib:
                child_name = child.attrib['Name']

            child_dict[child_name] = element_to_dict(child)

        # Include attributes in the dictionary
        for key, value in element.attrib.items():
            child_dict['@' + key] = value

        return child_dict

    return element_to_dict(xml)

if __name__ == '__main__':
    logtype = 'Microsoft-Windows-Sysmon/Operational'
    logs = eventlog_to_dict(logtype=logtype)
    
    with open('output.json', 'w') as f:
        json.dump(logs, f, indent=4)