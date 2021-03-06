# Query BUSCO for a given species or functional group. 
# A script that takes a given functional group as input, along with the taxonomic level of that group
# (e.g. Phaeocystis antarctica, species), and then checks for BUSCO completeness among the contigs
# identified as that taxonomic level or lower, also evaluating the number of copies of the BUSCO
# matches to differentiate between multiple strains. # !/ usr/bin/env python3

import pandas as pd
import numpy as np
import os
import sys
import argparse
import chardet
import glob

__author__ = "Arianna Krinos, Harriet Alexander"
__copyright__ = "EUKulele"
__license__ = "MIT"
__email__ = "akrinos@mit.edu"

parser = argparse.ArgumentParser()
parser.add_argument('--busco_out') # the output from the BUSCO run on the full sample file
parser.add_argument('--organism_group') # the focal name of species/genus/order/class etc.
parser.add_argument('--taxonomic_level') # the taxonomic level of the specified focal name.
parser.add_argument('--fasta_file') # the fasta file from which we pull sequences for the mock transcriptome.
parser.add_argument('--taxonomy_file_prefix') # the taxonomy file we use to create the mock transcriptome.
parser.add_argument('--tax_table') # the taxonomy table to get the full classification of the organism as assessed by the database being used.
parser.add_argument('--sample_name') # name of the original sample being assessed.
parser.add_argument('--download_busco',action='store_true') # if specified, we download BUSCO file from the url in the next argument
parser.add_argument('--create_fasta',action='store_true') # if specified, we create a "transcriptome fasta" when we query for the organisms
parser.add_argument('--busco_url',default=0)
parser.add_argument('--busco_location',default="busco") # location to store the BUSCO tar reference
parser.add_argument('--output_dir',default="output")
parser.add_argument('--available_cpus',default=1)
parser.add_argument('--busco_threshold',default=50)

def read_in_taxonomy(infile):
    with open(infile, 'rb') as f:
        result = chardet.detect(f.read())
    tax_out = pd.read_csv(infile, sep='\t',encoding=result['encoding'])
    tax_out.columns = tax_out.columns.str.lower()
    tax_out = tax_out.set_index('source_id')
    return tax_out

args = parser.parse_args()
organism_format = " ".join(args.organism_group.split("_"))
organism = args.organism_group
taxonomy = args.taxonomic_level
tax_table = read_in_taxonomy(args.tax_table)
full_taxonomy = tax_table.loc[[(organism_format in curr) for curr in tax_table[taxonomy]],:]
print(organism_format)
print(full_taxonomy)
if len(full_taxonomy.index) < 1:
    print("No taxonomy found for that organism and taxonomic level.")
    sys.exit(1)
level_hierarchy = ['supergroup','division','class','order','family','genus','species']
curr_level = [ind for ind in range(len(level_hierarchy)) if level_hierarchy[ind] == taxonomy][0]
print(curr_level)
max_level = len(level_hierarchy) - 1

success = 0
busco_scores = []
busco_out_file = pd.read_csv(args.busco_out, sep = "\t", comment = "#", names = ["BuscoID","Status","Sequence","Score","Length"])
select_inds = [ (busco_out_file.Status[curr] == "Complete") | (busco_out_file.Status[curr] == "Fragmented") | (busco_out_file.Status[curr] == "Duplicated") for curr in range(len(busco_out_file.index))]
good_buscos = busco_out_file.loc[select_inds,:]
good_busco_sequences = [curr.split(".")[0] for curr in list(good_buscos.Sequence)]
Covered_IDs = list(good_buscos.BuscoID)
total_buscos = len(set(list(busco_out_file.BuscoID)))
print(total_buscos)

while (curr_level >= 0):
    
    #### GET THE CURRENT LEVEL OF TAXONOMY FROM THE TAX TABLE FILE ####
    curr_tax_list = set(list(full_taxonomy[level_hierarchy[curr_level]]))
    if len(curr_tax_list) > 1:
        print(curr_tax_list)
        print("More than 1 unique match found; using both matches: " + str("".join(curr_tax_list)))
              #using the first match (" + str(list(curr_tax_list)[0]) + ")")
    curr_taxonomy = ";".join(curr_tax_list) #str(list(curr_tax_list)[0])
    if (curr_taxonomy == "") | (curr_taxonomy.lower() == "nan"):
        print("No taxonomy found at level " + level_hierarchy[curr_level])
        continue
        
    #### CREATE A "MOCK TRANSCRIPTOME" BY PULLING BY TAXONOMIC LEVEL ####
    taxonomy_file = pd.read_csv(args.taxonomy_file_prefix + "_all_" + str(level_hierarchy[curr_level]) + "_counts.csv", sep=",",header=0)
    taxonomy_file = taxonomy_file.loc[[tax in curr_taxonomy for tax in list(taxonomy_file[level_hierarchy[curr_level].capitalize()])],:]
    transcripts_to_search = list(taxonomy_file["GroupedTranscripts"])
    transcripts_to_search_sep = []
    for transcript_name in transcripts_to_search:
        transcripts_to_search_sep.extend([curr.split(".")[0] for curr in transcript_name.split(";")])
    
    set_transcripts_to_search = set(transcripts_to_search_sep)
    good_busco_sequences_list = list(good_busco_sequences)
    BUSCOs_covered = set([Covered_IDs[curr] for curr in range(len(good_busco_sequences_list)) if good_busco_sequences_list[curr] in list(set_transcripts_to_search)])
    
    busco_completeness = len(BUSCOs_covered) / total_buscos * 100
    #len(set_transcripts_to_search.intersection(good_busco_sequences)) / total_buscos * 100
    busco_scores.append(busco_completeness)
    if busco_completeness >= args.busco_threshold:
        success = 1
        break
    curr_level = curr_level - 1

report_dir = os.path.join(args.output_dir, organism, args.taxonomic_level)
os.system("mkdir -p " + os.path.join(args.output_dir, organism))
os.system("mkdir -p " + report_dir)

report_file = os.path.join(report_dir, args.sample_name + "_report.txt")
reported = open(report_file,"w")
if success == 1:
    file_written = os.path.join(args.output_dir, organism, level_hierarchy[curr_level] + "_" + args.sample_name + ".txt")
    with open(file_written, 'w') as filehandle:
        for transcript_name in transcripts_to_search_sep:
            filehandle.write(transcript_name + '\n')
    if (args.create_fasta):
        mock_file_name = organism + "_" + level_hierarchy[curr_level] + "_" + args.sample_name + "_BUSCO_complete.fasta"
        os.system("grep -w -A 2 -f " + file_written + " " + args.fasta_file + " --no-group-separator > " + mock_file_name)
            
    reported.write("Taxonomy file successfully completed with BUSCO completeness " + str(busco_completeness) + "% at location " + str(file_written) + ". The file containing the transcript names for the mock transcriptome corresponding to this taxonomic level is located here: " + str(file_written) + ".\n")
    reported.write("The BUSCO scores found at the various taxonomic levels (Supergroup to " + str(args.taxonomic_level) + ") were: " + str(busco_scores))
else:
    reported.write("Sufficient BUSCO completeness not found at threshold " + str(args.busco_threshold) + "%. \n")
    reported.write("The BUSCO scores found at the various taxonomic levels (Supergroup to " + str(args.taxonomic_level) + ") were: " + str(busco_scores) + "\n")
reported.close()