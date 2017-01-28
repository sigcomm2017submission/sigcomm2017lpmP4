def if_unique(name, same_name):
    if len(same_name) > 1:
        raise KeyError("{:s} is not unique".format(name))
    if len(same_name) == 0:
        raise KeyError("{:s} is not found".format(name))
    return same_name[0]


def find_unique_by_key(name, key, entries):
    return if_unique(name, [x for x in entries if x[key] == name])


def find_unique_name(name, entries):
    return find_unique_by_key(name, 'name', entries)


def index_unique_by_key(name, key, entries):
    return if_unique(name, [i for i, x in enumerate(entries) if x[key] == name])


def index_unique_name(name, entries):
    return index_unique_by_key(name, 'name', entries)


def find_unique_name_idx(name, idx, entries):
    return if_unique(name, [x for x in entries if x[idx] == name])


def _create_in_with_id(where, cls, *args):
    result = cls._create_instance(len(where), *args)  # pylint: disable=protected-access
    where.append(result._json)  # pylint: disable=protected-access
    return result


def _create_in(where, cls, *args):
    result = cls._create_instance(*args)  # pylint: disable=protected-access
    where.append(result._json)  # pylint: disable=protected-access
    return result


class Program(object):
    def __init__(self, json):
        self._json = json

    def get_pipeline(self, name):
        return Pipeline(self, json=find_unique_name(name, self._json['pipelines']))

    def get_action(self, name):
        return Action(self, json=find_unique_name(name, self._json['actions']))

    def add_action(self, name, parameters):
        return _create_in_with_id(self._json['actions'], Action, self, name, parameters)

    def get_header(self, name):
        return Header(self, json=find_unique_name(name, self._json['headers']))

    def add_header(self, name, header_type, metadata):
        return _create_in_with_id(self._json['headers'], Header, self, name, header_type, metadata)

    def get_header_type(self, name):
        return HeaderType(self, json=find_unique_name(name, self._json['header_types']))

    def add_header_type(self, name):
        return _create_in_with_id(self._json['header_types'], HeaderType, self, name)

    @property
    def pipelines(self):
        return tuple(Pipeline(self, json) for json in self._json['pipelines'])


class Action(object):
    def __init__(self, program, json):
        self._program = program
        self._json = json

    @classmethod
    def _create_instance(cls, idx, program, name, parameters):
        return cls(program, json={
            'primitives' : [],
            'runtime_data' :
                [
                    {'name': pname, 'bitwidth': pbitwidth}
                    for pname, pbitwidth in parameters.items()
                ],
            'name' : name,
            'id' : idx
        })

    @property
    def parameters(self):
        return tuple(ActionParameter(self, x) for x in self._json['runtime_data'])

    def add_primitive_call(self, name, *args):
        parameters = []
        for arg in args:
            if isinstance(arg, FieldInstance):
                parameters.append({
                    'type': 'field',
                    'value': [arg.header.name, arg.name]
                })
            elif isinstance(arg, int):
                parameters.append({
                    'type': 'hexstr',
                    'value': hex(arg)
                })
            elif isinstance(arg, basestring):
                parameters.append({
                    'type': 'runtime_data',
                    'value': index_unique_name(arg, self._json['runtime_data'])
                })
            else:
                raise ValueError('Unsupported arg type: {}'.format(type(arg)))
        self._json['primitives'].append({
            'op': name,
            'parameters': parameters
        })

    def remove_primitive_call(self, name):
        self._json['primitives'].pop(index_unique_by_key(name, 'op', self._json['primitives']))

    @property
    def name(self):
        return self._json['name']


class ActionParameter(object):
    def __init__(self, action, json):
        self._action = action
        self._json = json

    @classmethod
    def _create_instance(cls, action, name, bitwidth):
        return cls(action, json={
            'name': name,
            'bitwidth': bitwidth
        })

    @property
    def name(self):
        return self._json['name']

    @property
    def bitwidth(self):
        return self._json['bitwidth']


class HeaderType(object):
    def __init__(self, program, json):
        self._program = program
        self._json = json

    @classmethod
    def _create_instance(cls, idx, program, name):
        return cls(program, json={
            'fields' : [],
            'max_length' : None,
            'name' : name,
            'length_exp' : None,
            'id' : idx
        })

    def add_field(self, name, length):
        return _create_in(self._json['fields'], Field, self, name, length)

    def get_field(self, name):
        return Field(self, json=find_unique_name_idx(name, 0, self._json['fields']))

    @property
    def fields(self):
        return tuple(Field(self, json) for json in self._json['fields'])

    @property
    def name(self):
        return self._json['name']


class Field(object):
    def __init__(self, header_type, json):
        self._header_type = header_type
        self._json = json

    @classmethod
    def _create_instance(cls, header_type, name, length):
        return cls(header_type, json=[name, length])

    @property
    def length(self):
        return self._json[1]

    @property
    def name(self):
        return self._json[0]

    @property
    def header_type(self):
        return self._header_type


class Header(object):
    def __init__(self, program, json):
        self._program = program
        self._json = json

    @classmethod
    def _create_instance(cls, idx, program, name, header_type, metadata): # pylint: disable=too-many-arguments
        return cls(program, json={
            'name': name,
            'metadata': metadata,
            'id': idx,
            'header_type': header_type.name
        })

    @property
    def header_type(self):
        return self._program.get_header_type(self._json['header_type'])

    @property
    def name(self):
        return self._json['name']

    def get_field_instance(self, field):
        if isinstance(field, basestring):
            return FieldInstance(self, self.header_type.get_field(field))
        if field.header_type.name != self.header_type.name:
            raise ValueError('field must belong to {:s}'.format(self.header_type.name))
        return FieldInstance(self, field)

class FieldInstance(object):
    def __init__(self, header, field):
        self._header = header
        self._field = field

    def __repr__(self):
        return '{:s}.{:s}'.format(self._header.name, self._field.name)

    @property
    def length(self):
        return self._field.length

    @property
    def name(self):
        return self._field.name

    @property
    def header(self):
        return self._header

class Pipeline(object):
    def __init__(self, p4, json):
        self._p4 = p4
        self._json = json

    def add_table(self, name, match_type, max_size):
        return _create_in_with_id(self._json['tables'], Table, self, name, match_type, max_size)

    def get_table(self, name):
        return Table(self, json=find_unique_name(name, self._json['tables']))

    @property
    def tables(self):
        return tuple(Table(self, json) for json in self._json['tables'])

    @property
    def conditionals(self):
        return tuple(Conditional(self, json) for json in self._json['conditionals'])

    @property
    def program(self):
        return self._p4

class Conditional(object):
    def __init__(self, pipeline, json):
        self._pipeline = pipeline
        self._json = json

    def _get_false_next(self):
        false_next = self._json['false_next']
        if not false_next:
            return None
        return self._pipeline.get_table(false_next)

    def _set_false_next(self, table):
        self._json['false_next'] = table.name

    false_next = property(_get_false_next, _set_false_next)

    def _get_true_next(self):
        true_next = self._json['true_next']
        if not true_next:
            return None
        return self._pipeline.get_table(true_next)

    def _set_true_next(self, table):
        self._json['true_next'] = table.name

    true_next = property(_get_true_next, _set_true_next)

class Table(object):
    def __init__(self, pipeline, json):
        self._pipeline = pipeline
        self._json = json

    @classmethod
    def _create_instance(cls, idx, pipeline, name, match_type, max_size): # pylint: disable=too-many-arguments
        return cls(pipeline, json={
            'name' : name,
            'id' : idx,
            'support_timeout' : False,
            'with_counters' : False,
            'direct_meters' : None,
            'match_type' : match_type,
            'actions' : [],
            'next_tables' : {},
            'base_default_next' : None,
            'type' : 'simple',
            'max_size' : max_size,
            'key' : []
        })

    @property
    def name(self):
        return self._json['name']

    @property
    def max_size(self):
        return self._json['max_size']

    @property
    def match_type(self):
        return self._json['match_type']

    @property
    def pipeline(self):
        return self._pipeline

    def set_keys(self, *keys):
        self._json['key'] = [{
            'mask' : None,
            'match_type' : self.match_type,
            'target' : [key.header.name, key.name]
        } for key in keys]

    @property
    def actions(self):
        return tuple(self._pipeline.program.get_action(act_name) for act_name in self._json['actions'])

    def set_actions(self, *actions):
        self._json['actions'] = [action.name for action in actions]

    def set_default_next(self, table):
        if table is None:
            self._json['base_default_next'] = None
        self._json['base_default_next'] = table.name

    def get_default_next(self):
        table_name = self._json['base_default_next']
        if table_name is None:
            return None
        return self._pipeline.get_table(table_name)

    def set_next(self, action, table):
        self._json['next_tables'].update({action.name : table.name})

    def get_next(self, action):
        table_name = self._json['next_tables'][action.name]
        if table_name is None:
            return None
        return self._pipeline.get_table(table_name)

    @property
    def fields(self):
        return tuple(
            self._pipeline.program.get_header(x['target'][0]).get_field_instance(x['target'][1])
            for x in self._json['key']
        )
