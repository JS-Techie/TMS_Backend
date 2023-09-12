from sqlalchemy import MetaData, Table, Column, UUID, text, ForeignKey, Double, Integer, DateTime, Boolean, String

from config.db_config import engine
from models.models import Base


def generate_tables():
    try:

        Base.metadata.create_all(engine)
        print("Tables created successfully!")

    except Exception as e:

        print("Error creating tables:", str(e))


def append_model_to_file(model_code):
    with open('models/models.py', 'a') as model_file:
        model_file.write(model_code)


async def get_table_and_model(table_name: str):

    metadata = MetaData()

    try:

        table = Table(
            table_name, metadata,
            id=Column(UUID(as_uuid=True), primary_key=True,
                      server_default=text('gen_random_uuid()')),
            transporter_id=Column(UUID(as_uuid=True), ForeignKey(
                't_transporter.trnsp_id'), nullable=False),
            rate=Column(Double, nullable=False),
            comment=Column(String, nullable=False),
            attempt_number=Column(Integer, nullable=False),
            created_at=Column(DateTime, nullable=False,
                              server_default=text("now()")),
            created_by=Column(UUID(as_uuid=True), ForeignKey(
                't_user.user_id'), nullable=False),
            updated_at=Column(DateTime, nullable=True),
            updated_by=Column(UUID(as_uuid=True), ForeignKey(
                't_user.user_id'), nullable=True),
            is_active=Column(Boolean, nullable=False, default=True),
        )

        metadata.create_all(engine)

        print("TABLE CREATED : ", table, " [OK]")

        model_code = f"""
            class {table_name.capitalize()}(Base,Persistance):
                 __tablename__ = '{table_name}'
                id = Column (UUID(as_uuid=True), primary_key=True,server_default=text('gen_random_uuid()')),
                transporter_id = Column(UUID(as_uuid=True),ForeignKey('t_transporter.trnsp_id'),nullable=False),
                rate = Column(Double,nullable=False),
                comment = Column(String,nullable=False),
                attempt_number = Column(Integer,nullable=False),
            """

        return (True, model_code)
    except Exception as e:
        return False, str(e)
    finally:
        engine.dispose()


def get_bid_model_name(bid_id: str) -> str:
    bid_id = bid_id.replace("-", "")
    return f'T_{bid_id}'
