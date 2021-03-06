#!/usr/bin/env python
import ujson
import pandas as pd
import numpy as np
import yaml
import chardet
import argparse
import multiprocessing
from joblib import Parallel, delayed

def tax_placement(pident):
    if pident >= tax_cutoffs['species']:
        out = 'species'; level = 7;
    elif pident >= tax_cutoffs['genus']:
        out = 'genus'; level = 6;
    elif pident >= tax_cutoffs['family']:
        out = 'family'; level = 5;
    elif pident >= tax_cutoffs['order']:
        out = 'order'; level = 4;
    elif pident < tax_cutoffs['order']:
        out = 'class'; level = 3;
    return out, level

def read_in_taxonomy(infile):
    with open(infile, 'rb') as f:
        result = chardet.detect(f.read())
    tax_out = pd.read_csv(infile, sep='\t',encoding=result['encoding'])
    tax_out.columns = tax_out.columns.str.lower()
    tax_out = tax_out.set_index('source_id')
    return tax_out

def read_in_tax_cutoffs(yamlfile):
    with open(yamlfile, 'r') as stream:
        co_out = yaml.safe_load(stream)
    return co_out

def read_in_protein_map(protjson):
    with open(protjson, 'rb') as f:
        pout = ujson.load(f)
    return pout

def read_in_diamond_file(dfile, pdict):
    dfout =  pd.read_csv(dfile, sep = '\t', header = None)
    dfout.columns = ['qseqid', 'sseqid', 'pident', 'length', 'mismatch', 'gapopen', 'qstart', 'qend', 'sstart', 'send', 'evalue', 'bitscore']
    dfout['ssqid_TAXID']=dfout.sseqid.map(pdict)
    return dfout

def gen_dict(tax_table):
    classes = ['supergroup','division','class','order','family','genus','species']
    tax_table["Classification"] = ""
    for c in classes:
        if all([str(curr).lower() != "nan" for curr in list(tax_table[c])]):
            if str(tax_table["Classification"][0]) != "":
                tax_table["Classification"] = tax_table["Classification"] + ";" + tax_table[c]
            else:
                tax_table["Classification"] = tax_table["Classification"] + tax_table[c]
    return(dict(zip(tax_table.index, tax_table["Classification"])))

def gen_reads_dict(names_to_reads):
    names_to_reads = pd.read_csv(names_to_reads,header=0,sep="\t")
    return(dict(zip(names_to_reads["TranscriptNames"],names_to_reads["NumReads"])))

def lca(full_classifications):
    classes = ['supergroup','division','class','order','family','genus','species']
    full_classifications_split = [[str(subtax).strip() for subtax in curr.split(";")] for curr in full_classifications]
    length_classes = [len(curr) for curr in full_classifications_split]
    if len(set(length_classes)) != 1:
        print("Error: not all classifications at at the same taxonomic level.")
        sys.exit(1)
    for l in reversed(range(length_classes[0])):
        set_classifications = [curr[l] for curr in full_classifications_split]
        if len(set(set_classifications)) == 1:
            return classes[l], set_classifications[0], "; ".join(full_classifications_split[0][0:(l+1)])
    return "","","" # if there are no common ancestors

def match_maker(dd, consensus_cutoff, tax_dict, use_counts):
    ambiguous = 0 # we assume unambiguous
    md = dd.pident.max()
    transcript_name = set(list(dd["qseqid"]))
    if len(transcript_name) > 1:
        print("More than 1 transcript name included in the group.")
    transcript_name = list(transcript_name)[0]
    ds = list(set(dd[dd.pident==md]['ssqid_TAXID']))
    counts = list(set(list(dd[dd.pident==md]['counts'])))
    print(counts)
    if (len(counts) >= 1):
        chosen_count = counts[0]
    else:
        chosen_count = 0
    assignment, level = tax_placement(md) # most specific taxonomic level assigned
    if len(ds)==1:
        if ds[0] not in tax_dict:
            print(dd[dd.pident==md])
            return(pd.DataFrame(columns=['transcript_name','classification_level', 'full_classification', 'classification', 'max_pid', 'counts', 'ambiguous']))
        full_classification = str(tax_dict[ds[0]]).split(";")[0:level]
        best_classification = full_classification[len(full_classification) - 1] # the most specific taxonomic level we can classify by
        full_classification = '; '.join(full_classification) # the actual assignments based on that
    else:
        classification_0 = []
        full_classification_0 = []
        for d in ds:
            if d not in tax_dict:
                return(pd.DataFrame(columns=['transcript_name','classification_level', 'full_classification', 'classification', 'max_pid', 'counts', 'ambiguous']))
            d_full_class = str(tax_dict[d]).split(";")[0:level]
            classification_0.append(d_full_class[len(d_full_class) - 1]) # the most specific taxonomic level we can classify by
            full_classification_0.append('; '.join(d_full_class)) # the actual assignments based on that
        entries = list(set(full_classification_0))
        if len(entries) == 1:
            best_classification = classification_0[0]
            full_classification = full_classification_0[0]
        else:
            ambiguous = 1
            best_frac = 0
            best_one_class = 0
            best_full_class = 0
            for e in entries:
                curr_frac = len(np.where(full_classification_0 == e)) / len(full_classification_0)
                if (isinstance(curr_frac, float)) & (curr_frac > best_frac):
                    best_frac = curr_frac
                    best_full_class = e
                    best_one_class = str(e.split(";")[len(e.split(";")) - 1]).strip()
            if best_frac >= consensus_cutoff:
                best_classification = best_one_class
                full_classification = best_full_class
            else:
                assignment, best_classification, full_classification = lca(full_classification_0)

    if use_counts == 1:
        return pd.DataFrame([[transcript_name, assignment, full_classification, best_classification, md, chosen_count, ambiguous]],\
                       columns=['transcript_name','classification_level', 'full_classification', 'classification', 'max_pid', 'counts', 'ambiguous'])
    else:
        return pd.DataFrame([[transcript_name, assignment, full_classification, best_classification, md, ambiguous]],\
                       columns=['transcript_name', 'classification_level', 'full_classification', 'classification', 'max_pid', 'ambiguous'])

def apply_parallel(grouped_data, match_maker, consensus_cutoff, tax_dict, use_counts):
    resultdf = Parallel(n_jobs=multiprocessing.cpu_count())(delayed(match_maker)(group, consensus_cutoff, tax_dict, use_counts) for name, group in grouped_data)
    return pd.concat(resultdf)

def classify_taxonomy_parallel(df, tax_dict, namestoreads, pdict, consensus_cutoff):
    chunksize = 10 ** 6
    counter = 0
    for chunk in pd.read_csv(df, sep = '\t', header = None, chunksize=chunksize):
        chunk.columns = ['qseqid', 'sseqid', 'pident', 'length', 'mismatch', 'gapopen', 'qstart', 'qend', 'sstart', 'send', 'evalue', 'bitscore']
        chunk['ssqid_TAXID']=chunk.sseqid.map(pdict)
        print(chunk['ssqid_TAXID'])
        if namestoreads != 0:
            chunk['counts']=[namestoreads[str(curr.split(".")[0])] if str(curr.split(".")[0]) in namestoreads else 0 for curr in chunk.qseqid]
            use_counts = 1
        else:
            chunk['counts'] = [0] * len(chunk.qseqid) # if no reads dict, each count is just assumed to be 0 and isn't recorded later
            use_counts = 0
            
        if counter == 0:
            outdf = apply_parallel(chunk.groupby('qseqid'), match_maker, consensus_cutoff, tax_dict, use_counts)
        else:
            outdf = pd.concat([outdf, apply_parallel(chunk.groupby('qseqid'), match_maker, consensus_cutoff, tax_dict, use_counts)], axis = 0)
        counter = counter + 1
    return outdf

# create a dictionary for all of the mmetsp and then just split by ";" and then take the top X based on the tax class level.
# time the difference between the new function and the original.
def classify_taxonomy(df, tax_dict, consensus_cutoff):
    level_dict = {'class':['supergroup','division','class'],
                       'order':['supergroup','division','class', 'order'],
                       'family':['supergroup','division','class', 'order', 'family'],
                       'genus': ['supergroup','division','class', 'order', 'family','genus'],
                        'species':['supergroup','division','class', 'order', 'family','genus', 'species']}

    outdf = pd.DataFrame(columns = ['classification_level', 'full_classification', 'classification', 'max_pid', 'ambiguous'])
    for t,dd in df.groupby('qseqid'):
        ambiguous = 0 # we assume unambiguous
        md = dd.pident.max()
        ds = list(set(dd[dd.pident==md]['ssqid_TAXID']))
        assignment, level = tax_placement(md) # most specific taxonomic level assigned
        if len(ds)==1:
            full_classification = tax_dict[ds[0]].split(";")[0:level]
            best_classification = full_classification[len(full_classification) - 1] # the most specific taxonomic level we can classify by
            full_classification = '; '.join(full_classification) # the actual assignments based on that
        else:
            classification_0 = []
            full_classification_0 = []
            for d in ds:
                d_full_class = tax_dict[d].split(";")[0:level]
                classification_0.append(d_full_class[len(d_full_class) - 1]) # the most specific taxonomic level we can classify by
                full_classification_0.append('; '.join(d_full_class)) # the actual assignments based on that
            if len(set(classification_0)) == 1:
                best_classification = classification_0[0]
                full_classification = full_classification_0[0]
            else:
                ambiguous = 1
                entries = list(set(full_classification_0))
                best_frac = 0
                best_one_class = 0
                best_full_class = 0
                for e in entries:
                    curr_frac = len(np.where(full_classification_0 == e)) / len(full_classification_0)
                    if (isinstance(curr_frac, float)) & (curr_frac > best_frac):
                        best_frac = curr_frac
                        best_full_class = e
                        best_one_class = e.split(";")[len(e.split(";")) - 1].strip()
                if best_frac >= consensus_cutoff:
                    best_classification = best_one_class
                    full_classification = best_full_class
                else:
                    best_classification, full_classification = lca(full_classification_0)
        outdf.loc[t] =  [assignment, full_classification, best_classification, md, ambiguous]
    return outdf

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--tax_file')
    parser.add_argument('--cutoff_file')
    parser.add_argument('--consensus_cutoff')
    parser.add_argument('--prot_map_file')
    parser.add_argument('--use_counts')
    parser.add_argument('--names_to_reads')
    parser.add_argument('--diamond_file')
    parser.add_argument('--outfile')
    parser.add_argument('--method')
    args = parser.parse_args()
    tax_table = read_in_taxonomy(args.tax_file)
    tax_cutoffs = read_in_tax_cutoffs(args.cutoff_file)
    pdict = read_in_protein_map(args.prot_map_file)
    tax_dict = gen_dict(tax_table)
    consensus_cutoff = float(args.consensus_cutoff)
    if args.method == "parallel":
        if (int(args.use_counts) == 1):
            print("Hello")
            print(args.use_counts)
            reads_dict = gen_reads_dict(args.names_to_reads)
            classification_df = classify_taxonomy_parallel(args.diamond_file, tax_dict, reads_dict, pdict, consensus_cutoff)
        else:
            classification_df = classify_taxonomy_parallel(args.diamond_file, tax_dict, 0, pdict, consensus_cutoff)
    else:
        diamond_df = read_in_diamond_file(args.diamond_file, pdict)
        classification_df = classify_taxonomy(diamond_df, tax_dict, consensus_cutoff)
    classification_df.to_csv(args.outfile, sep='\t')
