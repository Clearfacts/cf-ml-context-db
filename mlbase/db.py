from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
import pandas as pd
from mlbase import config
from typing import Dict, Any, Optional, List


import os
import socket

def get_host_ip(env_var_name: str, host_name: str) -> str:
    """
    Returns the value of the environment variable `env_var_name` if it exists.
    If not, resolves the IP address for `host_name`, stores it in the environment variable,
    and returns the IP address.
    """
    ip = os.environ.get(env_var_name)
    if ip:
        return ip
    ip = socket.gethostbyname(host_name)
    os.environ[env_var_name] = ip
    return ip


def _get_password(params):  
    if "env_variable" in params:
        # if the config file specifies an env variable, use that
        pwd_env_name = params["env_variable"]
        if pwd_env_name not in os.environ:
            raise ValueError(f"Environment variable {pwd_env_name} not set. Please set it to the database password. or define a password in the config file.")
        return os.getenv(pwd_env_name)
    elif "password" not in params:
        raise ValueError("No password found in the config file and no environment variable specified. Please set the 'password' or 'env_variable' value in the config file")   
    else:
        return params["password"]

class PostgresDatabase():

    def __init__(self, config_filename, section, print_queries=False):
        params = config.config(config_filename, section=section)
        self.params = params
        
        self.params['password'] = _get_password(self.params)
        self.print_queries = print_queries
        db_connection_string = self._connection_string()
        
        self.engine = create_engine(db_connection_string, poolclass=NullPool)
        #self.conn = self.engine.raw_connection()

    def _connection_string(self):
        return f"postgresql+psycopg2://{self.params['user']}:{self.params['password']}@{self.params['host']}:5432/{self.params['database']}"

    def raw_connection(self):
        return self.engine.raw_connection()

    def close(self):
        #self.conn.close()
        self.engine.dispose()



class MlDatabaseDao(PostgresDatabase):
    """
    Database class used by cf-ml-common
    """

    def __init__(self, config_file: str, section: str = "air_db"):
        super().__init__(config_file, section)
        
    


    
class MySqlDatabase():

    def __init__(self, config_file, section):
        self.params = config.config(config_file, section)
        
        self.ip = get_host_ip(f'DB_HOST_IP_{section}', self.host)
        db_connection_string = f"mysql+pymysql://{self.user}:{self.password}@{self.ip}:3306/{self.database}?charset=utf8mb4"
        #self.engine = create_engine(db_connection_string, encoding='utf8', poolclass=NullPool)
        self.engine = create_engine(db_connection_string,  poolclass=NullPool)
    
    @property
    def host(self):
        return self.params['host']
    
    @property
    def database(self):
        return self.params['database']
    
    @property
    def user(self):
        return self.params['user']
    
    @property
    def password(self):
        return _get_password(self.params)
        
    def raw_connection(self):
        return self.engine.raw_connection()
        
    def close(self):
        self.engine.dispose()    


    
