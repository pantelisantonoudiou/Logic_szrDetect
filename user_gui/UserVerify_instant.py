# -*- coding: utf-8 -*-
"""
Created on Mon Apr 13 10:29:00 2020

@author: panton01
"""

## ------>>>>> USER INPUT <<<<<< --------------
input_path = r'W:\Maguire Lab\Trina\2020\06- June\5142_5143_5160_5220\filt_data'
file_id = '071220_5160a.csv' # 5221 5222 5223 5162
ch_list = [0,1] # selected channels
enable = 1 # set to 1 to select from files that have not been analyzed
execute = 1 # 1 to run gui, 0 for verification
# list(filter(lambda k: '.h5' in k, os.listdir(obj.rawdata_path)))
## -------<<<<<<<<<<

### -------- IMPORTS ---------- ###
import os, sys, json, tables
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt
from matplotlib.widgets import Button, SpanSelector, TextBox
# User Defined
if (os.path.dirname(os.path.abspath(os.getcwd())) in sys.path) == False:
    sys.path.append(os.path.dirname(os.path.abspath(os.getcwd())))
from multich_dataPrep import lab2mat
from array_helper import find_szr_idx, merge_close
from build_feature_data import get_data, get_features_allch
import features
### ------------------------------------------ ####

       
class UserVerify:
    """
    Class for User verification of detected seizures
    
    """
    
    # class constructor (data retrieval)
    def __init__(self, input_path):
        """
        lab2mat(main_path)

        Parameters
        ----------
        input_path : Str, Path to raw data.

        """
        # pass input path
        self.input_path = input_path

        # Get general path
        path = Path(input_path)
        self.gen_path = path.parent
        
        # load object properties as dict
        jsonfile = 'organized.json'
        obj_props = lab2mat.load(os.path.join(self.gen_path, jsonfile))
        self.rawdata_path = os.path.join(self.gen_path, 'filt_data')
        
        # create user verified path
        verpred_path = 'verified_predictions'
        obj_props.update({'verpred_path' : verpred_path})
        self.verpred_path = os.path.join(self.gen_path, verpred_path)
        
         # make path if it doesn't exist
        if os.path.exists( self.verpred_path) is False:
            os.mkdir( self.verpred_path)
        
        # write attributes to json file using a dict
        jsonpath = os.path.join(self.gen_path, jsonfile)
        open(jsonpath, 'w').write(json.dumps(obj_props))
        
        # get sampling rate
        self.fs = round(obj_props['fs'] / obj_props['down_factor'])
        self.win = obj_props['win']
        
        # Read method parameters into dataframe
        df = pd.read_csv('selected_method.csv')
        self.thresh = np.array(df.loc[0][df.columns.str.contains('Thresh')])
        self.weights = np.array(df.loc[0][df.columns.str.contains('Weight')])
        self.enabled = np.array(df.loc[0][df.columns.str.contains('Enabled')])
        
        # Get feature names
        self.feature_names = df.columns[df.columns.str.contains('Enabled')] # get
        self.feature_names = np.array([x.replace('Enabled_', '') for x in  self.feature_names])
 
    def get_feature_pred(self, file_id):
        """
        get_feature_pred(self, file_id)

        Parameters
        ----------
        file_id : Str

        Returns
        -------
        data : 3d Numpy Array (1D = segments, 2D = time, 3D = channel)
        bounds_pred : 2D Numpy Array (rows = seizures, cols = start and end points of detected seizures)

        """
        
        # Define parameter list
        param_list = (features.autocorr, features.line_length, features.rms, features.mad, features.var, features.std, features.psd, features.energy,
                      features.get_envelope_max_diff,) # single channel features
        cross_ch_param_list = (features.cross_corr, features.signal_covar, features.signal_abs_covar,) # cross channel features
        
        # Get data and true labels
        data = get_data(self.gen_path, file_id, ch_num = ch_list, inner_path={'data_path':'filt_data'}, load_y = False)
        
        # Extract features and normalize
        x_data, labels = get_features_allch(data,param_list, cross_ch_param_list) # Get features and labels
        x_data = StandardScaler().fit_transform(x_data) # Normalize data
        
        # Get predictions
        thresh = (np.mean(x_data) + self.thresh * np.std(x_data))   # get threshold vector
        y_pred_array = (x_data > thresh) # get predictions for all conditions
        y_pred = y_pred_array * self.weights * self.enabled    # get predictions based on weights and selected features
        y_pred = np.sum(y_pred, axis=1) / np.sum(self.weights * self.enabled) # normalize to weights and selected features
        y_pred = y_pred > 0.5                                       # get popular vote
        bounds_pred = find_szr_idx(y_pred, np.array([0,1]))         # get predicted seizure index
        
        # If seizures are detected proceed to refine them
        if bounds_pred.shape[0] > 0:
            
            # Merge seizures close together
            bounds_pred = merge_close(bounds_pred, merge_margin = 5)
            
            # Remove seizures where a feature (line length or power) is not higher than preceeding region
            idx = np.where(np.char.find(self.feature_names,'line_length_0')==0)[0][0]
            bounds_pred = self.refine_based_on_surround(x_data[:,idx], bounds_pred)    
        
        return bounds_pred
         
    
    def refine_based_on_surround(self, feature, idx):
        """
        refine_based_on_surround(self,data,idx)

        Parameters
        ----------
        feature : 1D Numpy Array, feature over time bins
        idx : 2 column Numpy Array (rows = seizure segments)
            First column = seizure start segment.
            Second column = seizure end segment.

        Returns
        -------
        idx : Same as input index
            Only seizure segments that obey threshold condition are kept.

        """

        # Set Parameters
        logic_idx = np.zeros(idx.shape[0], dtype=int) # pre-allocate logic vector

        for i in range(idx.shape[0]): # iterate through seizure segments
            
            # get seizure and surrounding segments
            bef = feature[idx[i,0] - round(90/self.win) : idx[i,0] - round(30/self.win) + 1] # segment before seizure
            szr = feature[idx[i,0] : idx[i,1]+1] # seizure segment 

            # check if power difference meets threshold
            cond = ( np.abs(np.median(szr)) / np.abs(np.median(bef)) )*100
            if cond > 130:
                logic_idx[i] = 1
        
        # get index that passed threshold
        idx = idx[logic_idx == 1,:]
        
        return idx
        
               
    def save_emptyidx(self,data_len):
         """
         Save user predictions to csv file as binary
        
         Returns
         -------
         None.
        
         """
         # pre allocate file with zeros
         ver_pred = np.zeros(data_len)
         
         # save file
         np.savetxt(os.path.join(self.verpred_path,file_id), ver_pred, delimiter=',',fmt='%i')
         print('Verified predictions for ', file_id, ' were saved')   
            

    
    def main_func(self, filename):
        """
        main_func(self, filename)

        Parameters
        ----------
        filename : String

        Returns
        -------
        data : 3d Numpy Array (1D = segments, 2D = time, 3D = channel)
        idx_bounds : 2D Numpy Array (rows = seizures, cols = start and end points of detected seizures)

        """
        
        print('File being analyzed: ', file_id)

        # get data and predictions
        idx_bounds = self.get_feature_pred(file_id.replace('.csv',''))
           
        # load raw data for visualization
        filepath = os.path.join(self.gen_path, 'reorganized_data' ,filename.replace('.csv','.h5') )
        f = tables.open_file(filepath, mode='r')
        data = f.root.data[:]
        f.close()
        
        # check whether to continue
        print('>>>>',idx_bounds.shape[0] ,'seizures detected')
        
        return data,idx_bounds

        
   
        
# Execute if module runs as main program
if __name__ == '__main__' :
    
    # # create instance
    obj = UserVerify(input_path)
    data, idx_bounds = obj.main_func(file_id)
    
    if idx_bounds is not False and execute == 1:
        
        if idx_bounds.shape[0] == 0: # check for zero seizures
            obj.save_emptyidx(data.shape[0])
            
        else: # otherwise proceed with gui creation
    
            # get gui
            from verify_gui import matplotGui,fig,ax
            fig.suptitle('To Submit Press Enter; To Select Drag Mouse Pointer : '+file_id, fontsize=12)
               
            # init object
            callback = matplotGui(data,idx_bounds,obj, file_id)
            
            # add buttons
            axprev = plt.axes([0.625, 0.05, 0.13, 0.075]) # previous
            bprev = Button(axprev, 'Previous: <')
            bprev.on_clicked(callback.previous)
            axnext = plt.axes([0.765, 0.05, 0.13, 0.075]) # next
            bnext = Button(axnext, 'Next: >')
            bnext.on_clicked(callback.forward)
            axaccept = plt.axes([0.125, 0.05, 0.13, 0.075]) # accept
            baccept = Button(axaccept, 'Accept: y')
            baccept.on_clicked(callback.accept)
            axreject = plt.axes([0.265, 0.05, 0.13, 0.075]) # reject
            breject = Button(axreject, 'Reject: n')
            breject.on_clicked(callback.reject)
            axbox = plt.axes([0.5, 0.055, 0.05, 0.05]) # seizure number
            text_box = TextBox(axbox, 'Szr #', initial='0')
            text_box.on_submit(callback.submit)
            
            # add key press
            idx_out = fig.canvas.mpl_connect('key_press_event', callback.keypress)
            
            # set useblit True on gtkagg for enhanced performance
            span = SpanSelector(ax, callback.onselect, 'horizontal', useblit=True,
                rectprops=dict(alpha=0.5, facecolor='red'))
    
    

       
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        