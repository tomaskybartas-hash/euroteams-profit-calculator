from sqlalchemy import create_engine,MetaData,Table,Column,Integer,String,select
import pytest
from collector.database_transfer import transfer


def test_transfer_preserves_data_and_refuses_overwrite():
    schema=MetaData()
    table=Table('records',schema,Column('id',Integer,primary_key=True),Column('value',String))
    source=create_engine('sqlite://');target=create_engine('sqlite://')
    schema.create_all(source)
    with source.begin() as c:c.execute(table.insert(),[{'id':7,'value':'Žardininkų <>&'},{'id':11,'value':'unchanged'}])
    result=transfer(source,target,schema)
    assert result=={'status':'VERIFIED','counts':{'records':2}}
    assert transfer(source,target,schema)['status']=='ALREADY_VERIFIED'
    with source.begin() as c:c.execute(table.insert(),{'id':12,'value':'new source record'})
    with pytest.raises(RuntimeError,match='TRANSFER_TARGET_NOT_EMPTY'):transfer(source,target,schema)
    with target.connect() as c:assert c.execute(select(table)).all()==[(7,'Žardininkų <>&'),(11,'unchanged')]


def test_transfer_refuses_unaccounted_source_tables():
    schema=MetaData();Table('records',schema,Column('id',Integer,primary_key=True))
    source=create_engine('sqlite://');target=create_engine('sqlite://')
    schema.create_all(source)
    with source.begin() as c:c.exec_driver_sql('CREATE TABLE unexpected (id INTEGER)')
    with pytest.raises(RuntimeError,match='TRANSFER_SCHEMA_MISMATCH'):transfer(source,target,schema)
