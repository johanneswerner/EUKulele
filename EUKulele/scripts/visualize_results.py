import pandas as pd
import os
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import math
import sys
import yaml
import argparse

def countClassifs(level, level_hierarchy, name_level, df):
    set_list = set()
    
    classifications = list(df.loc[df["classification_level"] == level]["classification"])
    counts = list(df.loc[df["classification_level"] == level]["counts"])
    match_loc = int(np.where([curr == level for curr in level_hierarchy])[0])
    for curr in range(match_loc + 1,len(level_hierarchy)):
        classification_curr = list(df.loc[df["classification_level"] == level_hierarchy[curr]]["full_classification"])
        transcripts_curr = list(df.loc[df["classification_level"] == level_hierarchy[curr]]["transcript_name"])
        correct_index = list(np.where([len(str(cr).split(";")) >= abs(-1-(curr-match_loc)) for cr in classification_curr])[0])
        
        classification_curr = [classification_curr[cr2] for cr2 in correct_index]
        classifs_curr = [str(cr).split(";")[-1-(curr-match_loc)].strip() for cr in classification_curr]
        transcripts_curr = [transcripts_curr[cr2] for cr2 in correct_index]
        counts_curr = list(df.loc[df["classification_level"] == level_hierarchy[curr]]["counts"])
        counts_curr = [counts_curr[cr2] for cr2 in correct_index]
        
        # add to running list
        classifications.extend(classifs_curr)
        transcript_names.extend(transcripts_curr)
        counts.extend(counts_curr)
        
    classifications = [str(cr).strip().strip(""''"]['") for cr in classifications]
    full_list = classifications
    set_list.update(set(classifications))
    
    transcripts_classes = pd.DataFrame({classifications: classifications, transcript_names: transcript_names})
    transcripts_classes.groupby("classifications").agg({"transcript_names": lambda x: ';'.join(x)})
    transcripts_classes = transcripts_classes.set_index('classifications')
    transcripts_classes = transcripts_classes.loc[list(set_list)]
    
    full_frame = pd.DataFrame({name_level: classifications, "Counts": counts})
    final_frame = full_frame.groupby(name_level)['Counts'].agg(Sum='sum', Count='count')
    final_frame["GroupedTranscripts"] = list(transcripts_classes.transcript_names)
    return classifications, final_frame
    
def countClassifsNoCounts(level, level_hierarchy, name_level, df):
    set_list = set()
    
    classifications = list(df.loc[df["classification_level"] == level]["classification"])
    transcript_names = df.loc[df["classification_level"] == level]["transcript_name"]
    #class_and_tax = dict(zip(classifications, transcript_names))
    match_loc = int(np.where([curr == level.lower() for curr in level_hierarchy])[0])
    for curr in range(match_loc + 1,len(level_hierarchy)):
        classification_curr = list(df.loc[df["classification_level"] == level_hierarchy[curr]]["full_classification"])
        transcripts_curr = list(df.loc[df["classification_level"] == level_hierarchy[curr]]["transcript_name"])
        correct_index = list(np.where([len(str(cr).split(";")) >= abs(-1-(curr-match_loc)) for cr in classification_curr])[0])
        
        classification_curr = [classification_curr[cr2] for cr2 in correct_index]
        transcripts_curr = [transcripts_curr[cr2] for cr2 in correct_index]
        classifs_curr = [str(cr).split(";")[-1-(curr-match_loc)].strip() for cr in classification_curr]
        
        #for curr_ind in range(len(classifs_curr)):
        #    class_curr = classifs_curr[curr_ind]
        #    transcript_curr = transcripts_curr[curr_ind]
        #    if class_curr in class_and_tax:
        #        class_and_tax[class_curr] = class_and_tax[class_curr] + ";" + transcript_curr
        #    else:
        #        class_and_tax[class_curr] = transcript_curr
        
        # add to running list
        transcript_names.extend(transcripts_curr)
        classifications.extend(classifs_curr)
        
    classifications = [str(cr).strip().strip(""''"]['") for cr in classifications]
    full_list = classifications
    set_list.update(set(classifications))
    
    transcripts_classes = pd.DataFrame({classifications: classifications, transcript_names: transcript_names})
    transcripts_classes.groupby("classifications").agg({"transcript_names": lambda x: ';'.join(x)})
    transcripts_classes = transcripts_classes.set_index('classifications')
    transcripts_classes = transcripts_classes.loc[list(set_list)]
    
    #final_frame = list(zip(list(set_list), [full_list.count(curr) for curr in list(set_list)]))
    final_frame = pd.DataFrame({name_level: list(set_list), Counts: [full_list.count(curr) for curr in list(set_list)], GroupedTranscripts: list(transcripts_classes.transcript_names)})
    
    return classifications, final_frame

def stripClassifData(df, use_counts):
    level_hierarchy = ['supergroup','division','class','order','family','genus','species']
    
    return_dict_list = dict()
    return_dict_frame = dict()
    for curr_level in level_hierarchy:
        if use_counts == 1:
            curr_list, curr_counts = countClassifs(curr_level, level_hierarchy, curr_level.capitalize(), df)
            return_dict_list[curr_level] = curr_list
            return_dict_frame[curr_level] = curr_counts
        else:
            curr_list, curr_counts = countClassifsNoCounts(curr_level, level_hierarchy, curr_level.capitalize(), df)
            return_dict_list[curr_level] = curr_list
            return_dict_frame[curr_level] = curr_counts
    return return_dict_list, return_dict_frame

def createPlotDataFrame(curr_df_start, cutoff_relative = 0.1, transcript_or_counts="NumTranscripts"):
    ## CREATE AGGREGATED COUNTS BY SAMPLE ##
    curr_df_summed = curr_df_start.groupby("Sample")[transcript_or_counts].agg(AllCts='sum')
    curr_df_summed = curr_df_start.join(curr_df_summed,how="left",on="Sample")

    ## CALCULATE RELATIVE COUNTS ## 
    curr_df_summed["Rel_Counts"] = curr_df_summed[transcript_or_counts] / curr_df_summed["AllCts"]
    curr_df_plot = curr_df_summed[["OfInterest","Sample","Rel_Counts"]]
    pivoted = curr_df_plot.pivot(index='Sample', columns='OfInterest', values='Rel_Counts')
    pivoted = pivoted.reindex(sorted(pivoted.columns), axis=1)

    ## If we're plotting both counts and transcripts, still decide on cutoff via transcripts ## 
    if transcript_or_counts == "Counts":
        curr_df_summed = curr_df_start.groupby("Sample")["NumTranscripts"].agg(AllCts='sum')
        curr_df_summed = curr_df_start.join(curr_df_summed,how="left",on="Sample")
        curr_df_summed["Rel_Counts_Transcripts"] = curr_df_summed["NumTranscripts"] / curr_df_summed["AllCts"]
        curr_df_summed = curr_df_summed[["OfInterest","Sample","Rel_Counts_Transcripts"]]
        pivoted_on_transcripts = curr_df_summed.pivot(index='Sample', columns='OfInterest', values='Rel_Counts_Transcripts')
        pivoted_on_transcripts = pivoted_on_transcripts.reindex(sorted(pivoted_on_transcripts.columns), axis=1)
        pivoted_agg = list(pivoted_on_transcripts.max(axis = 0, skipna = True))
    else:
        pivoted_agg = list(pivoted.max(axis = 0, skipna = True))
    
    ## Leave the columns that meet the threshold; sum the others into an "Other" column ##
    chosen_cols = [curr for curr in range(len(pivoted_agg)) if pivoted_agg[curr] > cutoff_relative]
    chosen_cols_other = [curr for curr in range(len(pivoted_agg)) if pivoted_agg[curr] <= cutoff_relative]
    pivoted_agg = list(pivoted.iloc[:,chosen_cols_other].sum(axis = 1, skipna = True))
    
    ## Modify the output dataframe accordingly ##
    pivoted = pivoted.iloc[:,chosen_cols]
    pivoted["Other"] = pivoted_agg
    
    return pivoted

def makeConcatFrame(curr_df, new_df, level, sample_name, use_counts):
    new_df = pd.DataFrame(new_df)
    if new_df.empty:
        return curr_df
    if use_counts == 1:
        new_df = pd.DataFrame(new_df.reset_index())
        new_df.columns = [level,"Counts","NumTranscripts","GroupedTranscripts"]
    else:
        new_df = pd.DataFrame(new_df)
        new_df.columns = [level,"NumTranscripts","GroupedTranscripts"]
    
    new_df["Sample"] = sample_name
    return pd.concat([curr_df, new_df], sort=True)

def visualize_all_results(out_prefix, out_dir, met_dir, samples_dir, prot_extension, nucle_extension, use_counts, rerun):
    results_frame = dict()

    ### READ IN RESULTS FILES FROM MET DIR THAT FIT SAMPLE SPEC FROM CONFIG ###
    samples = os.listdir(samples_dir)
    good_samples = 0
    for s in samples:
        file_name = s.split(".")[0] + "-estimated-taxonomy.out"
        if not os.path.isfile(os.path.join(met_dir,file_name)):
            print("One of the files, " + s + ", in the sample directory did not complete successfully.")
            sys.exit(1)
        else:
            results_frame[file_name] = pd.read_csv(os.path.join(met_dir,file_name), sep = "\t", index_col=0)
        good_samples = good_samples + 1
            
    if good_samples == 0:
        print("No taxonomic estimation files found! Exiting...")
        sys.exit(1)

    list_results = dict()
    frame_results = dict()

    # characterizing by major classes 
    for curr in results_frame.keys():
        list_results[curr], frame_results[curr] = stripClassifData(results_frame[curr], use_counts)

    counts_all = dict()
    level_hierarchy = ['supergroup','division','class','order','family','genus','species']
    for l in level_hierarchy:
        counts_all[l] = pd.DataFrame(columns = [l.capitalize(),"NumTranscripts","Sample"])

    for curr in results_frame.keys():
        sample_name = curr.split("-")[0]
        print(sample_name)
        for l in level_hierarchy:
            curr_df = counts_all[l]
            new_df = frame_results[curr][l]
            counts_all[l] = makeConcatFrame(curr_df, new_df, l.capitalize(), sample_name, use_counts)

    for l in level_hierarchy:
        ### SAVE THE CSVs OF THE DATA ###
        prefix = out_prefix
        counts_all[l].to_csv(os.path.join(out_dir, prefix + "_all_" + l + "_counts.csv"))

        ### INITIALIZE VARIABLES FOR LOOP ###
        Curr_Variable = l.capitalize()
        cutoff_counts = 100000
        cutoff_transcripts = 100

        ### GRAB DATAFRAME FROM SAVED DATA ###
        curr_df_start = counts_all[l].reset_index() #read.csv(paste0(prefix,"all_",tolower(Curr_Variable),"_counts.csv"))
        if Curr_Variable in curr_df_start:
            curr_df_start["OfInterest"] = curr_df_start[Curr_Variable]
        else:
            curr_df_start["OfInterest"] = []

        sns.set()

        ## CREATE AGGREGATED COUNTS BY SAMPLE ##
        curr_df_summed = curr_df_start.groupby("Sample")["NumTranscripts"].agg(AllCts='sum')
        curr_df_summed = curr_df_start.join(curr_df_summed,how="left",on="Sample")

        ## CALCULATE RELATIVE COUNTS ## 
        curr_df_summed["Rel_Counts"] = curr_df_summed["NumTranscripts"] / curr_df_summed["AllCts"]
        curr_df_plot = curr_df_summed[["OfInterest","Sample","Rel_Counts"]]
        print(curr_df_plot)
        print("curr df!")
        pivoted = curr_df_plot.pivot(index='Sample', columns='OfInterest', values='Rel_Counts')

        pivoted_agg = list(pivoted.sum(axis = 0, skipna = True))
        chosen_cols = [curr for curr in range(len(pivoted_agg)) if pivoted_agg[curr] > 0.1]
        pivoted = pivoted.iloc[:,chosen_cols]

        c25 = ["dodgerblue2", "#E31A1C",\
          "green4",\
          "#6A3D9A",\
          "#FF7F00",\
          "black", "gold1",\
          "skyblue2", "#FB9A99",\
          "palegreen2",\
          "#CAB2D6",\
          "#FDBF6F",\
          "gray70", "khaki2",\
          "maroon", "orchid1", "deeppink1", "blue1", "steelblue4",\
          "darkturquoise", "green1", "yellow4", "yellow3",\
          "darkorange4", "brown"]

        fig = plt.figure(figsize=(15,7.5))
        if len(set(curr_df_start["OfInterest"])) == 0:
            continue
        sns_palette = sns.palplot(sns.color_palette("Set1", n_colors=len(set(curr_df_start["OfInterest"]))))

        ### CREATE PLOTS ###
        if use_counts == 0:
            fig = plt.figure(figsize=(15,7.5))
            fig.set_facecolor('white')
            pivoted = createPlotDataFrame(curr_df_start, cutoff_relative = 0.05, transcript_or_counts="NumTranscripts")
            pivoted.plot(kind='bar', stacked=True, color = sns_palette)
            plt.tight_layout()
            plt.savefig(os.path.join(out_dir, l + '_transcripts.png'),dpi=100)
            plt.show()
            plt.close()
        else:
            f, (ax1, ax2) = plt.subplots(1, 2, sharey=True, figsize=(15,7.5))
            ax1.set_facecolor('white')
            ax2.set_facecolor('white')
            pivoted = createPlotDataFrame(curr_df_start, cutoff_relative = 0.05, transcript_or_counts="NumTranscripts")
            pivoted.plot(kind='bar', stacked=True, width=1, color = sns_palette, title="Transcripts", ax = ax1)
            pivoted = createPlotDataFrame(curr_df_start, cutoff_relative = 0.05, transcript_or_counts="Counts")
            pivoted.plot(kind='bar', stacked=True, width=1, color = sns_palette, title="Counts", ax = ax2)
            plt.tight_layout()
            plt.savefig(os.path.join(out_dir, l + '_counts_and_transcripts.png'),dpi=100)
            plt.show()
            plt.close()
