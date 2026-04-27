from configparser import ConfigParser


def config(filename='config/database.ini', section='air_db'):
    # create a parser
    parser = ConfigParser()
    # read config file
    parser.read(filename)

    # get section, default to postgresql
    db = {}

    int_params = ['h', 'w', 'max_steps', 'embedding_size']

    # Checks to see if section parser exists
    if parser.has_section(section):
        params = parser.items(section)
        for param in params:
            param_name = param[0]
            value = param[1]
            if param_name in int_params:
                db[param_name] = int(value)
            else:
                db[param_name] = value

    # Returns an error if a parameter is called that is not listed in the initialization file
    else:
        raise Exception('Section {0} not found in the {1} file'.format(section, filename))

    return db