import os

import math
import pandas as pd
import zipfile

from tools.app import current_dir, data_dir, output_dir
from cellcommdb.tools.filters import remove_not_defined_columns

import requests


def _unzip_inwebinbiomap(file_path):
    zip_ref = zipfile.ZipFile(file_path, 'r')
    extract_path = '%s/temp' % (current_dir)
    zip_ref.extractall(extract_path)
    zip_ref.close()


def _download_inwebinbiomap():
    print('Downloading InBio_Map_core_2016_09_12')
    s = requests.Session()
    # First, we need create session in inatomics
    namefile = 'InBio_Map_core_2016_09_12.zip'
    r = s.get("https://www.intomics.com/inbio/api/login_guest?ref=&_=1509120239303")
    r = s.get('https://www.intomics.com/inbio/map/api/get_data?file=%s' % namefile)
    print('Downloaded InBio_Map_core_2016_09_12')

    download_path = '%s/temp/InBio_Map_core_2016_09_12.zip' % (current_dir)
    file = open(download_path, 'wb')
    file.write(r.content)
    file.close()

    _unzip_inwebinbiomap(download_path)

    return '%s/temp/InBio_Map_core_2016_09_12/core.psimitab' % current_dir


def only_noncomplex_interactions(complexes_namefile, inweb_namefile):
    if os.path.isfile('%s%s' % (data_dir, inweb_namefile)):
        inweb_file = os.path.join(data_dir, inweb_namefile)
    else:
        inweb_file = os.path.join(output_dir, inweb_namefile)

    complexes_file = os.path.join(current_dir, 'data', complexes_namefile)

    complexes_df = pd.read_csv(complexes_file)

    proteins_in_complex = []

    for i in range(1, 5):
        proteins_in_complex = proteins_in_complex + complexes_df['protein_%s' % i].dropna().tolist()

    proteins_in_complex = list(set(proteins_in_complex))

    inweb_df = pd.read_csv(inweb_file)

    inweb_df_no_complex = inweb_df[inweb_df['protein_1'].apply(
        lambda protein: protein not in proteins_in_complex
    )]
    inweb_df_no_complex = inweb_df_no_complex[
        inweb_df_no_complex['protein_2'].apply(
            lambda protein: protein not in proteins_in_complex
        )]

    output_name = 'no_complex_interactions.csv'
    inweb_df_no_complex.to_csv('%s/out/%s' % (current_dir, output_name),
                               index=False, float_format='%.4f')


def generate_interactions_imex(interactions_base_namefile, database_proteins_namefile):
    interactions_base_df = pd.read_csv('%s%s' % (data_dir, interactions_base_namefile), sep='\t', na_values='-')

    interactions_base_df.dropna(how='any', subset=['A', 'B'], inplace=True)

    interactions_base_df['confidenceScore'].replace('nan', pd.np.NaN, inplace=True)

    imex_inteactions = pd.DataFrame()

    imex_inteactions['protein_1'] = interactions_base_df['A'].apply(
        lambda preformat_uniprot: preformat_uniprot.split(':')[1].split('-')[0])
    imex_inteactions['protein_2'] = interactions_base_df['B'].apply(
        lambda preformat_uniprot: preformat_uniprot.split(':')[1].split('-')[0])

    def extract_score(row):
        if isinstance(row, float) and math.isnan(row):
            return 0
        return row.split('intact-miscore:')[1]

    imex_inteactions['score_1'] = interactions_base_df['confidenceScore'].apply(extract_score)

    imex_inteactions['score_2'] = imex_inteactions['score_1']

    imex_inteactions['source'] = interactions_base_df['provider']

    database_proteins_df = pd.read_csv('%s/%s' % (data_dir, database_proteins_namefile))

    cellphone_interactions = _only_uniprots_in_df(database_proteins_df, imex_inteactions)

    def set_score_duplicates(interaction):
        interaction['score_1'] = \
            cellphone_interactions[(cellphone_interactions['protein_1'] == interaction['protein_1']) & (
                cellphone_interactions['protein_2'] == interaction['protein_2'])]['score_1'].max()

        interaction['score_2'] = \
            cellphone_interactions[(cellphone_interactions['protein_1'] == interaction['protein_1']) & (
                cellphone_interactions['protein_2'] == interaction['protein_2'])]['score_2'].max()

        return interaction

    interactions = cellphone_interactions.apply(set_score_duplicates, axis=1)

    interactions.drop_duplicates(keep='first', inplace=True)

    interactions.to_csv('%scellphone_interactions_imex.csv' % output_dir, index=False)


def generate_interactions_innatedb(interactions_base_namefile, database_gene_namefile):
    interactions_base_df = pd.read_csv('%s/%s' % (data_dir, interactions_base_namefile), sep='\t', na_values='-')

    innatedb_inteactions = pd.DataFrame()

    innatedb_inteactions['gene_1'] = interactions_base_df['alt_identifier_A'].apply(
        lambda preformat_uniprot: preformat_uniprot.split(':')[1])
    innatedb_inteactions['gene_2'] = interactions_base_df['alt_identifier_B'].apply(
        lambda preformat_uniprot: preformat_uniprot.split(':')[1])

    innatedb_inteactions['score_1'] = 0
    innatedb_inteactions['score_2'] = 1

    innatedb_inteactions['source'] = 'innatedb'

    database_genes_df = pd.read_csv('%s%s' % (data_dir, database_gene_namefile))

    cellphone_interactions = _only_genes_in_df(database_genes_df, innatedb_inteactions)

    cellphone_interactions.rename(index=str, columns={'uniprot_1': 'protein_1', 'uniprot_2': 'protein_2'}, inplace=True)

    cellphone_interactions = remove_not_defined_columns(cellphone_interactions,
                                                        ['protein_1', 'protein_2', 'score_1', 'score_2', 'source'])

    cellphone_interactions.drop_duplicates(inplace=True)

    cellphone_interactions.to_csv('%s/cellphone_interactions_innatedb.csv' % output_dir, index=False)


def merge_interactions_action(interactions_namefile_1, interactions_namefile_2):
    if os.path.isfile('%s/%s' % (data_dir, interactions_namefile_1)):
        interactions_1 = pd.read_csv('%s/%s' % (data_dir, interactions_namefile_1))
    else:
        interactions_1 = pd.read_csv('%s/%s' % (output_dir, interactions_namefile_1))

    if os.path.isfile('%s/%s' % (data_dir, interactions_namefile_2)):
        interactions_2 = pd.read_csv('%s/%s' % (data_dir, interactions_namefile_2))
    else:
        interactions_2 = pd.read_csv('%s/%s' % (output_dir, interactions_namefile_2))

    def interaction_exist(interaction):
        if len(interactions_1[(interactions_1['protein_1'] == interaction['protein_1']) & (
                    interactions_1['protein_2'] == interaction['protein_2'])]):
            return True

        if len(interactions_1[(interactions_1['protein_2'] == interaction['protein_1']) & (
                    interactions_1['protein_1'] == interaction['protein_2'])]):
            return True

        return False

    interactions_2_not_in_1 = interactions_2[interactions_2.apply(interaction_exist, axis=1) == False]

    interactions = interactions_1.append(interactions_2_not_in_1)

    interactions.to_csv('%s/cellphone_interactions.csv' % output_dir, index=False)


def generate_interactions_inweb(inweb_inbiomap_namefile, database_proteins_namefile):
    if not inweb_inbiomap_namefile:
        inweb_inbiomap_namefile = _download_inwebinbiomap()
        inweb_inbiomap_file = os.path.join(inweb_inbiomap_namefile)
    else:
        inweb_inbiomap_file = os.path.join(current_dir, 'data', inweb_inbiomap_namefile)

    inweb_inbiomap_df = pd.read_csv(inweb_inbiomap_file, delimiter='\t', na_values='-')

    inweb_interactions = pd.DataFrame()

    inweb_interactions['protein_1'] = inweb_inbiomap_df.take([0], axis=1).apply(
        lambda protein: protein.values[0].split(':')[1], axis=1)
    inweb_interactions['protein_2'] = inweb_inbiomap_df.take([1], axis=1).apply(
        lambda protein: protein.values[0].split(':')[1], axis=1)
    inweb_interactions['score_1'] = inweb_inbiomap_df.take([14], axis=1).apply(
        lambda protein: 0 if protein.values[0].split('|')[0] == '-' else protein.values[0].split('|')[0], axis=1)
    inweb_interactions['score_2'] = inweb_inbiomap_df.take([14], axis=1).apply(
        lambda protein: 0 if protein.values[0].split('|')[1] == '-' else protein.values[0].split('|')[1], axis=1)

    inweb_interactions['source'] = 'inweb'

    database_proteins_file = os.path.join(current_dir, 'data', database_proteins_namefile)

    database_proteins_df = pd.read_csv(database_proteins_file)

    inweb_interactions = _only_uniprots_in_df(database_proteins_df, inweb_interactions)

    inweb_interactions.to_csv('%scellphone_interactions_inweb.csv' % output_dir, index=False)


def remove_interactions_in_file(interaction_namefile, interactions_to_remove_namefile):
    if os.path.isfile('%s/%s' % (data_dir, interaction_namefile)):
        interactions_file = os.path.join(data_dir, interaction_namefile)
    else:
        interactions_file = os.path.join(output_dir, interaction_namefile)

    interactions_df = pd.read_csv(interactions_file)
    interactions_remove_df = pd.read_csv('%s/%s' % (data_dir, interactions_to_remove_namefile))

    def interaction_not_exists(row):
        if len(interactions_remove_df[(row['protein_1'] == interactions_remove_df['protein_1']) & (
                    row['protein_2'] == interactions_remove_df['protein_2'])]):
            return False

        if len(interactions_remove_df[(row['protein_1'] == interactions_remove_df['protein_2']) & (
                    row['protein_2'] == interactions_remove_df['protein_1'])]):
            return False

        return True

    interactions_filtered = interactions_df[interactions_df.apply(interaction_not_exists, axis=1)]

    interactions_filtered.to_csv('%s/clean_interactions.csv' % (output_dir), index=False)


def append_curated(interaction_namefile, interaction_curated_namefile):
    if os.path.isfile('%s/%s' % (data_dir, interaction_namefile)):
        interactions_file = os.path.join(data_dir, interaction_namefile)
    else:
        interactions_file = os.path.join(output_dir, interaction_namefile)

    interactions_df = pd.read_csv(interactions_file)
    interaction_curated_df = pd.read_csv('%s/%s' % (data_dir, interaction_curated_namefile))

    interactions_df.rename(index=str, columns={'protein_1': 'multidata_name_1', 'protein_2': 'multidata_name_2'},
                           inplace=True)

    interactions_merged = interactions_df.append(interaction_curated_df)

    interactions_merged.to_csv('%s/interaction.csv' % output_dir, index=False)


def _only_uniprots_in_df(uniprots_df, inweb_interactions):
    inweb_cellphone = pd.merge(inweb_interactions, uniprots_df, left_on=['protein_1'],
                               right_on=['uniprot'], how='inner')

    remove_not_defined_columns(inweb_cellphone, inweb_interactions.columns.values)

    inweb_cellphone = pd.merge(inweb_cellphone, uniprots_df, left_on=['protein_2'],
                               right_on=['uniprot'], how='inner')
    remove_not_defined_columns(inweb_cellphone, inweb_interactions.columns.values)

    # Prevents duplicated interactions if any uniprot is duplicated in uniprots_df or intaractions
    inweb_cellphone = inweb_cellphone[inweb_cellphone.duplicated() == False]

    return remove_not_defined_columns(inweb_cellphone, inweb_interactions.columns.values)


def _only_genes_in_df(genes_df, interactions):
    result = pd.merge(interactions, genes_df, left_on=['gene_1'],
                      right_on=['ensembl'], how='inner')

    result = pd.merge(result, genes_df, left_on=['gene_2'],
                      right_on=['ensembl'], how='inner', suffixes=['_1', '_2'])

    # Prevents duplicated interactions if any uniprot is duplicated in uniprots_df or intaractions
    result = result[result.duplicated() == False]

    return result
