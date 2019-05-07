import math

import pandas as pd
from cellphonedb.tools.interactions_helper import _only_uniprots_in_df
from cellphonedb.tools.tools_helper import normalize_interactions


def parse_interactions_imex(interactions_base_df, protein_df, gene_df):
    """
    Parses interactions list from IMEx data file.
    Steps:
        1. Get Uniprot values from columns A and B
        2. Get Uniprot values from ensembl in column altA and altB

        3. Remove duplicated interactions:
            - Remove permutated interactions. i.e.:
                    A->B        A->B
                    B->A    =>  A->B
                    A->B        A->B
            - Remove duplicated interactions and merge scores:
                Get maximum score value.
                Intact-score prevails over innatedb score (step 3).

    """
    interactions_base_df.dropna(how='any', subset=['A', 'B'], inplace=True)

    custom_interactions = pd.DataFrame()

    custom_interactions['a_raw_data'] = interactions_base_df['A']
    custom_interactions['b_raw_data'] = interactions_base_df['B']
    custom_interactions['a_raw_ensembl'] = interactions_base_df['altA']
    custom_interactions['b_raw_ensembl'] = interactions_base_df['altB']

    custom_interactions['protein_1'] = interactions_base_df[
        interactions_base_df['A'].apply(lambda value: value.split(':')[0] == 'uniprotkb')]['A'].apply(
        lambda value: value.split(':')[1].split('-')[0])

    custom_interactions['protein_2'] = interactions_base_df[
        interactions_base_df['B'].apply(lambda value: value.split(':')[0] == 'uniprotkb')]['B'].apply(
        lambda value: value.split(':')[1].split('-')[0])

    custom_interactions['source'] = interactions_base_df['provider']

    custom_interactions['raw_score'] = interactions_base_df['confidenceScore']  # .apply(extract_score)

    # Extract ensembl for a_raw_ensembl data. Only if value is not null and has ensembl: prefix
    custom_interactions['ensembl_1'] = custom_interactions.dropna(subset=['a_raw_ensembl'])[
        custom_interactions.dropna(subset=['a_raw_ensembl'])['a_raw_ensembl'].apply(
            lambda value: value.split(':')[0] == 'ensembl')][
        'a_raw_ensembl'].apply(
        lambda value: value.split(':')[1])

    custom_interactions['ensembl_2'] = custom_interactions.dropna(subset=['b_raw_ensembl'])[
        custom_interactions.dropna(subset=['b_raw_ensembl'])['b_raw_ensembl'].apply(
            lambda value: value.split(':')[0] == 'ensembl')][
        'b_raw_ensembl'].apply(
        lambda value: value.split(':')[1])

    custom_interactions = pd.merge(custom_interactions, gene_df, left_on='ensembl_1', right_on='ensembl', how='outer',
                                   indicator='_merge_1')

    custom_interactions.drop(['ensembl'], inplace=True, axis=1)
    custom_interactions = pd.merge(custom_interactions, gene_df, left_on='ensembl_2', right_on='ensembl', how='outer',
                                   indicator='_merge_2', suffixes=['_1', '_2'])

    def get_protein(row, protein_number):
        protein_x = row['protein_%s' % protein_number]
        if isinstance(protein_x, float) and math.isnan(protein_x):
            return row['uniprot_%s' % protein_number]

        return row['protein_%s' % protein_number]

    custom_interactions['protein_1'] = custom_interactions.apply(lambda row: get_protein(row, 1), axis=1)
    custom_interactions['protein_2'] = custom_interactions.apply(lambda row: get_protein(row, 2), axis=1)

    custom_interactions.dropna(how='any', subset=['protein_1', 'protein_2'], inplace=True)

    custom_interactions = custom_interactions[['protein_1', 'protein_2', 'raw_score', 'source']]
    custom_interactions = _only_uniprots_in_df(protein_df, custom_interactions)

    custom_interactions = normalize_interactions(custom_interactions)

    custom_interactions_unique = custom_interactions.drop_duplicates(['protein_1', 'protein_2'], keep='first')

    custom_interactions_unique = custom_interactions_unique[['protein_1', 'protein_2', 'source']]

    _validate_sources(custom_interactions_unique['source'].tolist(), interactions_base_df['provider'].tolist())

    custom_interactions_unique.rename(index=str, columns={'protein_1': 'uniprot_1', 'protein_2': 'uniprot_2'},
                                      inplace=True)

    return custom_interactions_unique


def _validate_sources(generated_sources, original_sources):
    """
    Check if all original soruces exist in generated source
    :type generated_sources: list
    :type original_sources: list
    :rtype: bool
    """

    generated_sources = list(set(generated_sources))
    original_sources = list(set(original_sources))
    not_existent_source = []
    for source in original_sources:
        if source not in generated_sources:
            not_existent_source.append(source)

    if not_existent_source:
        print('WARN: Some sources did exist in generated file')
        print(not_existent_source)
        return False

    return True
