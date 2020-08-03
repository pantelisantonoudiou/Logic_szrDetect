# -*- coding: utf-8 -*-
"""
Created on Mon Aug  3 16:47:30 2020

@author: Pante
"""


import os, features, time
import numpy as np
import pandas as pd
from numba import jit
from tqdm import tqdm
from sklearn.preprocessing import StandardScaler
from preprocess import preprocess_data
from build_feature_data import get_data, get_features_allch
from array_helper import find_szr_idx, match_szrs, merge_close
import matplotlib.pyplot as plt

main_path =  r'C:\Users\Pante\Desktop\seizure_data_tb\Train_data'  # 3514_3553_3639_3640  3642_3641_3560_3514
# folder_path = r'C:\Users\Pante\Desktop\seizure_data_tb\Train_data\3642_3641_3560_3514'
num_channels = [0,1]
win = 5


# define parameter list
param_list = (features.autocorr, features.line_length, features.rms, features.mad, features.var, features.std, features.psd, features.energy,
              features.get_envelope_max_diff,)
cross_ch_param_list = () # features.cross_corr


def multi_folder(main_path):
    
    # get subdirectories
    folders = [f.name for f in os.scandir(main_path) if f.is_dir()]
    
    for folder in folders:
        print('Analyzing', folder, '...' )
        
        # get dataframe with detected seizures
        df, szrs =  folder_loop(os.path.join(main_path,folder))
        
        # save dataframe as csv file
        df_path = os.path.join(main_path,folder+'_thresh_'+str(thresh_multiplier) + '_test.csv')
        df.to_csv(df_path, index=True)


def folder_loop(folder_path):
    
    # get file list 
    ver_path = os.path.join(folder_path, 'verified_predictions_pantelis')
    filelist = list(filter(lambda k: '.csv' in k, os.listdir(ver_path))) # get only files with predictions
    filelist = [os.path.splitext(x)[0] for x in filelist] # remove csv ending
    
    # create feature labels
    feature_labels = [x.__name__ + '_1' for x in param_list]; 
    feature_labels += [x.__name__ + '_2' for x in param_list]; 
    feature_labels += [x.__name__  for x in cross_ch_param_list]
    feature_labels = np.array(feature_labels)
    
    # create dataframe
    columns = ['exp_id', 'szr_start','szr_end' , 'before_szr', 'during_szr','after_szr']
    df = pd.DataFrame(data= np.zeros((0,len(columns))), columns = columns, dtype=np.int64)

    for i in tqdm(range(0, len(filelist))): # loop through experiments  

        # get data and true labels
        data, y_true = get_data(folder_path,filelist[i], ch_num = num_channels, 
                                inner_path={'data_path':'filt_data', 'pred_path':'verified_predictions_pantelis'} , load_y = True)
        
        ## UNCOMMENT LINE BELOW TO : Clean and filter data
        # data = preprocess_data(data,  clean = True, filt = True, verbose = 0)
        # print('-> data pre-processed.')
        
        # Get features and labels
        x_data, labels = get_features_allch(data,param_list,cross_ch_param_list)
        
        #  UNCOMMENT LINES BELOW TO : get refined data (multiply channels)
        # new_data = np.multiply(x_data[:,0:len(param_list)],x_data[:,len(param_list):x_data.shape[1]-len(cross_ch_param_list)])
        # x_data = np.concatenate((new_data, x_data[:,x_data.shape[1]-1:]), axis=1)
        
        # Normalize data
        x_data = StandardScaler().fit_transform(x_data)
        
        for ii in range(len(feature_labels)): # iterate through parameteres  x_data.shape[1]

            # get seizure index
            bounds_true = find_szr_idx(y_true, np.array([0,1])) # true
 
            # get experiment id
            exp_id = [filelist[i]]
            if bounds_true.shape[0] > 0:
        
                
                # get seizure and surround properties
                szrs = get_surround(x_data[:,6], bounds_true, np.array([30, 120]))
                df_temp = pd.DataFrame(data = szrs, columns = ['before_szr', 'during_szr','after_szr'])
                
                df_temp.insert(0, 'szr_end', bounds_true[:,1])
                df_temp.insert(0, 'szr_start', bounds_true[:,0])
                
                # multiply exp id to a list equivalent to the number of seizures
                exp_id *= bounds_true.shape[0]
                df_temp.insert(0, 'exp_id', [filelist[i]] * bounds_true.shape[0])
                
                # append to dataframe
                df.append(df_temp)
                import pdb; pdb.set_trace()
            
    return df


def get_surround(feature, idx, surround_time):
    """
    get_surround(feature, idx, surround_time)

    Parameters
    ----------
    feature : TYPE
    idx : TYPE
    surround_time : TYPE

    Returns
    -------
    szrs : 2d ndarray (rows = seizures, cols = features)

    """
    
    outbins = np.int64(surround_time/win) # convert bounds to bins
    
    # create empty vectors to store before, after and within seizure features
    szrs = np.zeros((idx.shape[0],3))
    
    for i in range(idx.shape[0]): # iterate over seizure number

        # get feature before withing and after seizure
        szrs[i,0] = np.mean(feature[idx[i,0] - outbins[1]: idx[i,0] - outbins[0]]) # vef
        szrs[i,1] = np.mean(feature[idx[i,0]:idx[i,1]])
        szrs[i,2] = np.mean(feature[idx[i,1] + outbins[0]: idx[i,1] + outbins[1]])            
    return szrs



if __name__ == '__main__':

    tic = time.time() # start timer       
    multi_folder(main_path, )
    print('Time elapsed = ',time.time() - tic, 'seconds.')  
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    