from configparser import ConfigParser

commands = [
    ["user"],  # add user
    ["add"],  # add pos to order
    ["remove"],  # add all pos from given user
    ["tip"],  # add tip
    ["start"],  # start new order
    ["abort"],  # abort order
    ["end"],  # end order and distribute cut
    ["help"],
    ["print"]
    # todo: extend list/extend each list
    # todo: help string erstellen
    #   all cmds + keywords/positions/uses

]


def config(section, filename='logins.ini'):
    """
    It reads a section from a configuration file and returns a dictionary of the parameters and their values

    :param section: The section of the config file to read
    :param filename: The name of the file that contains the configuration, defaults to logins.ini (optional)
    :return: A dictionary of the configs
    """
    parser = ConfigParser()
    parser.read(filename)

    configs = {}
    if parser.has_section(section):
        params = parser.items(section)
        for param in params:
            configs[param[0]] = param[1]
    else:
        raise Exception('Section {0} not found in the {1} file'.format(section, filename))

    return configs
