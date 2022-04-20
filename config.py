from configparser import ConfigParser

commands = [
    ["user"],   #add user
    ["add"],    #add pos to order
    ["remove"], #add all pos from given user
    ["tip"],    #add tip
    ["start"],  #start new order
    ["abort"],  #abort order
    ["end"]     #end order and distribute cut

]


def config(section, filename='logins.ini'):
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
