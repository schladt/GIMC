"""
Utility function to load malware data
"""
import os
import json

from sqlalchemy.orm import Session
from sqlalchemy import create_engine, select, MetaData, Table, and_
from tqdm import tqdm

with open ('../settings.json') as f:
    settings = json.load(f)

db_uri = settings['sqlalchemy_database_uri']
data_dir = os.path.join(settings['data_path'], 'classifier')

def mal_tokenizer(line):
    """
    Tokenize a line of text
    """
    line = line.lower()
    line = line.replace(',', ' ')
    line = line.replace('\\', ' ')
    line = line.replace('\\\\', ' ')
    return line.split()

tokenizer = mal_tokenizer

def get_mal_data(signatures):
    return_data = []
    for signature in signatures:
        # check if json files exist
        filepath = os.path.join(data_dir, f'{signature}_reports.json')
        if not os.path.isfile(filepath):
            # connect to database
            engine = create_engine(db_uri)

            # load tables
            metadata_obj = MetaData()
            conn = engine.connect()

            Tag = Table('tag', metadata_obj, autoload_with=engine)
            SampleTag = Table('sample_tag', metadata_obj, autoload_with=engine)
            Analysis = Table('analysis', metadata_obj, autoload_with=engine)

            # Start a session
            session = Session(engine)

            reports = []
            bad_reports = []
        
            # get all reports with the tag of signature
            stmt = select(Analysis.c.report).join(SampleTag, Tag.c.id == SampleTag.c.tag_id).join(
                Analysis, SampleTag.c.sample_id == Analysis.c.sample).where(and_(
                (Tag.c.value == signature),
                (Analysis.c.status == 2)
            ))

            results = session.execute(stmt).fetchall()
            print(f"Found {len(results)} {signature} reports")
            report_paths = [r[0] for r in results] 
            # Close the session
            session.close()

            # fix report paths
            report_paths = [item.lower() for item in report_paths]

            # fetch reports
            for report_path in tqdm(report_paths, desc=f"Reading {signature} reports"):
                try:
                    with open(report_path) as f:
                        r = f.read()
                        # tag and append report
                        reports.append([r, signature])
                except:
                    bad_reports.append(report_path)
                    print(f"Error reading {signature} report: {report_path}. Error number {len(bad_reports)}")
                    continue

            # Tokenize reports
            i = 0
            for report in tqdm(reports, desc="Tokenizing reports"):
                dynamic_report = json.loads(report[0])['dynamic']
                dynamic_report_tokenized = []
                for item in dynamic_report:
                    line = f"{item['Operation']}, {item['Path']}, {item['Result']}"
                    dynamic_report_tokenized.extend(tokenizer(line))
                reports[i][0] = dynamic_report_tokenized
                i += 1

            # json dump reports to file
            print("Dumping reports to file")
            with open(f'{signature}_reports.json', 'w') as f:
                json.dump(reports, f)

            return_data.extend(reports)
        else:
            print(f"Loading {signature} reports from file")
            with open(filepath) as f:
                return_data.extend(json.load(f))

    return return_data
            
def get_raw_data(signatures):
    return_data = []
    for signature in tqdm(signatures, desc="Loading raw data"):
        # connect to database
        engine = create_engine(db_uri)

        # load tables
        metadata_obj = MetaData()
        conn = engine.connect()

        Tag = Table('tag', metadata_obj, autoload_with=engine)
        SampleTag = Table('sample_tag', metadata_obj, autoload_with=engine)
        Analysis = Table('analysis', metadata_obj, autoload_with=engine)

        # Start a session
        session = Session(engine)

        reports = []
        bad_reports = []
    
        # get all reports with the tag of signature
        stmt = select(Analysis.c.report).join(SampleTag, Tag.c.id == SampleTag.c.tag_id).join(
            Analysis, SampleTag.c.sample_id == Analysis.c.sample).where(and_(
            (Tag.c.value == signature),
            (Analysis.c.status == 2)
        ))

        results = session.execute(stmt).fetchall()
        print(f"Found {len(results)} {signature} reports")
        report_paths = [r[0] for r in results] 

        # fix report paths
        report_paths = [item.lower() for item in report_paths]
        
        # Close the session
        session.close()

        # fetch reports
        for report_path in tqdm(report_paths, desc=f"Reading {signature} reports"):
            try:
                with open(report_path) as f:
                    r = f.read()
                    # tag and append report
                    reports.append({'id': signature, 'text': r})
            except:
                bad_reports.append(report_path)
                print(f"Error reading {signature} report: {report_path}. Error number {len(bad_reports)}")
                continue
        return_data.extend(reports)
    return return_data
    