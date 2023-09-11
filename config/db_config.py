from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

import os

engine = create_engine(os.getenv("DB_URL"), echo=True, future=True)
Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()






