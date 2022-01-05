"""Atomic Processing Utils"""

from src.constants import DATA_ROOT, PNAME_PLACEHOLDER_RE, PNAME_SUB

from functools import partial
from glob import iglob
from random import choice
import re
from typing import Dict, List, NamedTuple, Tuple

import pandas as pd

read_tsv = partial(pd.read_csv, sep='\t', encoding='utf8', header=None)
Dataframe = pd.DataFrame


class Relation(NamedTuple):
    relation: str
    tail: str


def load_atomic_data(glob_path: str = f'{DATA_ROOT}/atomic/*.tsv',
                     save: bool = False) -> Dataframe:
    """Load atomic dataset from glob path

    Args:
        glob_path - path to atomic folder
        save - if true saves dataframe to disk

    Returns:
        atomic dataframe
    """

    data_dict = {'head': [], 'relation': [], 'tail': []}

    for file in iglob(glob_path, recursive=False):
        if file.endswith('processed.tsv'): continue
        print(file)
        tmp = read_tsv(file, low_memory=False)
        for i, k in enumerate(data_dict.keys()):
            # retrieve columns and put them into data_dict
            data_dict[k].extend(tmp.iloc[:, i].tolist())

    df = Dataframe.from_dict(data_dict).reset_index().set_index('index')
    if save:
        df_path = f'{DATA_ROOT}/atomic/processed.tsv'
        serialized = f'{DATA_ROOT}/atomic/atomic.pickle'
        print('Saving dataframe to ', df_path)
        df.to_pickle(serialized)
        df.to_csv(df_path, sep='\t', encoding='utf8')
        print('data saved')

    return df


def physical_entity_attributes(
        atomic: Dataframe) -> Tuple[Dataframe, Dataframe]:
    """Extracts physical and entity attributes from Atomic
    
    Args:
        atomic - atomic dataframe

    Returns:
        dataframe only containing physical-entity attributes
    """
    phy_attrs = ['ObjectUse', 'AtLocation', 'MadeUpOf', 'HasProperty']
    ent_attrs = ['CapableOf', 'Desires', 'NotDesires']

    phy_frame = atomic[~atomic['relation'].isin(phy_attrs)]
    ent_frame = atomic[~atomic['relation'].isin(ent_attrs)]

    return (phy_frame, ent_frame)


def social_attributes(atomic: Dataframe) -> Dataframe:
    """Extracts social attributes from Atomic
    
    Args:
        atomic - atomic dataframe

    Returns:
        dataframe only containing social attributes
    """
    attrs = [
        'xNeed', 'xAttr', 'xEffect', 'xReact', 'xWant', 'xIntent', 'oEffect',
        'oReact', 'oWant'
    ]

    df = atomic[~atomic['relation'].isin(attrs)]

    return df


def event_attributes(atomic: Dataframe) -> Tuple[Dataframe, Dataframe]:
    """Extracts event attributes from Atomic
    
    Args:
        atomic - atomic dataframe

    Returns:
        dataframe only containing event attributes
    """
    script_attrs = ['isAfter', 'isBefore', 'HasSubevent']
    dynamic_attrs = ['Causes', 'HinderedBy', 'xReason']
    script_frame = atomic[~atomic['relation'].isin(script_attrs)]
    dyna_frame = atomic[~atomic['relation'].isin(dynamic_attrs)]

    return (script_frame, dyna_frame)


def collect_sample(from_head: str,
                   atomic: Dataframe) -> Dict[str, List[Relation]]:
    """Searches atomic dataframe for head

    Args:
        from_head - string to query
        atomic - atomic dataframe

    Returns:
        dict of head with entries of head
    """
    df = atomic[atomic['head'] == from_head]

    return {
        from_head: [
            Relation(r, t)
            for r, t in zip(df['relation'].tolist(), df['tail'].tolist())
        ]
    }


def connect_entries(atomic: Dataframe) -> Dataframe:
    """Collects all rows with same event and saves it into a new dataframe

    Args:
        atomic: dataframe

    Returns:
        new organized dataframe
    """
    raise NotImplementedError()


def fill_placeholders(atomic: Dataframe,
                      columns: List[str] = ['head', 'tail']) -> Dataframe:
    """Fills placeholder values Person {X, Y, Z} with an arbitrary `pname`

    Args:
        atomic - atomic dataframe
        columns - columns to process

    Returns:
        dataframe with replaced names
    """
    df = atomic
    names = PNAME_SUB

    def replace(x: str, placeholder: str, replace_with: str) -> str:
        if isinstance(x, str) and re.search(placeholder, x) is not None:
            s = re.sub(placeholder, replace_with, x)
            return s
        return x

    for i in PNAME_PLACEHOLDER_RE:
        rex = re.compile(i, flags=re.IGNORECASE)
        name = choice(names)

        for col in columns:
            df[col] = df[col].apply(
                lambda x: replace(x, placeholder=rex, replace_with=name))

        # do not allow duplicate names
        names.remove(name)
        re.purge()

    return df


def parse(atomic: Dataframe, parse_type: str, save: bool = True) -> Dataframe:
    """Apply parse function on atomic heads

    Args:
        atomic - atomic dataframe
        parse_type - possible parse types: srl, dp
        save - if true saves dataframe to disk

    Returns:
        dataframe with added parse column
    """
    assert parse_type in ['srl', 'dp',
                          'dep'], 'Parse type supplied not implemented'

    if parse_type == 'srl':
        from src.nlp import srl
        fn = srl
        del srl
    else:
        from src.nlp import dependency_parse as dp
        fn = dp
        del dp

    df = atomic
    print(f'Start {parse_type} parsing')
    parses = [fn(head) for head in df['head']]
    df[parse_type] = parses
    if save: df.to_pickle(f'{DATA_ROOT}/atomic/parse.pickle')
    return df


def find_relation(atomic: Dataframe):
    raise NotImplementedError()


# Testing area
if __name__ == "__main__":
    atomic = load_atomic_data(save=False)
    atomic = fill_placeholders(atomic)
    atomic.to_csv('tmp.tsv', sep='\t', encoding='utf8')
    # srl_parse(atomic, True)
    # parse(atomic, 'dep', save=False)
    #s = 'PersonX adopts a cat'
    #sample = collect_sample(s, atomic)
    #__import__('pprint').pprint(srl(s))
