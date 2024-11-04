# a utilty to get a report

import sys
import platform
import logging
import sqlalchemy

# set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


def main():
    from app.models import Analysis
    from config import Config
    from app import create_app

    config = Config() 
    app = create_app()

    # required the first parameter be the analysis_id or sha256 hash
    if len(sys.argv) < 2:
        logging.error("Usage: python report.py <analysis_id> | <sha256>")
        sys.exit(1)
    
    arg1 = sys.argv[1]
    with app.app_context():
        if len(arg1) == 64:
            analysis = Analysis.query.filter_by(sample=arg1).first()
        else:
            analysis = Analysis.query.filter_by(id=arg1).first()

        if analysis is None:
            logging.error(f"Analysis not found: {arg1}")
            sys.exit(1)

        if len(sys.argv) == 3 and sys.argv[2] == '--report':
            try:
                with open(analysis.report, 'r') as f:
                    print(f.read())
            except Exception as e:
                logging.error(f"Error reading report: {e}")
            return

        print(f"Analysis ID: {analysis.id}")
        print(f"SHA256: {analysis.sample}")
        print(f"Status: {analysis.status}")
        print(f"Error message: {analysis.error_message}")
        print(f"VM: {analysis.analysis_vm}")
        print(f"Date Updated: {analysis.date_updated}")
        print(f"Report Path: {analysis.report}")
        print("\nTo view the report, run again with --report flag")

        
if __name__ == '__main__':
    main()