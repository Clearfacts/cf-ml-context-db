"""
ClearFacts-specific database connection objects.

These extend the base MySqlDatabase and PostgresDatabase classes from mlbase.db
and are pre-configured for the ClearFacts production databases.

All connection details are read from config/database.ini:

  [web_db]          — shared ClearFacts webapp MySQL database
  [client_db]       — per-client sharded MySQL databases
  [customer_model_db] — customer model PostgreSQL database

Usage:
    from debug_agent.databases import ClearfactsWebAppDatabase, ClearfactsClientDatabase, CustomerModelDatabase

    web_db = ClearfactsWebAppDatabase("config/database.ini")
    client_db = ClearfactsClientDatabase("config/database.ini", connection_number=2, client_vat_number="0543870486")
    model_db = CustomerModelDatabase("config/database.ini")
"""

from mlbase.db import MySqlDatabase, PostgresDatabase


class ClearfactsWebAppDatabase(MySqlDatabase):
    """MySQL database used by the ClearFacts web app (cf-accounting project).

    Connects to the shared cf4a_webapp database on the operations read replica.
    Connection details are read from config/database.ini, section [web_db].
    """

    def __init__(self, config_file: str, section: str = "web_db"):
        super().__init__(config_file, section)


class ClearfactsClientDatabase(MySqlDatabase):
    """Per-client MySQL databases used by the ClearFacts web app.

    Databases are sharded across multiple hosts. The host is determined by
    connection_number; the database name is derived from the client VAT number.

    Connection details are read from config/database.ini, section [client_db].
    The [client_db] host value must contain a {connection_number} placeholder,
    e.g.: host = {connection_number}.prod.db.clearfacts.be

    Args:
        config_file:       Path to the database.ini config file.
        connection_number: The shard number for this client.
        client_vat_number: The client VAT number (used as the database name, e.g. cf4a_0543870486).
        section:           Config section name (default: client_db).
    """

    def __init__(
        self,
        config_file: str,
        connection_number: int,
        client_vat_number: str,
        section: str = "client_db",
    ):
        self.connection_number = connection_number
        self.client_vat_number = client_vat_number
        super().__init__(config_file, section)

    @property
    def host(self) -> str:
        return self.params["host"].format(connection_number=self.connection_number)

    @property
    def database(self) -> str:
        return f"cf4a_{self.client_vat_number}"


class CustomerModelDatabase(PostgresDatabase):
    """PostgreSQL database used for the Customer Model.

    Holds business partner info (name + address) found in EFFF.xml for each
    client and accountbp. Used for customer model lookups during enrichment.

    Connection details are read from config/database.ini, section [customer_model_db].
    """

    def __init__(self, config_file: str, section: str = "customer_model_db"):
        super().__init__(config_file, section)




class ContextDatabase(PostgresDatabase):
    """Target database for context storage and retrieval.

    """

    def __init__(self, config_file: str, section: str = "context_db"):
        super().__init__(config_file, section)
